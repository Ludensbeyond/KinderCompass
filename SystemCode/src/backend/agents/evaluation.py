"""Privacy-safe evaluation helpers for the full-conversation supervisor."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import ConversationExecutionMetadata


class ExpectedProfileDelta(BaseModel):
    """Reviewed authoritative profile effects for one turn.

    Paths are dot-separated object keys. ``set`` assertions are intentionally
    partial so volatile explanatory metadata does not enter the fixture, while
    ``removed`` makes reset and pending-flow cleanup explicit.
    """

    model_config = ConfigDict(extra="forbid")

    set: dict[str, Any] = Field(default_factory=dict, max_length=20)
    removed: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("removed")
    @classmethod
    def removed_paths_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("removed profile paths must be unique")
        return value


class ConversationEvaluationCase(BaseModel):
    """One reviewed synthetic turn and its expected routing/tool behavior."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    sequence: int = Field(ge=1, le=500)
    conversation_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    turn: int = Field(ge=1, le=50)
    carry_profile: bool = False
    message: str = Field(min_length=2, max_length=500)
    profile: dict[str, Any] = Field(default_factory=dict)
    selected_school_ids: list[str] = Field(default_factory=list, max_length=20)
    eligible_school_ids: list[str] = Field(default_factory=list, max_length=100)
    excluded_school_ids: list[str] = Field(default_factory=list, max_length=100)
    family: dict[str, Any] | None = None
    home_postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    expected_intent: str = Field(min_length=1, max_length=80)
    expected_route_scope: Literal[
        "application_workflow", "structured_kindercompass",
        "general_knowledge", "combined", "clarification",
    ]
    expected_tool_names: list[str] = Field(default_factory=list, max_length=3)
    expected_citation_scopes: list[
        Literal["school", "general", "structured", "policy"]
    ] = Field(default_factory=list, max_length=4)
    expected_answer_terms: list[str] = Field(default_factory=list, max_length=8)
    maximum_answer_words: int = Field(default=120, ge=1, le=300)
    expect_agent_acceptance: bool = True
    acceptable_fallback: bool = False
    expected_profile_mutations: int = Field(default=0, ge=0, le=1)
    expected_profile_delta: ExpectedProfileDelta = Field(
        default_factory=ExpectedProfileDelta
    )
    expected_ready_to_search: bool = False
    expected_active_school_id: str | None = None
    adversarial_kind: Literal[
        "none", "school_id", "profile", "citation", "tool_arguments",
        "instructions", "provider_configuration",
    ] = "none"

    @field_validator("expected_tool_names", "expected_citation_scopes")
    @classmethod
    def values_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("expected values must be unique")
        return value


class ConversationEvaluationSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    cases: list[ConversationEvaluationCase] = Field(min_length=1, max_length=500)

    @field_validator("cases")
    @classmethod
    def cases_are_ordered_and_unique(
        cls, value: list[ConversationEvaluationCase],
    ) -> list[ConversationEvaluationCase]:
        if [case.sequence for case in value] != sorted(case.sequence for case in value):
            raise ValueError("evaluation cases must be ordered by sequence")
        if len({case.case_id for case in value}) != len(value):
            raise ValueError("evaluation case IDs must be unique")
        return value

    @model_validator(mode="after")
    def conversations_are_contiguous(self) -> "ConversationEvaluationSet":
        expected_sequence = list(range(1, len(self.cases) + 1))
        if [case.sequence for case in self.cases] != expected_sequence:
            raise ValueError("evaluation sequences must be contiguous from one")
        seen_closed: set[str] = set()
        active_id: str | None = None
        active_turn = 0
        for case in self.cases:
            if case.conversation_id != active_id:
                if case.conversation_id in seen_closed:
                    raise ValueError("conversation turns must be contiguous")
                if active_id is not None:
                    seen_closed.add(active_id)
                active_id = case.conversation_id
                active_turn = 0
            active_turn += 1
            if case.turn != active_turn:
                raise ValueError("conversation turns must be contiguous from one")
            if case.carry_profile != (case.turn > 1):
                raise ValueError("only continuation turns may carry a returned profile")
        return self


