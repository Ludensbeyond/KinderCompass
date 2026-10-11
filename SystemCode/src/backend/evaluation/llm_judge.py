"""Opt-in, evidence-grounded LLM judging for recommendation examples.

This module is intentionally separate from the production ranking and
eligibility pipeline. Judge outputs are evaluation observations only.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from statistics import fmean, median
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from SystemCode.src.backend.evaluation.recommendation_metrics import (
    quadratic_weighted_kappa,
)


RUBRIC_DIMENSIONS = (
    "preference_alignment",
    "evidence_grounding",
    "eligibility_safety",
    "explanation_quality",
    "ranking_justification",
    "uncertainty_handling",
    "overall_usefulness",
)

CriticalFailureCode = Literal[
    "required_preference_violation",
    "eligibility_misrepresentation",
    "unsupported_material_claim",
    "uncertainty_misrepresentation",
]


class DimensionRating(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applicable: bool = Field(strict=True)
    score: int | None = Field(ge=1, le=5, strict=True)
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def score_matches_applicability(self) -> "DimensionRating":
        if self.applicable and self.score is None:
            raise ValueError("an applicable rubric dimension requires a score")
        if not self.applicable and self.score is not None:
            raise ValueError("a non-applicable rubric dimension must have a null score")
        return self


class JudgeRatings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference_alignment: DimensionRating
    evidence_grounding: DimensionRating
    eligibility_safety: DimensionRating
    explanation_quality: DimensionRating
    ranking_justification: DimensionRating
    uncertainty_handling: DimensionRating
    overall_usefulness: DimensionRating


class UnsupportedFactualClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=500)
    evidence_comparison: str = Field(min_length=1, max_length=500)


class CriticalFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: CriticalFailureCode
    rationale: str = Field(min_length=1, max_length=500)


class RecommendationJudgeResult(BaseModel):
    """Validated judge response; rationales must be concise and evidence based."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    ratings: JudgeRatings
    unsupported_factual_claims: list[UnsupportedFactualClaim] = Field(max_length=30)
    critical_failures: list[CriticalFailure] = Field(max_length=20)
    overall_assessment: Literal["strong", "mixed", "poor"]
    overall_rationale: str = Field(min_length=1, max_length=700)
    requires_human_review: bool = Field(strict=True)

    @model_validator(mode="after")
    def critical_failures_require_review(self) -> "RecommendationJudgeResult":
        if self.critical_failures and not self.requires_human_review:
            raise ValueError("critical failures must require human review")
        return self


class PreferenceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute: str = Field(min_length=1, max_length=80)
    requested_value: str = Field(min_length=1, max_length=160)
    importance: Literal["required", "high_priority", "preferred", "nice_to_have"]
    school_value: str | None = Field(default=None, max_length=300)
    evidence_state: Literal["matched", "not_matched", "unknown"]


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,79}$")
    rank: int = Field(ge=1, le=100)
    eligible: bool | None
    match_score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    profile_confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    combined_score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    preference_evidence: list[PreferenceEvidence] = Field(max_length=30)
    supplied_school_evidence: list[str] = Field(default_factory=list, max_length=40)


class PreferenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=160)
    importance: Literal["required", "high_priority", "preferred", "nice_to_have"]


