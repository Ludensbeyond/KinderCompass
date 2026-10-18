"""LLM-assisted scenario generation over a frozen, read-only school snapshot.

The model proposes synthetic family preferences only. School facts always come
from Neo4j and the processed catalogue, and no model-proposed labels are treated
as evaluation ground truth.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SystemCode.src.backend.domain.catalogue import SchoolRecord
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.pipeline.stage1.preference_schema import (
    ATTRIBUTE_CATALOG, IMPORTANCE_VALUES, make_preference_item, sync_preference_schema,
)
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.pipeline.stage1.scorer import score_school


PROMPT_VERSION = "recommendation-benchmark-scenarios-v1"
NEO4J_SNAPSHOT_QUERY = """
MATCH (p:Preschool)
RETURN p.school_id AS school_id, p.name AS name, p.centre_code AS centre_code,
       p.tp_code AS tp_code, p.postal_code AS postal_code, p.base_fee AS base_fee,
       p.operator_scheme AS operator_scheme, p.care_levels AS care_levels,
       p.philosophy AS philosophy, p.pedagogy AS pedagogy,
       p.second_languages_offered AS second_languages_offered,
       p.spark_certified AS spark_certified, p.service_model AS service_model,
       p.food_offered AS food_offered, p.weekday_full_day AS weekday_full_day,
       p.provision_of_transport AS provision_of_transport,
       p.last_updated AS last_updated, p.longitude AS longitude, p.latitude AS latitude
ORDER BY school_id
"""
GRAPH_FIELDS = (
    "school_id", "name", "centre_code", "tp_code", "postal_code", "base_fee",
    "operator_scheme", "care_levels", "philosophy", "pedagogy",
    "second_languages_offered", "spark_certified", "service_model", "food_offered",
    "weekday_full_day", "provision_of_transport", "last_updated", "longitude", "latitude",
)
PROGRAMMES = ("full_day", "half_day", "flexi_care_1", "flexi_care_2", "flexi_care_3")


class PreferenceProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute: str
    value: str
    importance: str


class ScenarioProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str = Field(min_length=8, max_length=240)
    preference_items: list[PreferenceProposal] = Field(min_length=1, max_length=5)
    candidate_school_ids: list[str] = Field(min_length=2, max_length=8)
    dob: str
    admission_date: str
    gross_household_income: float = Field(ge=0)
    citizenship: str
    programme_type: str
    working_hours_per_month: float = Field(ge=0)
    household_size: int = Field(ge=1)
    non_earning_dependants: int = Field(ge=0)
    special_approval: bool


class ScenarioBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cases: list[ScenarioProposal] = Field(min_length=1, max_length=30)


def snapshot_school_records(neo4j_records: list[dict[str, Any]], catalogue_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine graph fields with detailed source catalogue fields by stable ID."""
    by_id = {str(row.get("school_id")): row for row in catalogue_records if row.get("school_id")}
    result = []
    seen = set()
    for graph in neo4j_records:
        school_id = graph.get("school_id")
        if not isinstance(school_id, str) or not school_id.strip() or school_id in seen:
            raise ValueError("Neo4j snapshot has missing or duplicate school IDs")
        seen.add(school_id)
        source = by_id.get(school_id)
        if source is None:
            raise ValueError(f"Neo4j school {school_id!r} is absent from processed catalogue")
        row = {key: graph.get(key) for key in GRAPH_FIELDS}
        # Preserve graph nulls. Extra detailed fields (services_menu and source
        # facts) are copied only when Neo4j does not own the property.
        for key, value in source.items():
            if key not in row:
                row[key] = value
        row["source_metadata"] = {
            "neo4j_last_updated": graph.get("last_updated"),
            "catalogue_last_updated": source.get("last_updated"),
            "catalogue_school_id": source.get("school_id"),
        }
        result.append(row)
    if not result:
        raise ValueError("Neo4j returned no Preschool records")
    return result


