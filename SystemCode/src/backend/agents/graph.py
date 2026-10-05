"""Bounded LangGraph orchestration for selected-school webpage evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Optional, Sequence, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .contracts import (
    EvidenceCitation,
    GeneratedEvidenceAnswer,
    RetrievedEvidence,
    SelectedSchoolAgentRequest,
)
from .model_factory import create_agent_model
from .tools import (
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    create_selected_school_evidence_tool,
)


DEFAULT_MAX_TOOL_CALLS = 1
DEFAULT_MAX_GRAPH_ITERATIONS = 3
MAX_TOOL_CALL_LIMIT = 3
MAX_GRAPH_ITERATION_LIMIT = 6


@dataclass(frozen=True)
class SelectedSchoolGraphLimits:
    """Small, server-controlled execution limits for the first graph."""

    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
    max_graph_iterations: int = DEFAULT_MAX_GRAPH_ITERATIONS

    def __post_init__(self) -> None:
        if not 1 <= self.max_tool_calls <= MAX_TOOL_CALL_LIMIT:
            raise ValueError("max_tool_calls is outside the supported range")
        if not 1 <= self.max_graph_iterations <= MAX_GRAPH_ITERATION_LIMIT:
            raise ValueError("max_graph_iterations is outside the supported range")


@dataclass(frozen=True)
class SelectedSchoolGraphResult:
    """Validated agent answer or the caller-supplied deterministic fallback."""

    answer: str
    citations: tuple[EvidenceCitation, ...]
    answer_method: str
    fallback_reason: Optional[str] = None
    tool_calls: int = 0
    graph_iterations: int = 0
    termination_reason: str = "error"

    @property
    def execution_metadata(self) -> dict[str, Any]:
        """Return the complete, privacy-safe observability surface."""

        return {
            "answer_method": self.answer_method,
            "fallback_reason": self.fallback_reason,
            "tool_calls": self.tool_calls,
            "graph_iterations": self.graph_iterations,
            "termination_reason": self.termination_reason,
        }


class SelectedSchoolGraphState(TypedDict, total=False):
    """Internal graph state; it is never part of the HTTP wire contract."""

    request: SelectedSchoolAgentRequest
    messages: Annotated[list[BaseMessage], add_messages]
    evidence: list[RetrievedEvidence]
    answer: GeneratedEvidenceAnswer
    tool_calls: int
    graph_iterations: int
    termination_reason: str


_SYSTEM_PROMPT = """You answer a question about exactly one selected school.
You must call search_selected_school_evidence before answering. Use only the
returned passages. After retrieval, return only JSON with the keys answer,
citation_ids, and evidence_available. Never invent a citation identifier."""


def _initial_messages(request: SelectedSchoolAgentRequest) -> list[BaseMessage]:
    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"School name: {request.school_name}\n"
                f"Authoritative school ID: {request.school_id}\n"
                f"Question: {request.question}"
            )
        ),
    ]


def create_selected_school_evidence_graph(
    index: dict[str, Any],
    *,
    model: Optional[Any] = None,
    model_factory: Optional[Callable[[], Any]] = None,
    limits: Optional[SelectedSchoolGraphLimits] = None,
) -> Any:
    """Compile the selected-school graph without integrating it into services.

    The model chooses when to call the sole registered tool, but the graph
    replaces its arguments with authoritative request values and accepts no
    answer until retrieval has run. Both model iterations and tool executions
    are bounded independently.
    """

    execution_limits = limits or SelectedSchoolGraphLimits()
    if model is None:
        factory = model_factory or create_agent_model
        model = factory()
    if model is None:
        raise ValueError("agent mode requires an available model")

    evidence_tool = create_selected_school_evidence_tool(index)
    tool_enabled_model = model.bind_tools([evidence_tool])

    def call_model(state: SelectedSchoolGraphState) -> SelectedSchoolGraphState:
        iterations = state.get("graph_iterations", 0)
        if iterations >= execution_limits.max_graph_iterations:
            return {"termination_reason": "graph_iteration_limit"}

        request = state["request"]
        existing_messages = state.get("messages", [])
        messages = existing_messages or _initial_messages(request)
        response = tool_enabled_model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise TypeError("agent model must return an AIMessage")

        update: SelectedSchoolGraphState = {
            "messages": [response] if existing_messages else [*messages, response],
            "graph_iterations": iterations + 1,
        }
        requested_calls = len(response.tool_calls)
        completed_calls = state.get("tool_calls", 0)
        if requested_calls and completed_calls + requested_calls > execution_limits.max_tool_calls:
            update["termination_reason"] = "tool_call_limit"
            return update

        if not requested_calls and completed_calls:
            update["answer"] = GeneratedEvidenceAnswer.model_validate_json(response.content)
            update["termination_reason"] = "completed"
        elif not requested_calls:
            update["messages"].append(
                HumanMessage(content="Retrieval is required before an answer. Call the registered tool.")
            )
        return update

    def call_tool(state: SelectedSchoolGraphState) -> SelectedSchoolGraphState:
        request = state["request"]
        response = state["messages"][-1]
        if not isinstance(response, AIMessage):
            raise TypeError("tool execution requires an AIMessage")

        evidence = list(state.get("evidence", []))
        tool_messages: list[ToolMessage] = []
        for tool_call in response.tool_calls:
            if tool_call["name"] != SELECTED_SCHOOL_EVIDENCE_TOOL_NAME:
                raise ValueError("model requested an unregistered tool")
            result = evidence_tool.invoke(request.model_dump())
            evidence.extend(result)
            tool_messages.append(
                ToolMessage(
                    content=json.dumps([item.model_dump(mode="json") for item in result]),
                    name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                    tool_call_id=tool_call["id"],
                )
            )
        return {
            "messages": tool_messages,
            "evidence": evidence,
            "tool_calls": state.get("tool_calls", 0) + len(response.tool_calls),
        }

    def route_after_model(state: SelectedSchoolGraphState) -> str:
        if state.get("termination_reason"):
            return END
        response = state["messages"][-1]
        if isinstance(response, AIMessage) and response.tool_calls:
            return "search_evidence"
        return "model"

    builder = StateGraph(SelectedSchoolGraphState)
    builder.add_node("model", call_model)
    builder.add_node("search_evidence", call_tool)
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route_after_model)
    builder.add_edge("search_evidence", "model")
    return builder.compile()


def run_selected_school_evidence_graph(
    index: dict[str, Any],
    request: SelectedSchoolAgentRequest,
    *,
    deterministic_answer: str,
    deterministic_citations: Sequence[EvidenceCitation],
    model: Optional[Any] = None,
    model_factory: Optional[Callable[[], Any]] = None,
    limits: Optional[SelectedSchoolGraphLimits] = None,
) -> SelectedSchoolGraphResult:
    """Run and validate the graph, falling back on every execution failure.

    Only exception class names cross this boundary. Provider messages, prompts,
    retrieved text, and other potentially sensitive execution details do not.
    """

    state: SelectedSchoolGraphState = {}
    try:
        graph = create_selected_school_evidence_graph(
            index,
            model=model,
            model_factory=model_factory,
            limits=limits,
        )
        state = graph.invoke({"request": request})
        if state.get("termination_reason") != "completed" or "answer" not in state:
            raise ValueError("selected-school graph did not complete with an answer")

        answer = state["answer"]
        evidence = state.get("evidence", [])
        if not isinstance(answer, GeneratedEvidenceAnswer):
            raise TypeError("selected-school graph returned an invalid answer type")
        if any(item.school_id != request.school_id for item in evidence):
            raise ValueError("retrieved evidence does not match the authoritative school")
        if evidence and not answer.evidence_available:
            raise ValueError("generated answer rejected retrieved evidence")

        allowed = {item.citation.citation_id: item.citation for item in evidence}
        if any(citation_id not in allowed for citation_id in answer.citation_ids):
            raise ValueError("generated citation does not resolve to retrieved evidence")
        citations = tuple(allowed[citation_id] for citation_id in answer.citation_ids)
        return SelectedSchoolGraphResult(
            answer=answer.answer,
            citations=citations,
            answer_method="agent_grounded",
            tool_calls=state.get("tool_calls", 0),
            graph_iterations=state.get("graph_iterations", 0),
            termination_reason="completed",
        )
    except Exception as exc:
        return SelectedSchoolGraphResult(
            answer=deterministic_answer,
            citations=tuple(deterministic_citations),
            answer_method="deterministic_fallback",
            fallback_reason=_safe_fallback_reason(exc),
            tool_calls=state.get("tool_calls", 0),
            graph_iterations=state.get("graph_iterations", 0),
            termination_reason=state.get("termination_reason", "error"),
        )


def _safe_fallback_reason(exc: Exception) -> str:
    """Reduce arbitrary provider failures to a small non-sensitive vocabulary."""

    allowed = {
        "ValidationError",
        "TimeoutError",
        "RuntimeError",
        "ValueError",
        "TypeError",
        "ModelFactoryError",
    }
    name = type(exc).__name__
    return name if name in allowed else "AgentExecutionError"