class RecommendationJudgeCase(BaseModel):
    """Minimal, non-identifying evidence packet for one judged recommendation."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    case_type: str = Field(min_length=1, max_length=80)
    family_details_available: bool = Field(strict=True)
    preference_statement: str | None = Field(default=None, max_length=500)
    family_preferences: list[PreferenceSummary] = Field(max_length=20)
    candidates: list[CandidateEvidence] = Field(min_length=1, max_length=20)
    ranked_school_ids: list[str] = Field(min_length=1, max_length=20)
    response: str = Field(min_length=1, max_length=3000)
    safety_expectations: list[str] = Field(default_factory=list, max_length=10)
    human_ratings: dict[str, int] = Field(default_factory=dict)

    @field_validator("human_ratings", mode="before")
    @classmethod
    def human_rating_values_are_strict_integers(cls, value: Any) -> Any:
        if not isinstance(value, dict) or any(
            type(score) is not int or not 1 <= score <= 5 for score in value.values()
        ):
            raise ValueError("human ratings must be integer scores from 1 to 5")
        return value

    @model_validator(mode="after")
    def ids_and_human_ratings_are_valid(self) -> "RecommendationJudgeCase":
        candidate_ids = [candidate.school_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate school IDs must be unique within a case")
        if len(self.ranked_school_ids) != len(set(self.ranked_school_ids)):
            raise ValueError("ranked school IDs must be unique within a case")
        if not set(self.ranked_school_ids).issubset(candidate_ids):
            raise ValueError("ranked school IDs must refer to supplied candidates")
        ranked_by_position = [
            candidate.school_id for candidate in sorted(self.candidates, key=lambda item: item.rank)
        ]
        if ranked_by_position != self.ranked_school_ids:
            raise ValueError("ranked school IDs must match candidate rank positions")
        unknown_dimensions = set(self.human_ratings) - set(RUBRIC_DIMENSIONS)
        if unknown_dimensions:
            raise ValueError("human ratings contain unknown rubric dimensions")
        if any(isinstance(score, bool) or not 1 <= score <= 5 for score in self.human_ratings.values()):
            raise ValueError("human ratings must use the 1..5 scale")
        return self


class RecommendationJudgeDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    dataset_version: str = Field(min_length=1, max_length=40)
    dataset_kind: Literal["synthetic_unreviewed", "human_reviewed"]
    description: str = Field(min_length=1, max_length=500)
    cases: list[RecommendationJudgeCase] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> "RecommendationJudgeDataset":
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case IDs must be unique in a dataset")
        if self.dataset_kind == "synthetic_unreviewed" and any(
            case.human_ratings for case in self.cases
        ):
            raise ValueError("synthetic unreviewed datasets cannot contain human ratings")
        if self.dataset_kind == "human_reviewed" and not any(
            case.human_ratings for case in self.cases
        ):
            raise ValueError("human-reviewed datasets must contain human ratings")
        return self


class JudgeDisabledError(RuntimeError):
    """Raised when the explicitly opt-in live judge is disabled."""


JUDGE_SYSTEM_PROMPT = """You are an evaluator of a preschool recommendation and its explanation.
Use only the supplied anonymized preference statement (when present), normalized preference summary, candidate evidence, ranking, and response. Do not use outside knowledge about schools. Do not infer that unknown evidence is a match or mismatch. A confirmed eligibility failure or unknown eligibility must never be described as eligible. Missing family details mean eligibility is unverified. A required preference mismatch is a critical failure; preferred and nice-to-have preferences are not hard constraints.

Rate each of these dimensions from 1 to 5 when applicable:
1 preference_alignment: 1 contradicts required preferences; 2 misses an important preference; 3 mixed/partially aligned; 4 aligns with minor omissions; 5 faithfully reflects values and importance.
2 evidence_grounding: 1 major fabricated claims; 2 several unsupported material claims; 3 mixed grounding; 4 supported with minor gaps; 5 every factual claim is traceable to supplied evidence. List unsupported factual claims and compare each with the supplied evidence.
3 eligibility_safety: 1 recommends a known-ineligible or unverified school as eligible; 2 materially blurs eligibility; 3 safe but unclear; 4 clear with minor ambiguity; 5 accurately distinguishes eligible, ineligible, unknown, and missing family details. This is a critical failure when false/unknown eligibility is presented as confirmed.
4 explanation_quality: 1 absent or confusing; 2 generic; 3 understandable but underspecified; 4 specific and clear; 5 concise, specific strengths and trade-offs tied to evidence.
5 ranking_justification: 1 contradicts the supplied ordering/evidence; 2 largely unsupported; 3 partly supported; 4 accurately explains the ordering; 5 compares alternatives using only relevant supplied evidence. Mark not applicable if there is no comparison to explain.
6 uncertainty_handling: 1 turns unknown into fact; 2 hides material gaps; 3 mentions uncertainty incompletely; 4 distinguishes most unknowns; 5 clearly separates confirmed matches, mismatches, and unknown evidence.
7 overall_usefulness: 1 unsafe or unusable; 2 weak; 3 partly useful; 4 useful with minor gaps; 5 clear, relevant, actionable, and appropriately cautious.

