"""Bounded full-conversation supervisor graph.

The graph in this module only orchestrates registered, context-bound tools. It
does not replace the deterministic fallback or select a rollout mode; those
boundaries are intentionally owned by later migration steps.
"""

from __future__ import annotations

import json
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
    DECISION_AND_CALCULATION_TOOL_NAMES,
    EVIDENCE_TOOL_NAMES,
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    PREFERENCE_STATE_TOOL_NAMES,
    QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
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
Return only JSON matching: {"scope": one of application_workflow,
structured_kindercompass, general_knowledge, combined, clarification; "intent":
a short snake_case name; "confidence": 0..1; "clarification": string or null}.
Application workflow covers preference state, recommendations, comparisons,
fees, eligibility, closest-school and exclusion operations. Structured
KinderCompass covers catalogue facts such as food, programmes, fees, vacancy,
hours, transport, contact and location. General knowledge covers Singapore
early-childhood or policy guidance. Combined requires genuinely distinct
sources. School-published claims not represented by a structured field use the
selected-school webpage evidence capability. Do not answer the question."""

_SUPERVISOR_PROMPT = """You are a bounded KinderCompass tool supervisor. You must call at least
one registered tool before answering. Choose only tools applicable to the typed
route. A combined route may use multiple read-only tools. Never supply school
records, family values, profile state, calculations, facts, citations, or tool
configuration; those are server-owned. After the necessary tool results are
available, return only JSON matching {"answer": string, "citation_ids":
[strings]}. The wording must use only tool-returned answer candidates and
grounding facts, and citation IDs must come from tool results."""


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
                f"Newest message: {context.message}\n"
                f"Bounded profile context: {_bounded_profile(context.profile)}"
            )
        ),
    ]


def _parse_json_message(response: AIMessage, contract: type[Any]) -> Any:
    if not isinstance(response.content, str):
        raise TypeError("agent model JSON output must be text")
    return contract.model_validate_json(response.content)


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
    tool_enabled_model = model.bind_tools(tools)

    def route_turn(state: ConversationSupervisorState) -> ConversationSupervisorState:
        iterations = state.get("graph_iterations", 0)
        if iterations >= execution_limits.max_graph_iterations:
            return {"termination_reason": "iteration_limit"}
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
        response = _invoke_model(tool_enabled_model, state["messages"])

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
                answer = _parse_json_message(response, GeneratedConversationAnswer)
            except Exception:
                raise ConversationSupervisorError(
                    "malformed_output", "agent answer output was invalid",
                ) from None
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
            "messages": [*state["messages"], *tool_messages],
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
