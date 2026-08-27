"""Framework-independent contracts for selected-school evidence answers."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


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


class AgentContract(BaseModel):
    """Strict base for data passed across the selected-school agent boundary."""

    model_config = ConfigDict(extra="forbid")


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