Critical failure codes are limited to: required_preference_violation (a stated required preference is violated by the recommendation), eligibility_misrepresentation (false/unknown/unverified presented as eligible), unsupported_material_claim (unsupported claim materially affects eligibility, cost, safety, or choice), uncertainty_misrepresentation (unknown evidence asserted as a match or mismatch). Do not mark minor unsupported wording as critical. Set requires_human_review for any critical failure, low confidence, ambiguity, or incomplete evidence. Give short evidence-based rationales, not private chain-of-thought. Return the exact input case_id."""


def recommendation_judge_enabled(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return source.get("OPENAI_RECOMMENDATION_JUDGE_ENABLED", "false").strip().casefold() in {
        "1", "true", "yes", "on",
    }


def _judge_input(case: RecommendationJudgeCase) -> dict[str, Any]:
    """Exclude reference labels and descriptive fixture metadata from the judge."""
    return case.model_dump(exclude={"human_ratings", "case_type", "safety_expectations"})


def call_openai_judge(
    case: RecommendationJudgeCase | Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
    client: Any | None = None,
) -> RecommendationJudgeResult:
    """Call the configured provider only after explicit opt-in; never store prompts."""
    source = os.environ if environ is None else environ
    if not recommendation_judge_enabled(source):
        raise JudgeDisabledError("Recommendation judge is disabled")
    parsed_case = case if isinstance(case, RecommendationJudgeCase) else RecommendationJudgeCase.model_validate(case)
    if client is None:
        from openai import OpenAI

        model = source.get(
            "OPENAI_RECOMMENDATION_JUDGE_MODEL",
            source.get("OPENAI_EXPLANATION_MODEL", "gpt-4o-mini"),
        ).strip() or "gpt-4o-mini"
        try:
            timeout = float(source.get(
                "OPENAI_RECOMMENDATION_JUDGE_TIMEOUT_SECONDS",
                source.get("OPENAI_EXPLANATION_TIMEOUT_SECONDS", "8"),
            ))
        except (TypeError, ValueError):
            raise ValueError("Invalid recommendation judge timeout") from None
        if not 1 <= timeout <= 30:
            raise ValueError("Recommendation judge timeout must be between 1 and 30 seconds")
        client = OpenAI(timeout=timeout)
    else:
        model = source.get(
            "OPENAI_RECOMMENDATION_JUDGE_MODEL",
            source.get("OPENAI_EXPLANATION_MODEL", "gpt-4o-mini"),
        ).strip() or "gpt-4o-mini"

    response = client.responses.parse(
        model=model,
        instructions=JUDGE_SYSTEM_PROMPT,
        input=json.dumps(_judge_input(parsed_case), ensure_ascii=False),
        text_format=RecommendationJudgeResult,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("Judge provider returned no structured result")
    result = RecommendationJudgeResult.model_validate(response.output_parsed)
    if result.case_id != parsed_case.case_id:
        raise ValueError("Judge provider returned a mismatched case ID")
    return result


JudgeFunction = Callable[[Mapping[str, Any]], RecommendationJudgeResult | Mapping[str, Any]]


def evaluate_recommendation_judge(
    dataset: RecommendationJudgeDataset | Mapping[str, Any],
    judge: JudgeFunction,
    *,
    repeats: int = 2,
    mode: Literal["injected", "live"] = "injected",
) -> dict[str, Any]:
    """Run an injected judge repeatedly and aggregate valid observations only."""
    if repeats < 1 or repeats > 10:
        raise ValueError("repeats must be between 1 and 10")
    parsed_dataset = (
        dataset if isinstance(dataset, RecommendationJudgeDataset)
        else RecommendationJudgeDataset.model_validate(dataset)
    )
    if mode == "live" and not recommendation_judge_enabled():
        raise JudgeDisabledError("Live recommendation judging is disabled")
    case_reports: list[dict[str, Any]] = []
    all_valid_results: list[tuple[RecommendationJudgeCase, RecommendationJudgeResult]] = []
    invalid_count = 0

    for case in parsed_dataset.cases:
        run_reports = []
        case_valid: list[RecommendationJudgeResult] = []
        for run_number in range(1, repeats + 1):
            try:
                raw_result = judge(_judge_input(case))
                result = RecommendationJudgeResult.model_validate(raw_result)
                if result.case_id != case.case_id:
                    raise ValueError("Judge result case ID does not match input case")
            except Exception as exc:
                invalid_count += 1
                run_reports.append({
                    "run": run_number,
                    "status": "invalid_or_failed",
                    "error_type": type(exc).__name__,
                })
                continue
            case_valid.append(result)
            all_valid_results.append((case, result))
            run_reports.append({
                "run": run_number,
                "status": "valid",
                "result": result.model_dump(mode="json"),
            })

        repeated_signatures = [
            (tuple(
                getattr(result.ratings, dimension).score
                for dimension in RUBRIC_DIMENSIONS
            ), tuple(sorted(failure.code for failure in result.critical_failures)))
            for result in case_valid
        ]
        consistency = None
        if len(repeated_signatures) >= 2:
            consistency = sum(
                left == right
                for index, left in enumerate(repeated_signatures)
                for right in repeated_signatures[index + 1:]
            ) / (len(repeated_signatures) * (len(repeated_signatures) - 1) / 2)
        case_reports.append({
            "case_id": case.case_id,
            "runs": run_reports,
            "valid_runs": len(case_valid),
            "repeat_rating_and_critical_failure_agreement": consistency,
            "critical_failure_count": sum(len(result.critical_failures) for result in case_valid),
            "requires_human_review": (
                len(case_valid) < repeats
                or any(result.requires_human_review for result in case_valid)
            ),
        })

    dimension_summary = {}
    human_agreement = {}
    for dimension in RUBRIC_DIMENSIONS:
        scores = [
            rating.score
            for _, result in all_valid_results
            if (rating := getattr(result.ratings, dimension)).applicable
        ]
        dimension_summary[dimension] = {
            "mean_score": round(fmean(scores), 3) if scores else None,
            "rated_observations": len(scores),
        }
        paired = []
        for case in parsed_dataset.cases:
            case_scores = [
                getattr(result.ratings, dimension).score
                for result_case, result in all_valid_results
                if result_case.case_id == case.case_id
                and getattr(result.ratings, dimension).applicable
            ]
            if dimension in case.human_ratings and case_scores:
                paired.append((case.human_ratings[dimension], int(round(median(case_scores)))))
        human_agreement[dimension] = {
            "quadratic_weighted_kappa": quadratic_weighted_kappa(
                [item[0] for item in paired], [item[1] for item in paired],
            ) if paired else None,
            "paired_ratings": len(paired),
        }

    return {
        "dataset_id": parsed_dataset.dataset_id,
        "dataset_version": parsed_dataset.dataset_version,
        "dataset_kind": parsed_dataset.dataset_kind,
        "judge_mode": mode,
        "evaluation_status": "preliminary_judge_evaluation" if all_valid_results else "no_valid_judge_results",
        "cases": case_reports,
        "summary": {
            "case_count": len(parsed_dataset.cases),
            "requested_runs": len(parsed_dataset.cases) * repeats,
            "valid_runs": len(all_valid_results),
            "invalid_or_failed_runs": invalid_count,
            "critical_failure_count": sum(len(result.critical_failures) for _, result in all_valid_results),
            "cases_requiring_human_review": sum(item["requires_human_review"] for item in case_reports),
            "dimension_scores": dimension_summary,
            "human_agreement": human_agreement,
            "human_labels_present": any(case.human_ratings for case in parsed_dataset.cases),
        },
        "limitations": [
            "LLM ratings are preliminary and are not ground truth.",
            "Synthetic or unreviewed examples provide no product-performance evidence.",
            "Critical eligibility and hard-constraint policy remains deterministic in production.",
        ],
    }
