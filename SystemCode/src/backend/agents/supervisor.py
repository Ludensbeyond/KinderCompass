"""Bounded full-conversation supervisor graph.

The graph in this module only orchestrates registered, context-bound tools. It
does not replace the deterministic fallback or select a rollout mode; those
boundaries are intentionally owned by later migration steps.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from .contracts import (
    CapabilityToolResult,
    ConversationExecutionLimits,
    ConversationRequestContext,
    ConversationSupervisorResult,
    GeneratedConversationAnswer,
    RoutingDecision,
)
from .model_factory import create_conversation_agent_model
from .tools import (
    ASSESS_SELECTED_SCHOOL_TOOL_NAME,
    COMPARE_SELECTED_SCHOOLS_TOOL_NAME,
    CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
    DECISION_AND_CALCULATION_TOOL_NAMES,
    EVIDENCE_TOOL_NAMES,
    EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME,
    EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME,
    EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME,
    EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME,
    FIND_CLOSEST_SCHOOL_TOOL_NAME,
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    PREFERENCE_STATE_TOOL_NAMES,
    QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
    RECOMMEND_SELECTED_SCHOOL_TOOL_NAME,
    RESET_PREFERENCES_TOOL_NAME,
    RUN_WHAT_IF_SCENARIO_TOOL_NAME,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    UPDATE_PREFERENCES_TOOL_NAME,
)


class ConversationSupervisorState(TypedDict, total=False):
    """Backend-only execution state returned by the compiled graph."""

    context: ConversationRequestContext
    route: RoutingDecision
    messages: list[BaseMessage]
    tool_results: list[CapabilityToolResult]
    answer: GeneratedConversationAnswer
    result: ConversationSupervisorResult
    tool_calls: int
    profile_mutations: int
    graph_iterations: int
    termination_reason: str


_ROUTING_PROMPT = """You route one KinderCompass conversation turn before any tool is used.
Return one JSON object with exactly these fields and no markdown:
{"scope":"application_workflow|structured_kindercompass|general_knowledge|combined|clarification","intent":"snake_case_name","confidence":0.95,"clarification":null}.
Treat the server-classified intent supplied with the turn as authoritative. Map
update/reset/recommend/compare/assessment/fee/eligibility/distance/exclusion
intents to application_workflow; ask_selected_school_evidence to
structured_kindercompass; ask_general_knowledge to general_knowledge; and
ask_combined_evidence to combined. Map needs_clarification to clarification
unless the bounded profile contains a pending preference flow that the newest
message continues.
Use confidence 0.95 when applying this authoritative mapping.
Application workflow covers preference state, recommendations, comparisons,
fees, eligibility, closest-school and exclusion operations. Structured
KinderCompass covers catalogue facts such as food, programmes, fees, vacancy,
hours, transport, contact and location. General knowledge covers Singapore
early-childhood or policy guidance. Combined requires genuinely distinct
sources. School-published claims not represented by a structured field use the
selected-school webpage evidence capability. Do not answer the question."""

_SUPERVISOR_PROMPT = """You are a bounded KinderCompass tool supervisor. You must call at least
one registered tool before answering. Choose the single capability whose name
matches the server-classified intent. For update_preferences, use
continue_pending_preference_flow only when the bounded profile contains a
pending flow that the newest message answers; otherwise use update_preferences.
For ask_selected_school_evidence, use query_structured_school_facts only for
food, programmes, fees, vacancy, operating hours, transport, contact, or
location; otherwise use search_selected_school_evidence. A combined route must
call search_selected_school_evidence and search_general_knowledge together.
Do not call overlapping capabilities. Never supply school
records, family values, profile state, calculations, facts, citations, or tool
configuration; those are server-owned. After the necessary tool results are
available, return one JSON object with exactly these fields and no markdown:
{"answer":"grounded answer","citation_ids":["id"]}. Use the tool's answer
candidate verbatim whenever possible. The wording must use only tool-returned answer candidates and
grounding facts, and citation IDs must come from tool results."""


_NEUTRAL_ANSWER_WORDS = frozenset({
    "a", "about", "according", "also", "an", "and", "are", "as", "at",
    "available", "based", "be", "because", "been", "but", "by", "can",
    "compared", "could", "current", "data", "describes", "did", "do", "does",
    "each", "estimated", "for", "from", "guidance", "has", "have", "here",
    "how", "i", "if", "in", "indicates", "information", "is", "it", "its",
    "may", "means", "more", "no", "not", "of", "offers", "official", "on",
    "one", "only", "or", "preschool", "preschools", "provides", "result",
    "results", "says", "school", "schools", "shows", "so", "than", "that",
    "the", "their", "them", "there", "these", "they", "this", "those", "to",
    "unavailable", "use", "uses", "was", "webpage", "were", "what", "when",
    "which", "while", "who", "why", "will", "with", "you", "your", "s",
})


class ConversationSupervisorError(ValueError):
    """Graph failure carrying only a fixed, non-sensitive reason code."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def _bounded_profile(profile: dict[str, Any]) -> str:
    rendered = json.dumps(profile, sort_keys=True, default=str, separators=(",", ":"))
    return rendered if len(rendered) <= 4_000 else rendered[:4_000] + "..."