@dataclass(frozen=True)
class ConversationEvaluationRun:
    """Injected execution result; raw content is consumed but never reported."""

    deterministic_intent: str
    deterministic_response: dict[str, Any]
    agent_response: dict[str, Any]
    metadata: ConversationExecutionMetadata


EvaluationRunner = Callable[[ConversationEvaluationCase], ConversationEvaluationRun]


_FAILURE_CHECKS = {
    "routing": ("deterministic_intent_correct", "agent_route_correct"),
    "tool_selection": ("agent_tool_choice_correct",),
    "state_continuity": (
        "profile_state_matches", "authoritative_state_delta_correct",
        "readiness_correct", "active_school_identity_correct",
        "profile_mutation_count_correct",
    ),
    "grounding": (
        "citations_valid", "citation_scope_correct", "agent_response_useful",
    ),
    "validation": ("acceptance_expected",),
    "fallback": ("fallback_acceptable",),
}


def _citation_scopes(response: dict[str, Any]) -> list[str]:
    return sorted({
        str(item.get("evidence_scope"))
        for item in response.get("citations", [])
        if isinstance(item, dict) and item.get("evidence_scope")
    })


def _citations_valid(response: dict[str, Any]) -> bool:
    required = {"url", "title", "retrieved_at", "chunk_id", "evidence_scope"}
    return all(
        isinstance(item, dict)
        and required.issubset(item)
        and all(item.get(field) for field in required)
        for item in response.get("citations", [])
    )


def _useful(response: dict[str, Any], case: ConversationEvaluationCase) -> bool:
    answer = str(response.get("question") or "")
    folded = answer.casefold()
    return bool(answer.strip()) and len(answer.split()) <= case.maximum_answer_words and all(
        term.casefold() in folded for term in case.expected_answer_terms
    )


_MISSING = object()


def _profile_value(profile: dict[str, Any], path: str) -> Any:
    current: Any = profile
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _expected_state_matches(
    response: dict[str, Any], case: ConversationEvaluationCase,
) -> bool:
    profile = response.get("profile")
    if not isinstance(profile, dict):
        return False
    return all(
        _profile_value(profile, path) == expected
        for path, expected in case.expected_profile_delta.set.items()
    ) and all(
        _profile_value(profile, path) is _MISSING
        for path in case.expected_profile_delta.removed
    )


