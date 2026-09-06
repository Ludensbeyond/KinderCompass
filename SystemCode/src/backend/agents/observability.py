"""Allowlisted runtime telemetry for full-conversation agent execution."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import ConversationExecutionMetadata, ToolName


LOGGER = logging.getLogger("kindercompass.conversation_agent")


class ConversationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    mode: Literal["shadow", "agent"]
    route_scope: Literal[
        "application_workflow", "structured_kindercompass",
        "general_knowledge", "combined", "clarification",
    ] | None = None
    tool_names: list[ToolName] = Field(max_length=3)
    tool_calls: int = Field(ge=0, le=3)
    profile_mutations: int = Field(ge=0, le=1)
    graph_iterations: int = Field(ge=0, le=8)
    latency_ms: int = Field(ge=0, le=300_000)
    termination_reason: Literal[
        "deterministic", "completed", "clarification", "tool_call_limit",
        "mutation_limit", "iteration_limit", "timeout", "validation_failed", "error",
    ]
    validation_succeeded: bool
    fallback_reason: Literal[
        "invalid_routing", "unknown_tool", "invalid_arguments", "missing_context",
        "conflicting_results", "multiple_mutations", "malformed_output",
        "unsupported_citation", "timeout", "execution_limit", "model_unavailable",
        "tool_error", "model_error", "validation_error",
    ] | None = None
    profile_state_matches: bool | None = None
    citations_match: bool | None = None
    readiness_matches: bool | None = None


def build_conversation_observation(
    metadata: ConversationExecutionMetadata,
    *,
    mode: Literal["shadow", "agent"],
    deterministic_response: dict | None = None,
    agent_response: dict | None = None,
) -> ConversationObservation:
    """Reduce execution and optional shadow comparison to safe scalars."""

    compared = deterministic_response is not None and agent_response is not None
    return ConversationObservation(
        mode=mode,
        route_scope=metadata.route_scope,
        tool_names=list(metadata.tool_names),
        tool_calls=metadata.tool_calls,
        profile_mutations=metadata.profile_mutations,
        graph_iterations=metadata.graph_iterations,
        latency_ms=metadata.latency_ms,
        termination_reason=metadata.termination_reason,
        validation_succeeded=metadata.validation_succeeded,
        fallback_reason=metadata.fallback_reason,
        profile_state_matches=(
            agent_response.get("profile") == deterministic_response.get("profile")
            if compared else None
        ),
        citations_match=(
            agent_response.get("citations", []) == deterministic_response.get("citations", [])
            if compared else None
        ),
        readiness_matches=(
            agent_response.get("ready_to_search")
            == deterministic_response.get("ready_to_search")
            if compared else None
        ),
    )


def emit_conversation_observation(observation: ConversationObservation) -> None:
    """Emit only the validated allowlist; never accept arbitrary log context."""

    LOGGER.info("conversation_agent_observation %s", observation.model_dump_json())
