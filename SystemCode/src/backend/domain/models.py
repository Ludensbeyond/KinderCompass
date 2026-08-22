from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from SystemCode.src.backend.domain.catalogue import EvaluatedSchool, ProgrammeOption


SchoolId = str
ProgrammeId = Literal[
    "full_day",
    "half_day_am",
    "half_day_pm",
    "flexi_care_1",
    "flexi_care_1_am",
    "flexi_care_1_pm",
    "flexi_care_2",
    "flexi_care_3",
]


class FamilyDetails(BaseModel):
    dob: dt.date
    admission_date: dt.date
    gross_household_income: float = Field(ge=0)
    citizenship: Literal["SC", "SPR", "Others"] = "SC"
    programme_type: Literal[
        "full_day", "half_day", "flexi_care_1", "flexi_care_2", "flexi_care_3"
    ] = "full_day"
    working_hours_per_month: float = Field(default=56, ge=0)
    household_size: int = Field(default=1, ge=1)
    non_earning_dependants: int = Field(default=0, ge=0)
    special_approval: bool = False


class SearchRequest(BaseModel):
    message: str | None = Field(default=None, min_length=2, max_length=500)
    profile: dict[str, Any] | None = None
    town: str | None = Field(default=None, max_length=30)
    within_1km: bool = False
    home_postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    radius_km: float | None = Field(default=None, gt=0)


class PreferenceRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    profile: dict[str, Any] | None = None
    selected_school_ids: list[SchoolId] = Field(default_factory=list)
    eligible_school_ids: list[SchoolId] = Field(default_factory=list)
    excluded_school_ids: list[SchoolId] = Field(default_factory=list)
    family: FamilyDetails | None = None
    home_postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class EvaluateRequest(BaseModel):
    school_ids: list[SchoolId] = Field(min_length=1)
    profile: dict[str, Any] = Field(default_factory=dict)
    family: FamilyDetails
    include_ineligible: bool = False
    trace_id: str | None = Field(default=None, max_length=36)


class ProgrammeEstimateRequest(BaseModel):
    family: FamilyDetails
    programme_id: ProgrammeId


class FeedbackRequest(BaseModel):
    trace_id: uuid.UUID
    anonymous_session_id: uuid.UUID
    school_id: SchoolId = Field(min_length=1)
    event_type: Literal["selected", "rejected", "contacted", "visited", "applied", "rated"]
    reason: Literal[
        "good_match", "fee", "distance", "programme", "evidence", "other"
    ] | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    consent: Literal[True]


class FeedbackResponse(BaseModel):
    event_id: uuid.UUID
    status: Literal["recorded"]


class RouteRequest(BaseModel):
    school_id: SchoolId = Field(min_length=1)
    home_postal_code: str = Field(pattern=r"^\d{6}$")


class GeocodeRequest(BaseModel):
    postal_code: str = Field(pattern=r"^\d{6}$")


class DistanceRequest(BaseModel):
    school_ids: list[SchoolId] = Field(min_length=1)
    home_postal_code: str = Field(pattern=r"^\d{6}$")


class HealthResponse(BaseModel):
    status: Literal["ok"]


class DistanceItem(BaseModel):
    school_id: SchoolId
    distance_km: float


class DistanceResponse(BaseModel):
    distances: list[DistanceItem]


class EvaluationResponse(BaseModel):
    eligible_count: int
    centres: list[EvaluatedSchool]
    trace: dict[str, Any]


class ProgrammeEstimateResponse(ProgrammeOption):
    school_id: SchoolId
    programme_id: ProgrammeId
    base_fee: float | None = None
    working_status: str | None = None


class SearchResponse(BaseModel):
    message: str
    centres: list[dict[str, Any]]
    profile: dict[str, Any]
    understood: list[str]
    trace: dict[str, Any]


class PreferenceResponse(BaseModel):
    profile: dict[str, Any]
    understood: list[str]
    ready_to_search: bool
    question: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    answer_method: str | None = None
    fallback_reason: str | None = None


class GeocodeResponse(BaseModel):
    name: str
    type: Literal["home"]
    latitude: float
    longitude: float


class RouteResponse(BaseModel):
    total_distance_km: float
    distance_method: str
    schedule: list[dict[str, Any]]