def evaluate_conversation_cases(
    evaluation_set: ConversationEvaluationSet,
    runner: EvaluationRunner,
) -> dict[str, Any]:
    """Compare both paths while returning no messages, answers, profiles, or facts."""

    results: list[dict[str, Any]] = []
    returned_profiles: dict[str, dict[str, Any]] = {}
    for case in evaluation_set.cases:
        effective_case = case
        if case.carry_profile:
            effective_case = case.model_copy(update={
                "profile": deepcopy(returned_profiles.get(case.conversation_id, case.profile)),
            })
        run = runner(effective_case)
        returned_profile = run.agent_response.get("profile")
        if isinstance(returned_profile, dict):
            returned_profiles[case.conversation_id] = deepcopy(returned_profile)
        agent_accepted = run.metadata.validation_succeeded
        citations_valid = _citations_valid(run.agent_response)
        deterministic_state_expected = _expected_state_matches(
            run.deterministic_response, case,
        )
        agent_state_expected = _expected_state_matches(run.agent_response, case)
        result = {
            "case_id": case.case_id,
            "deterministic_intent_correct": run.deterministic_intent == case.expected_intent,
            "agent_route_correct": run.metadata.route_scope == case.expected_route_scope,
            "agent_tool_choice_correct": (
                sorted(run.metadata.tool_names) == sorted(case.expected_tool_names)
            ),
            "profile_state_matches": (
                run.agent_response.get("profile") == run.deterministic_response.get("profile")
                and run.agent_response.get("ready_to_search")
                == run.deterministic_response.get("ready_to_search")
                and run.agent_response.get("understood")
                == run.deterministic_response.get("understood")
            ),
            "authoritative_state_delta_correct": (
                deterministic_state_expected and agent_state_expected
            ),
            "readiness_correct": (
                run.deterministic_response.get("ready_to_search")
                == case.expected_ready_to_search
                and run.agent_response.get("ready_to_search")
                == case.expected_ready_to_search
            ),
            "active_school_identity_correct": (
                case.expected_active_school_id is None
                or (
                    _profile_value(
                        run.deterministic_response.get("profile") or {},
                        "active_school.school_id",
                    ) == case.expected_active_school_id
                    and _profile_value(
                        run.agent_response.get("profile") or {},
                        "active_school.school_id",
                    ) == case.expected_active_school_id
                )
            ),
            "grounding_valid": (
                agent_accepted == case.expect_agent_acceptance and citations_valid
            ),
            "citations_valid": citations_valid,
            "citation_scope_correct": (
                _citation_scopes(run.agent_response)
                == sorted(case.expected_citation_scopes)
            ),
            "deterministic_response_useful": _useful(run.deterministic_response, case),
            "agent_response_useful": _useful(run.agent_response, case),
            "agent_accepted": agent_accepted,
            "acceptance_expected": agent_accepted == case.expect_agent_acceptance,
            "fallback_acceptable": (
                run.metadata.fallback_reason is None or case.acceptable_fallback
            ),
            "profile_mutation_count_correct": (
                run.metadata.profile_mutations == case.expected_profile_mutations
            ),
            "tool_names": list(run.metadata.tool_names),
            "tool_calls": run.metadata.tool_calls,
            "profile_mutations": run.metadata.profile_mutations,
            "graph_iterations": run.metadata.graph_iterations,
            "latency_ms": run.metadata.latency_ms,
            "termination_reason": run.metadata.termination_reason,
            "validation_succeeded": run.metadata.validation_succeeded,
            "fallback_reason": run.metadata.fallback_reason,
        }
        checks = {
            "deterministic_intent_correct", "agent_route_correct",
            "agent_tool_choice_correct", "profile_state_matches",
            "authoritative_state_delta_correct", "readiness_correct",
            "active_school_identity_correct", "profile_mutation_count_correct",
            "citations_valid", "citation_scope_correct",
            "agent_response_useful", "acceptance_expected", "fallback_acceptable",
        }
        result["passed"] = all(result[key] for key in checks)
        result["failure_categories"] = [
            category
            for category, category_checks in _FAILURE_CHECKS.items()
            if any(not result[key] for key in category_checks)
        ]
        results.append(result)

    total = len(results)

    def rate(key: str) -> float:
        return round(sum(bool(item[key]) for item in results) / total, 4)

    return {
        "schema_version": 2,
        "case_count": total,
        "passed": all(item["passed"] for item in results),
        "metrics": {
            "case_pass_rate": rate("passed"),
            "deterministic_intent_accuracy": rate("deterministic_intent_correct"),
            "agent_route_accuracy": rate("agent_route_correct"),
            "agent_tool_selection_accuracy": rate("agent_tool_choice_correct"),
            "profile_state_match_rate": rate("profile_state_matches"),
            "authoritative_state_delta_accuracy": rate(
                "authoritative_state_delta_correct"
            ),
            "readiness_accuracy": rate("readiness_correct"),
            "profile_mutation_accuracy": rate("profile_mutation_count_correct"),
            "grounding_validity_rate": rate("grounding_valid"),
            "citation_validity_rate": rate("citations_valid"),
            "deterministic_response_usefulness_rate": rate(
                "deterministic_response_useful"
            ),
            "response_usefulness_rate": rate("agent_response_useful"),
            "agent_acceptance_rate": rate("agent_accepted"),
            "agent_fallback_rate": round(
                sum(item["fallback_reason"] is not None for item in results) / total, 4,
            ),
            "unexpected_agent_fallback_rate": round(
                sum(
                    item["fallback_reason"] is not None
                    and not item["fallback_acceptable"]
                    for item in results
                ) / total,
                4,
            ),
        },
        "results": results,
    }