def _preference_profile(proposals: list[PreferenceProposal]) -> dict[str, Any]:
    hard: dict[str, Any] = {}
    preferences: dict[str, Any] = {}
    items = []
    for proposal in proposals:
        attr = proposal.attribute
        if attr not in {"care_level", "language", "spark_certified", "transport", "full_day", "operator_scheme", "food", "pedagogy"}:
            raise ValueError(f"Unsupported evaluation preference: {attr}")
        if proposal.importance not in IMPORTANCE_VALUES:
            raise ValueError(f"Unsupported preference importance: {proposal.importance}")
        value: Any = proposal.value
        if attr in {"spark_certified", "transport", "full_day"}:
            if proposal.value.casefold() not in {"true", "false"}:
                raise ValueError(f"{attr} must be true or false")
            value = proposal.value.casefold() == "true"
        elif attr == "max_distance_km":
            value = float(proposal.value)
        items.append(make_preference_item(attr, value, proposal.importance))
        if attr == "care_level":
            hard["level"] = value
        elif attr == "max_distance_km":
            hard["max_distance_km"] = value
        elif attr == "language" and proposal.importance == "required":
            hard["language"] = value
        else:
            key = f"language:{value}" if attr == "language" else attr
            weight = {"required": 5, "high_priority": 4, "preferred": 3, "nice_to_have": 1}[proposal.importance]
            preferences[key] = {"value": value, "weight": weight, "desired": True}
    return sync_preference_schema({"schema_version": 2, "hard_constraints": hard,
                                   "preferences": preferences, "preference_items": items})


