"""Preflight validation for manually maintained recommendation benchmarks.

This validates structure and provenance metadata only. It cannot independently
verify that a reviewer, source, or label is truthful.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping
from typing import Any


BENCHMARK_KIND = "manual_label_benchmark"
SYNTHETIC_KIND = "synthetic_test_fixture"
SPLITS = {"development", "held_out_test"}
LABEL_TYPES = {
    "relevance", "reference_order", "hard_constraint_outcomes", "eligibility",
    "hard_constraint_check", "eligibility_fee_claims", "explanation_claims",
    "human_judge_ratings",
}


def _fail(path: str, message: str) -> None:
    raise ValueError(f"benchmark {path}: {message}")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_benchmark(dataset: dict[str, Any]) -> dict[str, Any]:
    """Validate benchmark structure and return it unchanged for the existing runner."""
    if not isinstance(dataset, dict):
        _fail("$", "expected a JSON object")
    required = ("schema_version", "benchmark_id", "benchmark_version", "dataset_kind", "split", "ranking_cases", "label_provenance")
    for field in required:
        if field not in dataset:
            _fail(field, "is required")
    if isinstance(dataset["schema_version"], bool) or dataset["schema_version"] != 1:
        _fail("schema_version", "must be 1")
    if not _text(dataset["benchmark_id"]):
        _fail("benchmark_id", "must be a non-empty string")
    if not _text(dataset["benchmark_version"]):
        _fail("benchmark_version", "must be a non-empty string")
    synthetic = dataset["dataset_kind"] == SYNTHETIC_KIND
    if dataset["dataset_kind"] not in {BENCHMARK_KIND, SYNTHETIC_KIND}:
        _fail("dataset_kind", f"must be {BENCHMARK_KIND!r} or {SYNTHETIC_KIND!r}")
    if not isinstance(dataset["split"], str) or dataset["split"] not in SPLITS:
        _fail("split", "must be 'development' or 'held_out_test'")
    # A metadata claim never upgrades user-entered labels to independently audited evidence.
    allowed_statuses = {"illustrative_only"} if synthetic else {"not_reviewed", "reviewed_by_benchmark_reviewer"}
    if dataset.get("reference_label_status") not in allowed_statuses:
        _fail("reference_label_status", f"must be one of {sorted(allowed_statuses)}")
    if synthetic and not _text(dataset.get("synthetic_data_notice")):
        _fail("synthetic_data_notice", "must state that records and labels are synthetic and illustrative")
    cases = dataset["ranking_cases"]
    provenance = dataset["label_provenance"]
    if not isinstance(cases, list):
        _fail("ranking_cases", "must be a list")
    if not isinstance(provenance, list):
        _fail("label_provenance", "must be a list")

    case_by_id: dict[str, dict[str, Any]] = {}
    candidates: dict[str, set[str]] = {}
    labels_needed: set[tuple[str, str, str]] = set()
    for index, case in enumerate(cases):
        path = f"ranking_cases[{index}]"
        if not isinstance(case, dict):
            _fail(path, "must be an object")
        case_id = case.get("case_id")
        if not _text(case_id) or case_id in case_by_id:
            _fail(f"{path}.case_id", "must be a unique, non-empty string")
        if case.get("reference_case_id") != case_id:
            _fail(f"{path}.reference_case_id", "must equal case_id")
        if synthetic and case.get("synthetic") is not True:
            _fail(f"{path}.synthetic", "must be true for every synthetic case")
        if not isinstance(case.get("profile"), dict):
            _fail(f"{path}.profile", "must be the normalized KinderCompass profile object")
        profile = case["profile"]
        preferences = profile.get("preferences", {})
        if not isinstance(preferences, dict):
            _fail(f"{path}.profile.preferences", "must be an object keyed by normalized preference attribute")
        for attribute, preference in preferences.items():
            if not _text(attribute) or not isinstance(preference, dict) or "value" not in preference:
                _fail(f"{path}.profile.preferences.{attribute}", "must be an object with a value")
            weight = preference.get("weight", 3)
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
                _fail(f"{path}.profile.preferences.{attribute}.weight", "must be a finite number")
            if "desired" in preference and not isinstance(preference["desired"], bool):
                _fail(f"{path}.profile.preferences.{attribute}.desired", "must be true or false")
        preference_items = profile.get("preference_items", [])
        if not isinstance(preference_items, list):
            _fail(f"{path}.profile.preference_items", "must be a list")
        for item_index, item in enumerate(preference_items):
            item_path = f"{path}.profile.preference_items[{item_index}]"
            if not isinstance(item, dict) or not _text(item.get("attribute")) or "value" not in item:
                _fail(item_path, "must include attribute and value")
            importance = item.get("importance", "preferred")
            if not isinstance(importance, str) or importance not in {"required", "high_priority", "preferred", "nice_to_have"}:
                _fail(f"{item_path}.importance", "must be required, high_priority, preferred, or nice_to_have")
        if not isinstance(profile.get("hard_constraints", {}), dict):
            _fail(f"{path}.profile.hard_constraints", "must be an object")
        if not isinstance(case.get("schools"), list):
            _fail(f"{path}.schools", "must be a list of candidate school records")
        ids: list[str] = []
        for school_index, school in enumerate(case["schools"]):
            if not isinstance(school, dict):
                _fail(f"{path}.schools[{school_index}]", "must be an object")
            school_id = school.get("school_id", school.get("id"))
            if not _text(school_id):
                _fail(f"{path}.schools[{school_index}].school_id", "must be a non-empty string")
            if synthetic and (
                school.get("synthetic") is not True
                or not school_id.startswith("SYN-")
                or not str(school.get("name", "")).startswith("Synthetic ")
            ):
                _fail(f"{path}.schools[{school_index}]", "synthetic candidates must be marked and use synthetic IDs and names")
            ids.append(school_id)
        if len(set(ids)) != len(ids):
            _fail(f"{path}.schools", "school IDs must be unique")
        case_by_id[case_id] = case
        candidates[case_id] = set(ids)

        references = case.get("reference_ids")
        if references is not None:
            if not isinstance(references, list) or any(not _text(item) for item in references):
                _fail(f"{path}.reference_ids", "must be a list of non-empty school IDs")
            if len(set(references)) != len(references):
                _fail(f"{path}.reference_ids", "must not contain duplicate IDs")
            if not set(references).issubset(candidates[case_id]):
                _fail(f"{path}.reference_ids", "contains an ID absent from schools")
        if "labels_complete" in case and not isinstance(case["labels_complete"], bool):
            _fail(f"{path}.labels_complete", "must be true or false")
        if case.get("labels_complete") is True and references is None:
            _fail(f"{path}.reference_ids", "is required when labels_complete is true")
        relevance = case.get("relevance", {})
        if not isinstance(relevance, dict):
            _fail(f"{path}.relevance", "must map school IDs to integer grades")
        for school_id, grade in relevance.items():
            if school_id not in candidates[case_id] or isinstance(grade, bool) or not isinstance(grade, int) or grade not in range(4):
                _fail(f"{path}.relevance.{school_id}", "must label a candidate with an integer from 0 to 3")
            labels_needed.add((case_id, "relevance", school_id))
        if references is not None and case.get("labels_complete") is True and set(relevance) != set(references):
            _fail(f"{path}.relevance", "must label every reference_ids member when labels_complete is true")

        for field, allowed in (("hard_constraint_outcomes", {"pass", "fail", "unknown"}),
                               ("eligibility", {"eligible", "ineligible", "unknown"})):
            values = case.get(field, {})
            if not isinstance(values, dict):
                _fail(f"{path}.{field}", "must map candidate school IDs to labels")
            for school_id, value in values.items():
                if school_id not in candidates[case_id] or not isinstance(value, str) or value not in allowed:
                    _fail(f"{path}.{field}.{school_id}", f"must refer to a candidate and use one of {sorted(allowed)}")
                labels_needed.add((case_id, field, school_id))

        order = case.get("reference_order")
        if synthetic and order is not None:
            _fail(f"{path}.reference_order", "synthetic scenarios cannot claim an independently judged ranking")
        if order is not None:
            order_ids = list(order) if isinstance(order, dict) else order
            if not isinstance(order_ids, list) or any(not _text(item) for item in order_ids):
                _fail(f"{path}.reference_order", "must be an ordered list or school-to-rank mapping")
            if len(set(order_ids)) != len(order_ids) or not set(order_ids).issubset(candidates[case_id]):
                _fail(f"{path}.reference_order", "school IDs must be unique candidates")
            if isinstance(order, dict) and any(isinstance(rank, bool) or not isinstance(rank, (int, float)) or not math.isfinite(rank) for rank in order.values()):
                _fail(f"{path}.reference_order", "rank values must be numbers; equal values represent ties")
            labels_needed.update((case_id, "reference_order", school_id) for school_id in order_ids)

        checks = case.get("hard_constraint_checks", [])
        if not isinstance(checks, list):
            _fail(f"{path}.hard_constraint_checks", "must be a list")
        for check_index, check in enumerate(checks):
            check_path = f"{path}.hard_constraint_checks[{check_index}]"
            if not isinstance(check, dict) or not _text(check.get("constraint")):
                _fail(check_path, "must name a constraint")
            check_ids, excluded, outcomes = check.get("candidate_ids"), check.get("excluded_ids"), check.get("outcomes")
            if not isinstance(check_ids, list) or any(not _text(item) for item in check_ids) or not set(check_ids).issubset(candidates[case_id]):
                _fail(f"{check_path}.candidate_ids", "must contain candidate school IDs")
            if not isinstance(excluded, list) or any(not _text(item) for item in excluded) or not set(excluded).issubset(set(check_ids)):
                _fail(f"{check_path}.excluded_ids", "must be a subset of candidate_ids")
            if len(set(check_ids)) != len(check_ids) or len(set(excluded)) != len(excluded):
                _fail(check_path, "candidate_ids and excluded_ids must not contain duplicates")
            if not isinstance(outcomes, dict):
                _fail(f"{check_path}.outcomes", "must map IDs to pass, fail, or unknown")
            for school_id, outcome in outcomes.items():
                if school_id not in check_ids or not isinstance(outcome, str) or outcome not in {"pass", "fail", "unknown"}:
                    _fail(f"{check_path}.outcomes.{school_id}", "must label a check candidate as pass, fail, or unknown")
                labels_needed.add((case_id, "hard_constraint_check", f"{check['constraint']}:{school_id}"))

    # Claim/rating arrays use case_id to associate labels with a scenario.
    for field, label_type in (("eligibility_fee_claims", "eligibility_fee_claims"),
                              ("explanation_claims", "explanation_claims"),
                              ("human_judge_ratings", "human_judge_ratings")):
        records = dataset.get(field, [])
        if not isinstance(records, list):
            _fail(field, "must be a list")
        seen: set[str] = set()
        for index, item in enumerate(records):
            path = f"{field}[{index}]"
            if not isinstance(item, dict) or not _text(item.get("case_id")) or item.get("case_id") not in case_by_id:
                _fail(f"{path}.case_id", "must reference a ranking case")
            key_field = "claim_id" if "claim" in label_type else "dimension" if label_type == "human_judge_ratings" else "claim_id"
            key = item.get(key_field)
            if not _text(key):
                _fail(f"{path}.{key_field}", "must be a non-empty stable identifier")
            unique = f"{item['case_id']}:{label_type}:{key}"
            if unique in seen:
                _fail(path, f"duplicate {key_field} for this case")
            seen.add(unique)
            if label_type == "eligibility_fee_claims":
                if item.get("verified") is not True and item.get("verified") is not False:
                    _fail(f"{path}.verified", "must be true or false; use false for unverified claims")
                if item.get("verified") is True and ("expected" not in item or "predicted" not in item):
                    _fail(path, "verified claims require predicted and expected values")
                claim_reference = item.get("reference")
                if item.get("verified") is True and not (isinstance(claim_reference, dict) and _text(claim_reference.get("source")) and _text(claim_reference.get("reference"))):
                    _fail(f"{path}.reference", "verified factual claims require source and stable reference")
                if not _text(item.get("school_id")) or item["school_id"] not in candidates[item["case_id"]]:
                    _fail(f"{path}.school_id", "must identify a candidate school in the case")
            elif label_type == "explanation_claims":
                if item.get("status") not in {"supported", "contradicted", "unsupported", "unverifiable"}:
                    _fail(f"{path}.status", "must be supported, contradicted, unsupported, or unverifiable")
                if not _text(item.get("claim")):
                    _fail(f"{path}.claim", "must contain the manually segmented atomic claim")
                if not isinstance(item.get("evidence_available"), bool):
                    _fail(f"{path}.evidence_available", "must be true or false")
                if item["evidence_available"]:
                    evidence = item.get("evidence")
                    if not isinstance(evidence, dict) or not _text(evidence.get("source")) or not _text(evidence.get("reference")):
                        _fail(f"{path}.evidence", "available evidence requires source and stable reference")
            else:
                if isinstance(item.get("human"), bool) or not isinstance(item.get("human"), int) or item.get("human") not in range(1, 6):
                    _fail(f"{path}.human", "must be an integer from 1 to 5")
                if isinstance(item.get("llm_judge"), bool) or not isinstance(item.get("llm_judge"), int) or item.get("llm_judge") not in range(1, 6):
                    _fail(f"{path}.llm_judge", "must be an integer from 1 to 5")
            if label_type != "eligibility_fee_claims" or item.get("verified") is True:
                labels_needed.add((item["case_id"], label_type, key))

    not_applicable = dataset.get("not_applicable_labels", [])
    if not isinstance(not_applicable, list):
        _fail("not_applicable_labels", "must be a list")
    not_applicable_keys: set[tuple[str, str, str]] = set()
    for index, item in enumerate(not_applicable):
        path = f"not_applicable_labels[{index}]"
        if not isinstance(item, dict):
            _fail(path, "must be an object")
        case_id, label_type, label_key = item.get("case_id"), item.get("label_type"), item.get("label_key")
        if not _text(case_id) or case_id not in case_by_id or not isinstance(label_type, str) or label_type not in LABEL_TYPES or not _text(label_key):
            _fail(path, "requires a known case_id, supported label_type, and non-empty label_key")
        key = (case_id, label_type, label_key)
        if key in labels_needed or key in not_applicable_keys:
            _fail(path, "cannot duplicate a populated or not-applicable label")
        not_applicable_keys.add(key)
        if label_type in {"relevance", "reference_order", "hard_constraint_outcomes", "eligibility"} and label_key not in candidates[case_id]:
            _fail(f"{path}.label_key", "must identify a candidate school in the case")
        if label_type == "hard_constraint_check":
            constraint, separator, school_id = label_key.partition(":")
            if not separator or not _text(constraint) or school_id not in candidates[case_id]:
                _fail(f"{path}.label_key", "must use <constraint>:<candidate-school-id>")
        if not _text(item.get("reason")) or not _text(item.get("reviewer")):
            _fail(path, "requires a reason and reviewer")
        decided_at = item.get("decided_at")
        try:
            if not _text(decided_at) or dt.date.fromisoformat(decided_at).isoformat() != decided_at:
                raise ValueError
        except ValueError:
            _fail(f"{path}.decided_at", "must be a valid ISO date in YYYY-MM-DD form")

    if synthetic:
        if dataset.get("reference_order") is not None:
            _fail("reference_order", "synthetic scenarios cannot claim an independently judged ranking")
        for field in ("eligibility_fee_claims", "explanation_claims", "human_judge_ratings", "confidence_cases", "not_applicable_labels"):
            if dataset.get(field):
                _fail(field, "must be empty for synthetic illustrative benchmark data")
        if dataset.get("label_provenance"):
            _fail("label_provenance", "synthetic illustrative labels must not claim source or verification provenance")

    supplied: set[tuple[str, str, str]] = set()
    for index, item in enumerate(provenance):
        path = f"label_provenance[{index}]"
        if not isinstance(item, dict):
            _fail(path, "must be an object")
        case_id, label_type, label_key = item.get("case_id"), item.get("label_type"), item.get("label_key")
        if not _text(case_id) or case_id not in case_by_id or not isinstance(label_type, str) or label_type not in LABEL_TYPES or not _text(label_key):
            _fail(path, "requires a known case_id, supported label_type, and non-empty label_key")
        key = (case_id, label_type, label_key)
        if key in supplied:
            _fail(path, "duplicates provenance for a label")
        supplied.add(key)
        if synthetic:
            _fail("label_provenance", "synthetic illustrative labels must not claim source or verification provenance")
        if not _text(item.get("source")) or not _text(item.get("reference")):
            _fail(path, "requires source and stable reference/URL")
        date_value = item.get("verified_at")
        if not _text(date_value):
            _fail(f"{path}.verified_at", "is required as an ISO date (YYYY-MM-DD)")
        try:
            if dt.date.fromisoformat(date_value).isoformat() != date_value:
                raise ValueError
        except ValueError:
            _fail(f"{path}.verified_at", "must be a valid ISO date in YYYY-MM-DD form")
        if not _text(item.get("reviewer")):
            _fail(f"{path}.reviewer", "must identify the reviewer or role")
    if synthetic:
        return dataset

    missing = sorted(labels_needed - supplied)
    if missing:
        case_id, label_type, label_key = missing[0]
        _fail("label_provenance", f"missing source/date/reviewer record for {case_id}/{label_type}/{label_key}")
    extra = supplied - labels_needed
    if extra:
        case_id, label_type, label_key = sorted(extra)[0]
        _fail("label_provenance", f"references no populated label: {case_id}/{label_type}/{label_key}")

    if dataset.get("human_judge_ratings"):
        config = dataset.get("judge_configuration")
        if not isinstance(config, dict) or any(not config.get(key) for key in ("model", "prompt_version", "rubric_version", "settings")):
            _fail("judge_configuration", "paired human–LLM ratings require model, prompt_version, rubric_version, and settings")
    if dataset.get("hard_constraints"):
        _fail("hard_constraints", "benchmark labels must be attached to a ranking case under hard_constraint_outcomes or hard_constraint_checks")
    confidence_cases = dataset.get("confidence_cases", [])
    if not isinstance(confidence_cases, list):
        _fail("confidence_cases", "must be a list")
    for index, item in enumerate(confidence_cases):
        path = f"confidence_cases[{index}]"
        if not isinstance(item, dict):
            _fail(path, "must be an object")
        for field in ("known_weight", "total_weight", "reported_confidence"):
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                _fail(f"{path}.{field}", "must be a finite number")
        if item["total_weight"] < 0 or not 0 <= item["known_weight"] <= item["total_weight"]:
            _fail(path, "known_weight must be between zero and total_weight")
        if not 0 <= item["reported_confidence"] <= 1:
            _fail(f"{path}.reported_confidence", "must be between zero and one")
    return dataset

