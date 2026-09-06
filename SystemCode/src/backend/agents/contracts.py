"""Framework-independent contracts for bounded conversation agents."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]*$",
    ),
]
BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000),
]
QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=500),
]
SchoolName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]
TitleText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
AnswerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=800),
]
ToolName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]*$",
    ),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class AgentContract(BaseModel):
    """Strict base for data passed across the selected-school agent boundary."""

    model_config = ConfigDict(extra="forbid")


class ConversationFamilyContext(AgentContract):
    """Validated family inputs copied into backend-only supervisor context."""

    dob: date
    admission_date: date
    gross_household_income: float = Field(ge=0)
    citizenship: Literal["SC", "SPR", "Others"] = "SC"
    programme_type: Literal[
        "full_day", "half_day", "flexi_care_1", "flexi_care_2", "flexi_care_3",
    ] = "full_day"
    working_hours_per_month: float = Field(default=56, ge=0)
    household_size: int = Field(default=1, ge=1)
    non_earning_dependants: int = Field(default=0, ge=0)
    special_approval: bool = False


class SelectedSchoolAgentRequest(AgentContract):
    """Authoritative school context and the parent's evidence question."""

    question: QuestionText
    school_id: Identifier
    school_name: SchoolName


class EvidenceCitation(AgentContract):
    """Public provenance for one retrieved school-specific passage."""

    citation_id: Identifier
    school_id: Identifier
    chunk_id: Identifier
    url: str = Field(min_length=9, max_length=2_048, pattern=r"^https://[^\s]+$")
    title: TitleText
    retrieved_at: datetime

    @model_validator(mode="after")
    def citation_identifies_chunk(self) -> "EvidenceCitation":
        if self.citation_id != self.chunk_id:
            raise ValueError("citation_id must match chunk_id")
        return self


class RetrievedEvidence(AgentContract):
    """A bounded retrieved passage with its school-specific citation."""

    school_id: Identifier
    chunk_id: Identifier
    text: BoundedText
    citation: EvidenceCitation

    @model_validator(mode="after")
    def citation_matches_evidence(self) -> "RetrievedEvidence":
        if self.citation.school_id != self.school_id:
            raise ValueError("citation school_id must match evidence school_id")
        if self.citation.chunk_id != self.chunk_id:
            raise ValueError("citation chunk_id must match evidence chunk_id")
        return self


class GeneratedEvidenceAnswer(AgentContract):
    """Bounded model output whose citation IDs must resolve after generation."""

    answer: AnswerText
    citation_ids: list[Identifier] = Field(default_factory=list, max_length=3)
    evidence_available: bool

    @model_validator(mode="after")
    def citations_match_availability(self) -> "GeneratedEvidenceAnswer":
        if len(set(self.citation_ids)) != len(self.citation_ids):
            raise ValueError("citation_ids must be unique")
        if self.evidence_available and not self.citation_ids:
            raise ValueError("evidence answers require at least one citation_id")
        if not self.evidence_available and self.citation_ids:
            raise ValueError("unavailable evidence cannot have citation_ids")
        return self


def _validate_bounded_json(value: Any, *, name: str) -> Any:
    """Reject oversized or non-JSON server context before it reaches a model."""

    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > 25_000 or depth > 12:
            raise ValueError(f"{name} exceeds the bounded context size")
        if item is None or isinstance(item, (bool, int, float)):
            return
        if isinstance(item, str):
            if len(item) > 5_000:
                raise ValueError(f"{name} contains text longer than 5000 characters")
            return
        if isinstance(item, dict):
            if len(item) > 2_000:
                raise ValueError(f"{name} contains too many fields")
            for key, child in item.items():
                if not isinstance(key, str) or not key or len(key) > 128:
                    raise ValueError(f"{name} contains an invalid field name")
                visit(child, depth + 1)
            return
        if isinstance(item, (list, tuple)):
            if len(item) > 2_000:
                raise ValueError(f"{name} contains too many items")
            for child in item:
                visit(child, depth + 1)
            return
        raise ValueError(f"{name} contains a non-JSON value")

    visit(value, 0)
    return value