def build_generated_dataset(
    proposals: ScenarioBatch | dict[str, Any], *, split: str, seed: int,
    school_snapshot: list[dict[str, Any]], snapshot_version: str,
    catalogue_version: str, policy_version: str, model: str,
    generation_settings: dict[str, Any],
) -> dict[str, Any]:
    """Validate proposals, freeze referenced facts, and calculate rule outputs."""
    if split not in {"development", "held_out_test"}:
        raise ValueError("split must be development or held_out_test")
    parsed = proposals if isinstance(proposals, ScenarioBatch) else ScenarioBatch.model_validate(proposals)
    by_id = {row["school_id"]: row for row in school_snapshot}
    identities: set[str] = set()
    cases = []
    for index, proposal in enumerate(parsed.cases, 1):
        profile = _preference_profile(proposal.preference_items)
        candidate_ids = proposal.candidate_school_ids
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Scenario contains duplicate candidate school IDs")
        if any(school_id not in by_id for school_id in candidate_ids):
            raise ValueError("Scenario references a school absent from the frozen snapshot")
        family = FamilyDetails.model_validate({
            "dob": proposal.dob, "admission_date": proposal.admission_date,
            "gross_household_income": proposal.gross_household_income,
            "citizenship": proposal.citizenship, "programme_type": proposal.programme_type,
            "working_hours_per_month": proposal.working_hours_per_month,
            "household_size": proposal.household_size,
            "non_earning_dependants": proposal.non_earning_dependants,
            "special_approval": proposal.special_approval,
        })
        schools = [by_id[school_id] for school_id in candidate_ids]
        # Hash the canonical scenario inputs, not a model-generated description.
        fingerprint = json.dumps({"profile": profile, "schools": candidate_ids,
                                  "family": family.model_dump(mode="json")}, sort_keys=True)
        identity = hashlib.sha256(fingerprint.encode()).hexdigest()
        if identity in identities:
            raise ValueError("Duplicate generated scenario detected")
        identities.add(identity)
        class SnapshotRepository:
            def get_many(self, school_ids: list[str]) -> list[SchoolRecord]:
                return [SchoolRecord.model_validate(by_id[school_id]) for school_id in school_ids]

        service = EvaluationService(SnapshotRepository())
        predictions = service.evaluate(candidate_ids, profile, family, include_ineligible=True)
        outcomes = {}
        for school in schools:
            labels = []
            hard = profile.get("hard_constraints", {})
            if hard.get("level"):
                levels = school.get("care_levels") or []
                labels.append("unknown" if not levels else "pass" if hard["level"] in levels else "fail")
            if hard.get("language"):
                raw = school.get("second_languages_offered")
                languages = {part.strip().casefold() for part in str(raw or "").split("|") if part.strip()}
                labels.append("unknown" if not languages else "pass" if hard["language"].casefold() in languages else "fail")
            breakdown = score_school(profile, school)["match_breakdown"]
            for item in profile.get("preference_items", []):
                if item.get("importance") != "required" or item.get("attribute") in {"care_level", "language", "max_distance_km"}:
                    continue
                key = item["attribute"]
                if key == "language":
                    key = f"language:{item['value']}"
                scored = next((entry for entry in breakdown if entry["attribute"] == key), None)
                labels.append("unknown" if scored is None or scored.get("matched") is None
                              else "pass" if scored["matched"] else "fail")
            outcomes[school["school_id"]] = (
                "fail" if "fail" in labels else "unknown" if "unknown" in labels or not labels else "pass"
            )
        stage2 = {item["school_id"]: {
            "eligible": item.get("eligible"), "status": item.get("status"),
            "eligible_level": item.get("eligible_level"),
            "programme_id": item.get("programme_id"),
            "fee_before_subsidy": item.get("fee_before_subsidy"),
            "net_monthly_fee": item.get("net_monthly_fee"),
            "reason": item.get("reason"),
        } for item in predictions}
        family_json = family.model_dump(mode="json")
        cases.append({
            "case_id": f"{split}-{index:02d}-{identity[:10]}",
            "reference_case_id": f"{split}-{index:02d}-{identity[:10]}",
            "scenario": proposal.scenario,
            "profile": profile,
            "family": family_json,
            "candidate_school_ids": candidate_ids,
            "schools": schools,
            "candidate_retrieval": {
                "status": "not_executed",
                "candidate_source": "LLM_proposed_subset_of_frozen_snapshot",
                "note": "No per-case Stage 1 Cypher replay; this artifact does not evaluate Neo4j query recall.",
            },
            "predicted": {
                "stage1_ranking": [item["school_id"] for item in predictions],
                "stage1_scores": {item["school_id"]: {
                    "match_score": item.get("match_score"),
                    "profile_confidence": item.get("profile_confidence"),
                    "combined_score": item.get("combined_score"),
                } for item in predictions},
                "hard_constraint_outcomes": outcomes,
                "stage2_eligibility_and_fee": stage2,
                "source": "production_EvaluationService_over_frozen_candidates",
            },
            "hard_constraint_outcomes": outcomes,
            "expected_outcome_status": "code_derived_for_required_preferences",
            "relevance": {},
            "labels_complete": False,
            "llm_proposed_labels": [],
            "label_status": "no_independent_relevance_labels",
            "scenario_fingerprint": identity,
        })
    return {
        "schema_version": 1,
        "benchmark_id": "kindercompass-real-snapshot-scenarios",
        "benchmark_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "dataset_kind": "generated_synthetic_scenarios",
        "split": split,
        "source_snapshot": {
            "snapshot_version": snapshot_version,
            "catalogue_version": catalogue_version,
            "policy_version": policy_version,
            "school_count": len(school_snapshot),
            "sha256": hashlib.sha256(json.dumps(school_snapshot, sort_keys=True, default=str).encode()).hexdigest(),
        },
        "generation": {"model": model, "prompt_version": PROMPT_VERSION,
                       "generated_at": datetime.now(timezone.utc).isoformat(),
                       "seed": seed, "settings": generation_settings,
                       "labels_note": "LLM proposes scenarios only; relevance is unlabelled; deterministic outputs are predictions, not independent ground truth."},
        "ranking_cases": cases,
        "label_provenance": [],
        "human_review_required": True,
    }


