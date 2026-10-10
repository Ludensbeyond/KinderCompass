"""New-flow arguments and server results; legacy supervisor contracts stay intact."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from .contracts import AgentContract, Identifier, QuestionText, PublicCitation, ToolName, _validate_bounded_json
from ..pipeline.stage1.preference_schema import make_preference_item


class ToolArguments(AgentContract):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class PreferenceChoice(ToolArguments):
    attribute: str
    value: str | bool | float | int
    importance: Literal["required", "high_priority", "preferred", "nice_to_have"]
    desired: bool = True

    @model_validator(mode="after")
    def supported_choice(self):
        from ..pipeline.stage1.preference_schema import ALLOWED_VALUES
        allowed = ALLOWED_VALUES.get(self.attribute, set())
        if allowed and all(type(v) is bool for v in allowed) and type(self.value) is not bool:
            raise ValueError("boolean preferences require a boolean value")
        make_preference_item(self.attribute, self.value, self.importance)
        if self.attribute in {"care_level", "max_distance_km"} and (
            self.importance != "required" or not self.desired
        ):
            raise ValueError("care level and distance use positive required constraints")
        return self


class PreferencePatch(ToolArguments):
    set: list[PreferenceChoice] = Field(default_factory=list, max_length=15)
    remove: list[str] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def unique_supported_fields(self):
        from ..pipeline.stage1.preference_schema import ATTRIBUTE_CATALOG
        fields = [c.attribute for c in self.set] + self.remove
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("patch must contain unique attributes")
        if any(field not in ATTRIBUTE_CATALOG for field in fields):
            raise ValueError("unsupported preference attribute")
        return self


class ResetContinueArguments(ToolArguments):
    operation: Literal["reset", "resolve_strength", "resolve_contradiction", "resolve_relaxation"]
    choice: Literal["required", "preferred", "keep_existing", "use_incoming", "approve", "decline"] | None = None

    @model_validator(mode="after")
    def choice_matches_operation(self):
        allowed = {"reset": {None}, "resolve_strength": {"required", "preferred"},
                   "resolve_contradiction": {"keep_existing", "use_incoming"},
                   "resolve_relaxation": {"approve", "decline"}}
        if self.choice not in allowed[self.operation]:
            raise ValueError("choice does not match operation")
        return self


class SchoolIdsArguments(ToolArguments):
    school_ids: list[Identifier] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(self.school_ids) != len(set(self.school_ids)):
            raise ValueError("school IDs must be unique")
        return self


class SchoolFactsArguments(SchoolIdsArguments):
    operation: Literal["food", "programmes", "fees", "vacancy", "operating_hours", "transport", "contact", "location"]


class SchoolEvidenceArguments(SchoolIdsArguments):
    query: QuestionText


class GeneralGuidanceArguments(ToolArguments):
    query: QuestionText


class SearchArguments(ToolArguments):
    operation: Literal["search", "rank", "compare"] = "search"
    school_ids: list[Identifier] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def scope_is_valid(self):
        if len(self.school_ids) != len(set(self.school_ids)):
            raise ValueError("school IDs must be unique")
        if self.operation in {"rank", "compare"} and not self.school_ids:
            raise ValueError("rank and compare require school IDs")
        if self.operation == "compare" and len(self.school_ids) > self.limit:
            raise ValueError("compare limit must include every requested school")
        return self


class ScenarioOverrides(ToolArguments):
    gross_household_income: float | None = Field(default=None, ge=0)
    citizenship: Literal["SC", "SPR", "Others"] | None = None
    programme_type: Literal["full_day", "half_day", "flexi_care_1", "flexi_care_2", "flexi_care_3"] | None = None
    working_hours_per_month: float | None = Field(default=None, ge=0)
    household_size: int | None = Field(default=None, ge=1)
    non_earning_dependants: int | None = Field(default=None, ge=0)
    special_approval: bool | None = None

    @model_validator(mode="after")
    def no_explicit_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("scenario overrides cannot clear family inputs")
        return self


class CalculationArguments(SchoolIdsArguments):
    overrides: ScenarioOverrides = Field(default_factory=ScenarioOverrides)


class NearbyArguments(ToolArguments):
    postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    radius_km: float | None = Field(default=None, gt=0)
    limit: int = Field(default=10, ge=1, le=20)


class StructuredToolResult(AgentContract):
    """No answer candidate: facts, missing inputs and provenance only."""

    result_id: Identifier
    tool_name: ToolName
    status: Literal["ok", "needs_input", "no_evidence", "unavailable"]
    data: dict[str, Any] = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list, max_length=15)
    citations: list[PublicCitation] = Field(default_factory=list, max_length=15)
    catalogue_version: str
    state_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def bounded_result(self):
        import json
        if len({c.citation_id for c in self.citations}) != len(self.citations):
            raise ValueError("tool citations must have unique IDs")
        _validate_bounded_json(self.data, name="structured tool result")
        if len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False, allow_nan=False).encode("utf-8")) > 64000:
            raise ValueError("tool result exceeds 64000 bytes")
        return self