def _routing_messages(context: ConversationRequestContext) -> list[BaseMessage]:
    return [
        SystemMessage(content=_ROUTING_PROMPT),
        HumanMessage(
            content=(
                f"Newest message: {context.message}\n"
                f"Server-classified intent: {context.deterministic_intent or 'unavailable'}\n"
                f"Bounded profile context: {_bounded_profile(context.profile)}\n"
                f"Selected schools: {len(context.selected_schools)}; "
                f"eligible results: {len(context.eligible_schools)}; "
                f"excluded results: {len(context.excluded_schools)}; "
                f"family supplied: {context.family is not None}; "
                f"postal code supplied: {context.home_postal_code is not None}."
            )
        ),
    ]


def _supervisor_messages(
    context: ConversationRequestContext,
    route: RoutingDecision,
) -> list[BaseMessage]:
    return [
        SystemMessage(content=_SUPERVISOR_PROMPT),
        HumanMessage(
            content=(
                f"Typed route: {route.model_dump_json()}\n"
                f"Server-classified intent: {context.deterministic_intent or route.intent}\n"
                f"Newest message: {context.message}\n"
                f"Bounded profile context: {_bounded_profile(context.profile)}"
            )
        ),
    ]


def _parse_json_message(response: AIMessage, contract: type[Any]) -> Any:
    if not isinstance(response.content, str):
        raise TypeError("agent model JSON output must be text")
    content = response.content.strip()
    if content.startswith("```json\n") and content.endswith("```"):
        content = content[8:-3].strip()
    elif "{" in content and "}" in content:
        content = content[content.find("{"):content.rfind("}") + 1]
    return contract.model_validate_json(content)


def _invoke_model(model: Any, messages: list[BaseMessage]) -> AIMessage:
    try:
        response = model.invoke(messages)
    except TimeoutError:
        raise ConversationSupervisorError("timeout", "agent execution timed out") from None
    except Exception:
        raise ConversationSupervisorError("model_error", "agent model failed") from None
    if not isinstance(response, AIMessage):
        raise ConversationSupervisorError("model_error", "agent model returned an invalid message")
    return response


def _parse_generated_answer(response: AIMessage) -> GeneratedConversationAnswer:
    """Accept typed output, JSON, or plain wording for server-side grounding."""

    if len(response.tool_calls) == 1:
        return GeneratedConversationAnswer.model_validate(
            response.tool_calls[0].get("args")
        )
    if response.tool_calls:
        raise ValueError("agent answer used an unexpected tool")
    try:
        return _parse_json_message(response, GeneratedConversationAnswer)
    except Exception:
        if isinstance(response.content, str) and response.content.strip():
            return GeneratedConversationAnswer(
                answer=response.content.strip(), citation_ids=[],
            )
        raise


