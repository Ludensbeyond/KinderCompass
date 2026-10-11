"""Explainable, evidence-aware Stage 1 preschool scoring."""

from __future__ import annotations

import math
import re
from typing import Any

from stage1.evidence import evidence_details


IMPORTANCE_MULTIPLIERS = {
    "required": 2.0,
    "high_priority": 1.5,
    "preferred": 1.0,
    "nice_to_have": 0.5,
}

MISSING_VALUE_SENTINELS = {
    "", "na", "n/a", "none", "null", "unknown", "not available", "not applicable",
}


def _is_missing(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and value.strip().casefold() in MISSING_VALUE_SENTINELS
    )


def _yes_no(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if _is_missing(value):
        return None
    normalized = str(value).strip().casefold()
    if normalized in {"yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    return None


def _languages(school):
    value = school.get("second_languages_offered")
    if _is_missing(value):
        return set()
    return {
        item.strip().casefold()
        for item in str(value).split("|")
        if not _is_missing(item)
    }


def _school_value(school: dict[str, Any], attribute: str, target: Any):
    if attribute == "pedagogy":
        value = school.get("pedagogy")
        if _is_missing(value) or (isinstance(value, str) and value.strip().casefold() == "general"):
            return (None, 0.0)
        return (value, 0.65)
    if attribute.startswith("language:"):
        languages = _languages(school)
        return (target.casefold() in languages if languages else None, 1.0 if languages else 0.0)
    if attribute == "spark_certified":
        value = school.get("spark_certified")
        parsed = _yes_no(value)
        return (parsed, 1.0 if parsed is not None else 0.0)
    if attribute == "operator_scheme":
        value = school.get("operator_scheme")
        return (None if _is_missing(value) else value, 0.0 if _is_missing(value) else 1.0)
    if attribute == "transport":
        value = school.get("provision_of_transport")
        parsed = _yes_no(value)
        return (parsed, 1.0 if parsed is not None else 0.0)
    if attribute == "food":
        raw_value = school.get("food_offered")
        if _is_missing(raw_value):
            return (None, 0.0)
        value = str(raw_value).strip().casefold()
        return ("halal" in value or "no pork" in value, 1.0)
    if attribute == "full_day":
        value = school.get("weekday_full_day")
        parsed = _yes_no(value)
        if parsed is not None:
            return (parsed, 1.0)
        if _is_missing(value):
            return (None, 0.0)
        # This catalogue field records weekday full-day operating hours. Accept
        # a structured time range as evidence; arbitrary non-empty text is unknown.
        time_range = re.fullmatch(
            r"\s*(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\s*",
            str(value),
        )
        if time_range:
            start_hour, start_minute, end_hour, end_minute = map(int, time_range.groups())
            if (
                start_hour < 24 and end_hour < 24
                and start_minute < 60 and end_minute < 60
                and (end_hour, end_minute) > (start_hour, start_minute)
            ):
                return (True, 1.0)
        return (None, 0.0)
    return (None, 0.0)


def _matches(actual, target, desired):
    if isinstance(actual, bool):
        match = actual == bool(target)
    else:
        match = str(actual).strip().casefold() == str(target).strip().casefold()
    return match if desired else not match


def score_school(profile: dict, school: dict[str, Any]) -> dict[str, Any]:
    breakdown = []
    strengths = []
    tradeoffs = []
    weighted_score = 0.0
    requested_weight = 0.0
    verifiable_weight = 0.0
    known_weight = 0.0
    importance_by_attribute = {
        (f"language:{item['value']}" if item["attribute"] == "language" else item["attribute"]): item["importance"]
        for item in profile.get("preference_items", [])
    }

    for attribute, preference in profile.get("preferences", {}).items():
        target = preference["value"]
        desired = preference.get("desired", True)
        importance = importance_by_attribute.get(attribute, "preferred")
        base_weight = float(preference.get("weight", 3))
        weight = base_weight * IMPORTANCE_MULTIPLIERS[importance]
        actual, availability = _school_value(school, attribute, target)
        known = bool(availability)
        match = _matches(actual, target, desired) if known else None
        compatibility = 1.0 if match else 0.0
        if weight > 0:
            requested_weight += weight
            if known:
                known_weight += weight
                weighted_score += compatibility * weight
                verifiable_weight += weight
        label = attribute.split(":", 1)[0].replace("_", " ")
        breakdown.append({
            "attribute": attribute,
            "preference": target,
            "school_value": actual,
            "matched": match,
            "status": "matched" if match is True else "not_matched" if match is False else "unknown",
            "importance": importance,
            "weight": round(weight, 2),
            "confidence": 1.0 if known else 0.0,
            "contribution": round(compatibility * weight, 2),
            "possible_contribution": round(weight, 2) if match is not None else 0.0,
            **evidence_details(attribute, school, actual, known),
        })
        if match is True:
            strengths.append(label)
        elif match is False:
            tradeoffs.append(label)

    # Match retains the original semantics: unknown evidence is excluded from
    # its denominator. Confidence independently reports evidence completeness.
    # Unsupported and zero-weight preferences do not affect either score.
    score = (
        100.0 if not requested_weight
        else 0.0 if not verifiable_weight
        else weighted_score / verifiable_weight * 100.0
    )
    profile_confidence = 1.0 if not requested_weight else known_weight / requested_weight
    confidence_score = profile_confidence * 100.0
    combined_score = math.sqrt(score * confidence_score)
    return {
        **school,
        "match_score": round(score, 1),
        "profile_confidence": round(profile_confidence, 2),
        "combined_score": round(combined_score, 1),
        "strengths": strengths[:5],
        "tradeoffs": tradeoffs[:5],
        "match_breakdown": breakdown,
    }


def rank_schools(profile: dict, schools: list[dict[str, Any]], limit: int = 20):
    required = {
        (f"language:{item['value']}" if item["attribute"] == "language" else item["attribute"])
        for item in profile.get("preference_items", [])
        if item.get("importance") == "required"
    }
    ranked = []
    for school in schools:
        scored = score_school(profile, school)
        proven_failure = any(
            item["attribute"] in required and item["matched"] is False
            for item in scored["match_breakdown"]
        )
        if not proven_failure:
            ranked.append(scored)
    ranked.sort(
        key=lambda item: (
            -item["combined_score"],
            -item["match_score"],
            -item["profile_confidence"],
            str(item.get("school_id") or ""),
        )
    )
    return ranked[:limit]