def prompt_for_generation(schools: list[dict[str, Any]], *, count: int, seed: int, avoid_descriptions: list[str] | None = None) -> str:
    """Prompt exposes facts and missingness but requests only scenarios/preferences."""
    rng = random.Random(seed)
    useful = [row for row in schools if any(row.get(key) not in (None, [], "") for key in
              ("care_levels", "second_languages_offered", "pedagogy", "operator_scheme", "spark_certified"))]
    rng.shuffle(useful)
    compact = [{"school_id": row["school_id"], **{key: row.get(key) for key in (
        "name", "care_levels", "second_languages_offered", "pedagogy", "operator_scheme",
        "spark_certified", "provision_of_transport", "weekday_full_day", "food_offered",
        "base_fee", "postal_code", "town", "last_updated")},
        "services_menu": [{key: service.get(key) for key in (
            "levels_offered", "type_of_service", "type_of_citizenship", "fees", "last_updated")}
            for service in (row.get("services_menu") or []) if isinstance(service, dict)]}
        for row in useful]
    return json.dumps({
        "task": f"Create exactly {count} distinct synthetic family scenarios.",
        "rules": ["Use only preference attributes and values from the supplied supported schema.",
                  "Choose candidate_school_ids only from supplied records.",
                  "Do not invent, repair, or describe school facts; null means unknown.",
                  "Vary required and optional preferences, trade-offs, unknown evidence, family age, programme and budget where applicable.",
                  "Do not generate expected rankings, eligibility labels, relevance labels, or claims about suitability.",
                  "Family details are invented test inputs, not real people."],
        "supported_preferences": {key: ATTRIBUTE_CATALOG[key] for key in (
            "care_level", "language", "spark_certified", "transport", "full_day",
            "operator_scheme", "food", "pedagogy")},
        "importance_values": sorted(IMPORTANCE_VALUES), "programme_values": PROGRAMMES,
        "seed": seed, "avoid_near_duplicate_scenarios": avoid_descriptions or [],
        "school_snapshot_records": compact,
    }, ensure_ascii=False)


def evaluate_frozen_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    """Replay production ranking and Stage 2 over a saved artifact, offline."""
    if dataset.get("dataset_kind") != "generated_synthetic_scenarios":
        raise ValueError("Expected a generated synthetic scenario artifact")
    reports = []
    for case in dataset.get("ranking_cases", []):
        schools = case.get("schools")
        candidate_ids = case.get("candidate_school_ids")
        if not isinstance(schools, list) or not isinstance(candidate_ids, list):
            raise ValueError("Each case needs frozen schools and candidate_school_ids")
        by_id = {school.get("school_id"): school for school in schools if isinstance(school, dict)}
        if len(by_id) != len(schools) or set(by_id) != set(candidate_ids):
            raise ValueError(f"{case.get('case_id')}: candidate IDs do not match frozen school records")
        profile = case.get("profile")
        family = FamilyDetails.model_validate(case.get("family"))

        class SnapshotRepository:
            def get_many(self, school_ids: list[str]) -> list[SchoolRecord]:
                return [SchoolRecord.model_validate(by_id[school_id]) for school_id in school_ids]

        evaluated = EvaluationService(SnapshotRepository()).evaluate(
            candidate_ids, profile, family, include_ineligible=True,
        )
        reports.append({
            "case_id": case["case_id"],
            "candidate_retrieval": "not_replayed",
            "ranking_ids": [item["school_id"] for item in evaluated],
            "results": [{
                "school_id": item["school_id"], "eligible": item.get("eligible"),
                "status": item.get("status"), "eligible_level": item.get("eligible_level"),
                "programme_id": item.get("programme_id"),
                "fee_before_subsidy": item.get("fee_before_subsidy"),
                "net_monthly_fee": item.get("net_monthly_fee"), "reason": item.get("reason"),
            } for item in evaluated],
            "independent_relevance_metrics": None,
            "label_status": case.get("label_status", "unknown"),
        })
    return {
        "benchmark_id": dataset.get("benchmark_id"),
        "benchmark_version": dataset.get("benchmark_version"),
        "split": dataset.get("split"),
        "source_snapshot": dataset.get("source_snapshot"),
        "evaluation_mode": "offline_frozen_candidates_production_EvaluationService",
        "retrieval_evaluated": False,
        "relevance_evaluated": False,
        "case_count": len(reports),
        "cases": reports,
    }