def grounded_answer_is_valid(
    answer: GeneratedConversationAnswer,
    tool_results: list[CapabilityToolResult],
) -> bool:
    """Return whether generated wording contains only tool-grounded terms."""

    source = " ".join(
        [
            item
            for result in tool_results
            for item in [result.answer_candidate, *result.grounding_facts]
        ]
        + [
            f"{citation.title} {citation.authority or ''}"
            for result in tool_results
            for citation in result.citations
        ]
    )
    tokens = set(re.findall(r"[a-z0-9]+", source.casefold()))
    answer_tokens = set(re.findall(r"[a-z0-9]+", answer.answer.casefold()))
    unsupported = answer_tokens - tokens - _NEUTRAL_ANSWER_WORDS
    return not unsupported and bool(answer_tokens - _NEUTRAL_ANSWER_WORDS)


def _authoritative_composition(
    answer: GeneratedConversationAnswer,
    tool_results: list[CapabilityToolResult],
) -> GeneratedConversationAnswer:
    """Keep valid model wording, otherwise use bounded authoritative candidates."""

    citations = list(dict.fromkeys(
        citation.citation_id
        for result in tool_results
        for citation in result.citations
    ))
    # School-published claims keep the retrieval adapter's wording verbatim so
    # the claim and its school-scoped citations cannot drift during paraphrase.
    if any(
        result.tool_name == SELECTED_SCHOOL_EVIDENCE_TOOL_NAME
        for result in tool_results
    ):
        candidate = " ".join(result.answer_candidate for result in tool_results)
        if len(candidate) > 800:
            candidate = candidate[:800].rstrip()
        return GeneratedConversationAnswer(
            answer=candidate, citation_ids=citations,
        )
    if grounded_answer_is_valid(answer, tool_results):
        return answer.model_copy(update={"citation_ids": citations})
    candidate = " ".join(result.answer_candidate for result in tool_results)
    if len(candidate) > 800:
        candidate = candidate[:800].rstrip()
    return GeneratedConversationAnswer(answer=candidate, citation_ids=citations)


def _tool_candidate_answer(
    tool_results: list[CapabilityToolResult],
) -> GeneratedConversationAnswer:
    """Build the safest bounded answer when provider composition is unusable."""

    placeholder = GeneratedConversationAnswer(
        answer=tool_results[0].answer_candidate,
        citation_ids=[],
    )
    return _authoritative_composition(placeholder, tool_results)


def _authoritative_arguments(
    tool_name: str,
    model_arguments: Any,
    context: ConversationRequestContext,
) -> dict[str, Any]:
    """Strip model-authored context while retaining typed operation choices."""

    arguments = model_arguments if isinstance(model_arguments, dict) else {}
    if tool_name in PREFERENCE_STATE_TOOL_NAMES | DECISION_AND_CALCULATION_TOOL_NAMES:
        return {}
    if tool_name in EVIDENCE_TOOL_NAMES:
        return {"question": context.message}
    if tool_name == QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME:
        return {
            key: arguments[key]
            for key in ("operation", "school_ids")
            if key in arguments
        }
    return arguments


def _allowed_tool_names(scope: str) -> frozenset[str]:
    if scope == "application_workflow":
        return PREFERENCE_STATE_TOOL_NAMES | DECISION_AND_CALCULATION_TOOL_NAMES
    if scope == "structured_kindercompass":
        return frozenset({
            QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
            SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
        })
    if scope == "general_knowledge":
        return frozenset({GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME})
    if scope == "combined":
        return (
            PREFERENCE_STATE_TOOL_NAMES
            | DECISION_AND_CALCULATION_TOOL_NAMES
            | EVIDENCE_TOOL_NAMES
            | frozenset({QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME})
        )
    return frozenset()


_INTENT_SCOPES = {
    "update_preferences": "application_workflow",
    "reset_preferences": "application_workflow",
    "find_closest_preschool": "application_workflow",
    "recommend_selected_preschool": "application_workflow",
    "assess_selected_preschool": "application_workflow",
    "explain_top_ranked_preschool": "application_workflow",
    "compare_selected_preschools": "application_workflow",
    "explain_selected_tradeoffs": "application_workflow",
    "explain_evidence_provenance": "application_workflow",
    "run_what_if_scenario": "application_workflow",
    "explain_school_exclusion": "application_workflow",
    "ask_selected_school_evidence": "structured_kindercompass",
    "ask_general_knowledge": "general_knowledge",
    "ask_combined_evidence": "combined",
}

