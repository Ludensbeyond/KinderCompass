"""Validation and deterministic fallback for conversation-supervisor results."""

from __future__ import annotations

import re
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from .config import disable_agent_entry_points
from .contracts import (
    CapabilityToolResult,
    ConversationExecutionLimits,
    ConversationExecutionMetadata,
    ConversationRequestContext,
    ConversationSupervisorResult,
    GeneratedConversationAnswer,
    PublicCitation,
    RoutingDecision,
)
from .model_factory import ModelFactoryError
from .supervisor import (
    ConversationSupervisorError,
    _allowed_tool_names,
    _assemble_result,
    create_conversation_supervisor_graph,
)
from .tools import (
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    PREFERENCE_STATE_TOOL_NAMES,
    QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
)


class ConversationValidationError(ValueError):
    """Validation rejection carrying a fixed, non-sensitive reason code."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ConversationSupervisorRunResult:
    """Validated agent response or one complete deterministic fallback."""

    response: dict[str, Any]
    metadata: ConversationExecutionMetadata


_NEUTRAL_WORDS = frozenset({
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
    "which", "while", "who", "why", "will", "with", "you", "your",
    "s",
})

_FALLBACK_REASONS = frozenset({
    "invalid_routing", "unknown_tool", "invalid_arguments", "missing_context",
    "conflicting_results", "multiple_mutations", "malformed_output",
    "unsupported_citation", "timeout", "execution_limit", "model_unavailable",
    "tool_error", "model_error", "validation_error",
})


def _fail(reason: str) -> None:
    raise ConversationValidationError(reason)


def _revalidate(contract: type[Any], value: Any) -> Any:
    payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
    return contract.model_validate(payload)


def _tool_calls(state: dict[str, Any]) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    for message in state.get("messages", []):
        if isinstance(message, AIMessage):
            calls.extend(
                (str(call.get("id") or ""), str(call.get("name") or ""))
                for call in message.tool_calls
            )
    return calls


def _school_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "school_id" and isinstance(child, str):
                found.add(child)
            else:
                found.update(_school_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_school_ids(child))
    return found


def _validate_profile_invariants(
    context: ConversationRequestContext,
    results: list[CapabilityToolResult],
) -> None:
    allowed_ids = set(
        context.selected_school_ids
        + context.eligible_school_ids
        + context.excluded_school_ids
    ) | _school_ids(context.profile)
    for result in results:
        if not _school_ids(result.profile).issubset(allowed_ids):
            _fail("validation_error")
        if result.mutates_profile and result.tool_name not in PREFERENCE_STATE_TOOL_NAMES:
            _fail("validation_error")
    if len(results) > 1:
        if any(result.mutates_profile for result in results):
            _fail("conflicting_results")
        baseline = (
            results[0].profile,
            results[0].understood,
            results[0].ready_to_search,
        )
        if any(
            (result.profile, result.understood, result.ready_to_search) != baseline
            for result in results[1:]
        ):
            _fail("conflicting_results")


def _validate_citations(
    context: ConversationRequestContext,
    route: RoutingDecision,
    answer: GeneratedConversationAnswer,
    result: ConversationSupervisorResult,
    tool_results: list[CapabilityToolResult],
) -> None:
    citations: dict[str, PublicCitation] = {}
    for tool_result in tool_results:
        for citation in tool_result.citations:
            existing = citations.get(citation.citation_id)
            if existing is not None and existing != citation:
                _fail("conflicting_results")
            citations[citation.citation_id] = citation
            if citation.evidence_scope == "school":
                if tool_result.tool_name != SELECTED_SCHOOL_EVIDENCE_TOOL_NAME:
                    _fail("unsupported_citation")
                if citation.school_id not in context.selected_school_ids:
                    _fail("unsupported_citation")
            elif citation.evidence_scope == "general":
                if tool_result.tool_name != GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME:
                    _fail("unsupported_citation")
            elif citation.evidence_scope == "structured":
                if tool_result.tool_name != QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME:
                    _fail("unsupported_citation")

    if any(citation_id not in citations for citation_id in answer.citation_ids):
        _fail("unsupported_citation")
    for tool_result in tool_results:
        available_ids = {citation.citation_id for citation in tool_result.citations}
        if available_ids and available_ids.isdisjoint(answer.citation_ids):
            _fail("unsupported_citation")
    resolved = [citations[citation_id] for citation_id in answer.citation_ids]
    if result.citations != resolved:
        _fail("unsupported_citation")

    selected_scopes = {citation.evidence_scope for citation in resolved}
    if route.scope != "combined" and len(selected_scopes) > 1:
        _fail("unsupported_citation")
    allowed_scopes = {
        "application_workflow": {"policy", "structured"},
        "structured_kindercompass": {"school", "structured"},
        "general_knowledge": {"general"},
        "combined": {"school", "general", "structured", "policy"},
    }.get(route.scope, set())
    if not selected_scopes.issubset(allowed_scopes):
        _fail("unsupported_citation")


def _validate_grounded_wording(
    answer: GeneratedConversationAnswer,
    tool_results: list[CapabilityToolResult],
) -> None:
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
    unsupported = answer_tokens - tokens - _NEUTRAL_WORDS
    if unsupported or not (answer_tokens - _NEUTRAL_WORDS):
        _fail("validation_error")


def validate_conversation_supervisor_state(
    state: dict[str, Any],
    context: ConversationRequestContext,
    registered_tool_names: Iterable[str],
    *,
    limits: Optional[ConversationExecutionLimits] = None,
) -> ConversationSupervisorResult:
    """Validate a completed graph state before any agent result is accepted."""

    execution_limits = limits or ConversationExecutionLimits()
    termination = state.get("termination_reason")
    if termination == "mutation_limit":
        _fail("multiple_mutations")
    if termination in {"tool_call_limit", "iteration_limit"}:
        _fail("execution_limit")
    if termination == "clarification":
        _fail("invalid_routing")
    if termination != "completed":
        _fail("validation_error")

    try:
        route = _revalidate(RoutingDecision, state.get("route"))
        answer = _revalidate(GeneratedConversationAnswer, state.get("answer"))
        result = _revalidate(ConversationSupervisorResult, state.get("result"))
        tool_results = [
            _revalidate(CapabilityToolResult, item)
            for item in state.get("tool_results", [])
        ]
    except ValidationError:
        _fail("malformed_output")

    if state.get("context") != context or result.route != route:
        _fail("validation_error")
    if route.scope != "clarification" and route.confidence < 0.7:
        _fail("invalid_routing")
    calls = _tool_calls(state)
    call_names = [name for _, name in calls]
    registered = set(registered_tool_names)
    if not call_names or len(call_names) > execution_limits.max_tool_calls:
        _fail("execution_limit")
    if any(not call_id for call_id, _ in calls) or len({call_id for call_id, _ in calls}) != len(calls):
        _fail("conflicting_results")
    if any(name not in registered for name in call_names):
        _fail("unknown_tool")
    if any(name not in _allowed_tool_names(route.scope) for name in call_names):
        _fail("invalid_routing")
    if call_names != [item.tool_name for item in tool_results]:
        _fail("conflicting_results")
    tool_messages = [
        message for message in state.get("messages", [])
        if isinstance(message, ToolMessage)
    ]
    if len(tool_messages) != len(calls):
        _fail("conflicting_results")
    for (call_id, name), message, tool_result in zip(calls, tool_messages, tool_results):
        if message.tool_call_id != call_id or message.name != name:
            _fail("conflicting_results")
        try:
            recorded = CapabilityToolResult.model_validate_json(str(message.content))
        except ValidationError:
            _fail("malformed_output")
        if recorded != tool_result:
            _fail("conflicting_results")
    if state.get("tool_calls") != len(call_names):
        _fail("conflicting_results")

    mutations = sum(item.mutates_profile for item in tool_results)
    if mutations > execution_limits.max_profile_mutations:
        _fail("multiple_mutations")
    if state.get("profile_mutations", 0) != mutations:
        _fail("conflicting_results")
    if route.scope == "combined" and len(set(call_names)) < 2:
        _fail("missing_context")
    if route.scope != "combined" and len(tool_results) > 1:
        _fail("conflicting_results")

    _validate_profile_invariants(context, tool_results)
    final_messages = [
        message for message in state.get("messages", [])
        if isinstance(message, AIMessage) and not message.tool_calls
    ]
    if not final_messages:
        _fail("malformed_output")
    try:
        recorded_answer = GeneratedConversationAnswer.model_validate_json(
            str(final_messages[-1].content),
        )
    except ValidationError:
        _fail("malformed_output")
    if recorded_answer != answer:
        _fail("conflicting_results")
    expected = _assemble_result(route, answer, tool_results)
    if result != expected:
        _fail("conflicting_results")
    _validate_citations(context, route, answer, result, tool_results)
    _validate_grounded_wording(answer, tool_results)
    return result


def _public_result(result: ConversationSupervisorResult) -> dict[str, Any]:
    citations = []
    for citation in result.citations:
        item = citation.model_dump(mode="json", exclude_none=True)
        item["chunk_id"] = item.pop("citation_id")
        citations.append(item)
    return {
        "profile": deepcopy(result.profile),
        "understood": list(result.understood),
        "ready_to_search": result.ready_to_search,
        "question": result.answer,
        "citations": citations,
        "answer_method": "agent_grounded",
        "fallback_reason": None,
        "evidence_category": result.evidence_category,
    }


def _fallback_reason(exc: Exception) -> str:
    if isinstance(exc, (ConversationValidationError, ConversationSupervisorError)):
        return exc.reason if exc.reason in _FALLBACK_REASONS else "validation_error"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ModelFactoryError):
        return "model_unavailable"
    if isinstance(exc, ValidationError):
        return "malformed_output"
    if type(exc).__name__ in {"GraphRecursionError", "RecursionError"}:
        return "execution_limit"
    return "validation_error"


def _safe_count(value: Any, maximum: int) -> int:
    return min(maximum, max(0, value if isinstance(value, int) else 0))


def run_conversation_supervisor(
    context: ConversationRequestContext,
    tools: list[BaseTool],
    deterministic_fallback: Callable[[], dict[str, Any]],
    *,
    model: Optional[Any] = None,
    model_factory: Optional[Callable[[], Any]] = None,
    graph_factory: Callable[..., Any] = create_conversation_supervisor_graph,
    limits: Optional[ConversationExecutionLimits] = None,
) -> ConversationSupervisorRunResult:
    """Run, validate, and fail closed through exactly one legacy invocation."""

    execution_limits = limits or ConversationExecutionLimits()
    state: dict[str, Any] = {}
    started = time.monotonic()
    try:
        graph = graph_factory(
            context, tools, model=model, model_factory=model_factory,
            limits=execution_limits,
        )
        state = graph.invoke({})
        result = validate_conversation_supervisor_state(
            state, context, (tool.name for tool in tools), limits=execution_limits,
        )
        response = _public_result(result)
        validation_succeeded = True
        fallback_reason = None
        termination_reason = "completed"
    except Exception as exc:
        fallback_reason = _fallback_reason(exc)
        with disable_agent_entry_points():
            response = deepcopy(deterministic_fallback())
        response["answer_method"] = "deterministic_fallback"
        response["fallback_reason"] = fallback_reason
        validation_succeeded = False
        if state.get("termination_reason") in {
            "clarification", "tool_call_limit", "mutation_limit", "iteration_limit",
        }:
            termination_reason = state["termination_reason"]
        elif fallback_reason == "timeout":
            termination_reason = "timeout"
        elif fallback_reason in {"tool_error", "model_error", "model_unavailable"}:
            termination_reason = "error"
        else:
            termination_reason = "validation_failed"

    names = [item.tool_name for item in state.get("tool_results", [])][:3]
    metadata = ConversationExecutionMetadata(
        mode="agent",
        route_scope=getattr(state.get("route"), "scope", None),
        tool_names=names,
        tool_calls=_safe_count(state.get("tool_calls"), 3),
        profile_mutations=_safe_count(state.get("profile_mutations"), 1),
        graph_iterations=_safe_count(state.get("graph_iterations"), 8),
        latency_ms=min(300_000, max(0, int((time.monotonic() - started) * 1_000))),
        validation_succeeded=validation_succeeded,
        termination_reason=termination_reason,
        fallback_reason=fallback_reason,
    )
    return ConversationSupervisorRunResult(response=response, metadata=metadata)