class AuthoritativeSchoolContext(AgentContract):
    """One repository-resolved school record prepared for capability tools."""

    school_id: Identifier
    facts: dict[str, Any]

    @field_validator("facts")
    @classmethod
    def facts_are_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_json(value, name="school facts")
        if not isinstance(value.get("school_id"), str) or not value["school_id"]:
            raise ValueError("school facts require a school_id")
        return value

    @model_validator(mode="after")
    def facts_match_school(self) -> "AuthoritativeSchoolContext":
        if self.facts.get("school_id") != self.school_id:
            raise ValueError("school facts must match school_id")
        return self


class EvidenceIndexContext(AgentContract):
    """Server-loaded retrieval input; never accepted from an HTTP request."""

    scope: Literal["school", "general"]
    available: bool
    index: dict[str, Any] | None = None

    @field_validator("index")
    @classmethod
    def index_is_bounded(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None:
            _validate_bounded_json(value, name="evidence index")
        return value

    @model_validator(mode="after")
    def availability_matches_index(self) -> "EvidenceIndexContext":
        if self.available != (self.index is not None):
            raise ValueError("available must identify whether an index was loaded")
        return self


class ConversationRequestContext(AgentContract):
    """Complete authoritative, backend-built input for one conversation turn."""

    message: QuestionText
    profile: dict[str, Any] = Field(default_factory=dict)
    family: ConversationFamilyContext | None = None
    home_postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    selected_school_ids: list[Identifier] = Field(default_factory=list, max_length=50)
    eligible_school_ids: list[Identifier] = Field(default_factory=list, max_length=2_000)
    excluded_school_ids: list[Identifier] = Field(default_factory=list, max_length=2_000)
    selected_schools: list[AuthoritativeSchoolContext] = Field(default_factory=list, max_length=50)
    eligible_schools: list[AuthoritativeSchoolContext] = Field(default_factory=list, max_length=2_000)
    excluded_schools: list[AuthoritativeSchoolContext] = Field(default_factory=list, max_length=2_000)
    selected_school_evidence: EvidenceIndexContext
    general_knowledge_evidence: EvidenceIndexContext
    catalogue_version: ShortText

    @field_validator("profile")
    @classmethod
    def profile_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_bounded_json(value, name="profile")

    @model_validator(mode="after")
    def school_records_match_ids(self) -> "ConversationRequestContext":
        pairs = (
            (self.selected_school_ids, self.selected_schools, "selected"),
            (self.eligible_school_ids, self.eligible_schools, "eligible"),
            (self.excluded_school_ids, self.excluded_schools, "excluded"),
        )
        for identifiers, schools, label in pairs:
            if identifiers != [school.school_id for school in schools]:
                raise ValueError(f"{label} school records must match authoritative IDs")
        return self


class PreferenceStateToolRequest(AgentContract):
    """Arguments for tools bound to one server-built conversation turn.

    Preference state and the newest message are deliberately absent: the tool
    factory closes over the validated request context so a model cannot replace
    either value in a tool call.
    """

    use_authoritative_context: Literal[True] = True


class DecisionToolRequest(AgentContract):
    """Arguments for a fixed capability bound to authoritative turn context."""

    use_authoritative_context: Literal[True] = True


class StructuredSchoolFactsToolRequest(AgentContract):
    """Allowlisted fact operation over IDs already resolved in server context."""

    operation: Literal[
        "food", "programmes", "fees", "vacancy", "operating_hours",
        "transport", "contact", "location",
    ]
    school_ids: list[Identifier] = Field(default_factory=list, max_length=5)

    @field_validator("school_ids")
    @classmethod
    def school_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("school_ids must be unique")
        return value


class EvidenceSearchToolRequest(AgentContract):
    """A bounded user question for a server-scoped evidence search."""

    question: QuestionText


class RoutingDecision(AgentContract):
    """Typed intent and factual-source routing selected before tool execution."""

    scope: Literal[
        "application_workflow", "structured_kindercompass",
        "general_knowledge", "combined", "clarification",
    ]
    intent: Identifier
    confidence: float = Field(ge=0, le=1)
    clarification: ShortText | None = None

    @model_validator(mode="after")
    def clarification_matches_scope(self) -> "RoutingDecision":
        if self.scope == "clarification" and not self.clarification:
            raise ValueError("clarification scope requires a question")
        if self.scope != "clarification" and self.clarification:
            raise ValueError("only clarification scope may include a question")
        return self


class PublicCitation(AgentContract):
    """Resolvable citation metadata allowed to cross the public API boundary."""

    citation_id: Identifier
    evidence_scope: Literal["school", "general", "structured", "policy"]
    url: str = Field(min_length=9, max_length=2_048, pattern=r"^https://[^\s]+$")
    title: TitleText
    retrieved_at: datetime
    school_id: Identifier | None = None
    authority: ShortText | None = None

    @model_validator(mode="after")
    def school_scope_has_school(self) -> "PublicCitation":
        if self.evidence_scope == "school" and self.school_id is None:
            raise ValueError("school-scoped citations require a school_id")
        if self.evidence_scope in {"general", "policy"} and self.school_id is not None:
            raise ValueError("general and policy citations cannot identify a school")
        return self


class GeneralKnowledgeEvidence(AgentContract):
    """One typed passage returned by a replaceable general retrieval adapter."""

    chunk_id: Identifier
    text: BoundedText
    citation: PublicCitation

    @model_validator(mode="after")
    def citation_matches_passage(self) -> "GeneralKnowledgeEvidence":
        if self.citation.evidence_scope != "general":
            raise ValueError("general evidence requires a general-scoped citation")
        if self.citation.citation_id != self.chunk_id:
            raise ValueError("citation_id must match the general evidence chunk_id")
        return self


class CapabilityToolResult(AgentContract):
    """Authoritative tool output from which a public response can be assembled."""

    tool_name: ToolName
    mutates_profile: bool
    profile: dict[str, Any]
    understood: list[ShortText] = Field(default_factory=list, max_length=30)
    ready_to_search: bool
    answer_candidate: AnswerText
    grounding_facts: list[BoundedText] = Field(default_factory=list, max_length=30)
    citations: list[PublicCitation] = Field(default_factory=list, max_length=12)
    evidence_category: Literal[
        "authoritative_fact", "school_published_claim", "calculated_estimate",
        "parent_sentiment", "unknown",
    ] = "unknown"

    @field_validator("profile")
    @classmethod
    def result_profile_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_bounded_json(value, name="tool profile")


class GeneratedConversationAnswer(AgentContract):
    """The only wording and citation selection a model may generate."""

    answer: AnswerText
    citation_ids: list[Identifier] = Field(default_factory=list, max_length=12)

    @field_validator("citation_ids")
    @classmethod
    def citation_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("citation_ids must be unique")
        return value


class ConversationExecutionLimits(AgentContract):
    """Server-owned independent bounds for one supervisor turn."""

    max_tool_calls: int = Field(default=3, ge=1, le=3)
    max_profile_mutations: int = Field(default=1, ge=0, le=1)
    max_graph_iterations: int = Field(default=6, ge=1, le=8)


class ConversationExecutionMetadata(AgentContract):
    """Privacy-safe telemetry containing no conversation or evidence text."""

    mode: Literal["deterministic", "shadow", "agent"]
    route_scope: Literal[
        "application_workflow", "structured_kindercompass",
        "general_knowledge", "combined", "clarification",
    ] | None = None
    tool_names: list[ToolName] = Field(default_factory=list, max_length=3)
    tool_calls: int = Field(default=0, ge=0, le=3)
    profile_mutations: int = Field(default=0, ge=0, le=1)
    graph_iterations: int = Field(default=0, ge=0, le=8)
    latency_ms: int = Field(default=0, ge=0, le=300_000)
    validation_succeeded: bool = False
    termination_reason: Literal[
        "deterministic", "completed", "clarification", "tool_call_limit",
        "mutation_limit", "iteration_limit", "timeout", "validation_failed", "error",
    ]
    fallback_reason: Literal[
        "invalid_routing", "unknown_tool", "invalid_arguments", "missing_context",
        "conflicting_results", "multiple_mutations", "malformed_output",
        "unsupported_citation", "timeout", "execution_limit", "model_unavailable",
        "tool_error", "model_error", "validation_error",
    ] | None = None