_INTENT_TOOL_NAMES = {
    "reset_preferences": frozenset({RESET_PREFERENCES_TOOL_NAME}),
    "find_closest_preschool": frozenset({FIND_CLOSEST_SCHOOL_TOOL_NAME}),
    "recommend_selected_preschool": frozenset({RECOMMEND_SELECTED_SCHOOL_TOOL_NAME}),
    "assess_selected_preschool": frozenset({ASSESS_SELECTED_SCHOOL_TOOL_NAME}),
    "explain_top_ranked_preschool": frozenset({EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME}),
    "compare_selected_preschools": frozenset({COMPARE_SELECTED_SCHOOLS_TOOL_NAME}),
    "explain_selected_tradeoffs": frozenset({EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME}),
    "explain_evidence_provenance": frozenset({EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME}),
    "run_what_if_scenario": frozenset({RUN_WHAT_IF_SCENARIO_TOOL_NAME}),
    "explain_school_exclusion": frozenset({EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME}),
    "ask_selected_school_evidence": frozenset({
        SELECTED_SCHOOL_EVIDENCE_TOOL_NAME, QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
    }),
    "ask_general_knowledge": frozenset({GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME}),
    "ask_combined_evidence": frozenset({
        SELECTED_SCHOOL_EVIDENCE_TOOL_NAME, GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    }),
}


def _has_pending_preference_flow(context: ConversationRequestContext) -> bool:
    return any(
        context.profile.get(field)
        for field in ("pending", "pending_contradiction", "pending_relaxation")
    )


def _authoritative_route(context: ConversationRequestContext) -> RoutingDecision | None:
    """Map the already validated server intent to a bounded capability scope."""

    intent = context.deterministic_intent
    if not intent:
        return None
    if intent == "needs_clarification":
        if _has_pending_preference_flow(context):
            return RoutingDecision(
                scope="application_workflow", intent=intent, confidence=1,
            )
        return RoutingDecision(
            scope="clarification",
            intent=intent,
            confidence=1,
            clarification="Could you clarify what you would like me to do?",
        )
    scope = _INTENT_SCOPES.get(intent)
    if scope is None:
        return None
    return RoutingDecision(scope=scope, intent=intent, confidence=1)


def _tools_for_intent(
    context: ConversationRequestContext, tools: list[BaseTool],
) -> list[BaseTool]:
    intent = context.deterministic_intent
    if not intent:
        return tools
    if intent == "update_preferences":
        names = frozenset({
            CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME
            if _has_pending_preference_flow(context)
            else UPDATE_PREFERENCES_TOOL_NAME
        })
    elif intent == "needs_clarification" and _has_pending_preference_flow(context):
        names = frozenset({CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME})
    elif intent == "ask_selected_school_evidence":
        structured_markers = (
            "food", "programme", "program", "fee", "vacanc", "operating hour",
            "transport", "contact", "location", "structured fact", "arbitrary field",
        )
        names = frozenset({
            QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME
            if any(marker in context.message.casefold() for marker in structured_markers)
            else SELECTED_SCHOOL_EVIDENCE_TOOL_NAME
        })
    else:
        names = _INTENT_TOOL_NAMES.get(intent, frozenset())
    selected = [tool for tool in tools if tool.name in names]
    return selected or tools


