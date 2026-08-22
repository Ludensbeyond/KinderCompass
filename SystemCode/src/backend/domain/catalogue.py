from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MappingModel(BaseModel, Mapping[str, Any]):
    """Typed domain object that remains compatible with legacy mapping consumers."""

    model_config = ConfigDict(extra="allow")

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.model_dump())

    def __len__(self) -> int:
        return len(self.model_dump())

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class SchoolService(MappingModel):
    class_of_licence: str
    levels_offered: str
    type_of_service: str
    type_of_citizenship: Literal["SC", "SPR", "Others"]
    fees: float = Field(ge=0)
    last_updated: dt.date | None = None


class SchoolRecord(MappingModel):
    school_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    centre_code: str | None = None
    tp_code: str | None = None
    base_fee: float | None = Field(default=None, ge=0)
    care_levels: list[str] = Field(default_factory=list)
    services_menu: list[SchoolService] = Field(default_factory=list)
    pedagogy: str | None = None
    operator_scheme: str | None = None


class PolicyReference(MappingModel):
    policy_id: str
    authority: str
    effective_from: dt.date
    source_url: str


class ProgrammeOption(MappingModel):
    programme_id: str
    service_label: str
    programme: str | None = None
    status: str
    eligible: bool
    eligible_level: str | None = None
    fee_before_subsidy: float = Field(ge=0)
    net_monthly_fee: float = Field(ge=0)
    basic_subsidy: float | None = Field(default=None, ge=0)
    additional_subsidy: float | None = Field(default=None, ge=0)
    minimum_copayment: float | None = Field(default=None, ge=0)
    policy_source: PolicyReference | None = None
    warnings: list[str] = Field(default_factory=list)


class EvaluatedSchool(SchoolRecord):
    status: str
    eligible: bool
    eligible_level: str | None = None
    programme_id: str | None = None
    service_label: str | None = None
    fee_before_subsidy: float | None = Field(default=None, ge=0)
    net_monthly_fee: float | None = Field(default=None, ge=0)
    basic_subsidy: float | None = Field(default=None, ge=0)
    additional_subsidy: float | None = Field(default=None, ge=0)
    minimum_copayment: float | None = Field(default=None, ge=0)
    preferred_programme: str
    preferred_programme_available: bool
    programme_options: list[ProgrammeOption] = Field(default_factory=list)
    policy_source: PolicyReference | None = None
    warnings: list[str] = Field(default_factory=list)