def _assemble_result(
    route: RoutingDecision,
    answer: GeneratedConversationAnswer,
    tool_results: list[CapabilityToolResult],
) -> ConversationSupervisorResult:
    """Assemble public-shaped fields while preserving tool authority."""

    authoritative = next(
        (result for result in reversed(tool_results) if result.mutates_profile),
        tool_results[-1],
    )
    available_citations = {
        citation.citation_id: citation
        for result in tool_results
        for citation in result.citations
    }
    citations = [
        available_citations[citation_id]
        for citation_id in answer.citation_ids
        if citation_id in available_citations
    ]
    categories = {result.evidence_category for result in tool_results}
    category = authoritative.evidence_category
    for preferred in (
        "school_published_claim", "calculated_estimate", "authoritative_fact",
        "parent_sentiment",
    ):
        if preferred in categories:
            category = preferred
            break
    return ConversationSupervisorResult(
        route=route,
        profile=authoritative.profile,
        understood=authoritative.understood,
        ready_to_search=authoritative.ready_to_search,
        answer=answer.answer,
        citations=citations,
        answer_status=(
            "combined_evidence"
            if route.scope == "combined"
            else authoritative.answer_status
        ),
        evidence_category=category,
    )


def create_conversation_supervisor_graph(
    context: ConversationRequestContext,
    tools: list[BaseTool],
    *,
    model: Optional[Any] = None,
    model_factory: Optional[Callable[[], Any]] = None,
    limits: Optional[ConversationExecutionLimits] = None,
) -> Any:
    """Compile a supervisor for one context and its context-bound tool registry."""

    execution_limits = limits or ConversationExecutionLimits()
    registry = {tool.name: tool for tool in tools}
    if not registry:
        raise ValueError("conversation supervisor requires at least one registered tool")
    if len(registry) != len(tools):
        raise ValueError("conversation supervisor tool names must be unique")

    if model is None:
        factory = model_factory or create_conversation_agent_model
        model = factory()
    if model is None:
        raise ValueError("conversation agent mode requires an available model")
    scoped_tools = _tools_for_intent(context, tools)
    try:
        tool_selection_model = model.bind_tools(scoped_tools, tool_choice="required")
    except TypeError:
        # Minimal injected test doubles may expose only the portable bind_tools
        # signature. Provider clients use the required-tool variant above.
        tool_selection_model = model.bind_tools(scoped_tools)
    try:
        answer_model = model.bind_tools(
            [GeneratedConversationAnswer],
            tool_choice=GeneratedConversationAnswer.__name__,
        )
    except TypeError:
        # Preserve compatibility with injected portable model doubles. Their
        # plain JSON response continues through the same strict contract.
        answer_model = model

    def route_turn(state: ConversationSupervisorState) -> ConversationSupervisorState:
        iterations = state.get("graph_iterations", 0)
        if iterations >= execution_limits.max_graph_iterations:
            return {"termination_reason": "iteration_limit"}
        route = _authoritative_route(context)
        if route is None:
            response = _invoke_model(model, _routing_messages(context))
            try:
                route = _parse_json_message(response, RoutingDecision)
            except Exception:
                raise ConversationSupervisorError(
                    "invalid_routing", "agent routing output was invalid",
                ) from None
        update: ConversationSupervisorState = {
            "context": context,
            "route": route,
            "graph_iterations": iterations + 1,
        }
        if route.scope == "clarification":
            update["termination_reason"] = "clarification"
        else:
            update["messages"] = _supervisor_messages(context, route)
        return update

    def call_model(state: ConversationSupervisorState) -> ConversationSupervisorState:
        iterations = state.get("graph_iterations", 0)
        if iterations >= execution_limits.max_graph_iterations:
            return {"termination_reason": "iteration_limit"}
        invocation_model = (
            tool_selection_model if state.get("tool_calls", 0) == 0 else answer_model
        )
        response = _invoke_model(invocation_model, state["messages"])

        if state.get("tool_calls", 0) and response.tool_calls:
            try:
                typed_answer = _authoritative_composition(
                    _parse_generated_answer(response), state["tool_results"],
                )
            except Exception:
                typed_answer = _tool_candidate_answer(state["tool_results"])
            # The answer submission is a typed model response, not a capability
            # invocation. Normalize it to the existing recorded-answer shape so
            # validation still counts and verifies only registered tool calls.
            response = AIMessage(content=typed_answer.model_dump_json())

        messages = [*state["messages"], response]
        update: ConversationSupervisorState = {
            "messages": messages,
            "graph_iterations": iterations + 1,
        }
        requested = len(response.tool_calls)
        completed = state.get("tool_calls", 0)
        if requested and completed + requested > execution_limits.max_tool_calls:
            update["termination_reason"] = "tool_call_limit"
            return update

        requested_mutations = sum(
            call.get("name") in PREFERENCE_STATE_TOOL_NAMES
            for call in response.tool_calls
        )
        if state.get("profile_mutations", 0) + requested_mutations > execution_limits.max_profile_mutations:
            update["termination_reason"] = "mutation_limit"
            return update

        if not requested and state.get("tool_calls", 0) == 0:
            update["messages"] = [
                *messages,
                HumanMessage(content="A registered capability tool is required before an answer."),
            ]
        elif not requested:
            try:
                answer = _authoritative_composition(
                    _parse_generated_answer(response), state["tool_results"],
                )
            except Exception:
                answer = _tool_candidate_answer(state["tool_results"])
            update["messages"] = [
                *state["messages"], AIMessage(content=answer.model_dump_json()),
            ]
            update["answer"] = answer
            update["result"] = _assemble_result(
                state["route"], answer, state["tool_results"],
            )
            update["termination_reason"] = "completed"
        return update

    def call_tools(state: ConversationSupervisorState) -> ConversationSupervisorState:
        response = state["messages"][-1]
        if not isinstance(response, AIMessage):
            raise TypeError("tool execution requires an AIMessage")

        results = list(state.get("tool_results", []))
        tool_messages: list[ToolMessage] = []
        mutations = state.get("profile_mutations", 0)
        for call in response.tool_calls:
            name = call.get("name")
            if name not in registry:
                raise ConversationSupervisorError(
                    "unknown_tool", "model requested an unregistered tool",
                )
            if name not in _allowed_tool_names(state["route"].scope):
                raise ConversationSupervisorError(
                    "invalid_routing", "model requested a tool outside the typed route",
                )
            arguments = _authoritative_arguments(name, call.get("args"), context)
            try:
                raw_result = registry[name].invoke(arguments)
                result = CapabilityToolResult.model_validate(raw_result)
            except TimeoutError:
                raise ConversationSupervisorError(
                    "timeout", "capability tool timed out",
                ) from None
            except Exception as exc:
                if str(exc) == "no pending preference flow is available":
                    reason = "missing_context"
                elif isinstance(exc, ValueError) or type(exc).__name__ == "ValidationError":
                    reason = "invalid_arguments"
                else:
                    reason = "tool_error"
                raise ConversationSupervisorError(reason, "capability tool failed") from None
            results.append(result)
            mutations += int(result.mutates_profile)
            if mutations > execution_limits.max_profile_mutations:
                return {
                    "tool_results": results,
                    "profile_mutations": mutations,
                    "termination_reason": "mutation_limit",
                }
            tool_messages.append(ToolMessage(
                content=result.model_dump_json(),
                name=name,
                tool_call_id=call["id"],
            ))
        return {
            "messages": [
                *state["messages"],
                *tool_messages,
                HumanMessage(content=(
                    "Compose only from the tool results. Use each answer_candidate "
                    "verbatim whenever possible and include every returned citation_id."
                )),
            ],
            "tool_results": results,
            "tool_calls": state.get("tool_calls", 0) + len(response.tool_calls),
            "profile_mutations": mutations,
        }

    def after_routing(state: ConversationSupervisorState) -> str:
        return END if state.get("termination_reason") else "model"

    def after_model(state: ConversationSupervisorState) -> str:
        if state.get("termination_reason"):
            return END
        response = state["messages"][-1]
        if isinstance(response, AIMessage) and response.tool_calls:
            return "tools"
        return "model"

    builder = StateGraph(ConversationSupervisorState)
    builder.add_node("route", route_turn)
    builder.add_node("model", call_model)
    builder.add_node("tools", call_tools)
    builder.add_edge(START, "route")
    builder.add_conditional_edges("route", after_routing)
    builder.add_conditional_edges("model", after_model)
    builder.add_edge("tools", "model")
    return builder.compile()
