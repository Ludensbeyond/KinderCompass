"""Explainable, evidence-aware Stage 1 preschool scoring."""

from __future__ import annotations

from typing import Any

from stage1.evidence import evidence_details


IMPORTANCE_MULTIPLIERS = {
    "required": 2.0,
    "high_priority": 1.5,
    "preferred": 1.0,
    "nice_to_have": 0.5,
}


def _languages(school):
    value = school.get("second_languages_offered") or ""
    return {item.strip().lower() for item in str(value).split("|") if item.strip()}


def _school_value(school: dict[str, Any], attribute: str, target: Any):
    if attribute == "pedagogy":
        value = school.get("pedagogy")
        if value in (None, "", "na", "General"):
            return (None, 0.0)
        return (value, 0.65)
    if attribute.startswith("language:"):
        languages = _languages(school)
        return (target.lower() in languages, 1.0 if languages else 0.0)
    if attribute == "spark_certified":
        value = school.get("spark_certified")
        return (str(value).lower() == "yes", 1.0 if value not in (None, "", "na") else 0.0)
    if attribute == "operator_scheme":
        value = school.get("operator_scheme")
        return (value, 1.0 if value not in (None, "", "na") else 0.0)
    if attribute == "transport":
        value = school.get("provision_of_transport")
        return (str(value).lower() == "yes", 1.0 if value not in (None, "", "na") else 0.0)
    if attribute == "food":
        value = str(school.get("food_offered") or "").lower()
        return ("halal" in value or "no pork" in value, 1.0 if value and value != "na" else 0.0)
    if attribute == "full_day":
        value = school.get("weekday_full_day")
        return (value not in (None, "", "na"), 1.0 if value is not None else 0.0)
    return (None, 0.0)


def _matches(actual, target, desired):
    if isinstance(actual, bool):
        match = actual == bool(target)
    else:
        match = str(actual).lower() == str(target).lower()
    return match if desired else not match


def score_school(profile: dict, school: dict[str, Any]) -> dict[str, Any]:
    breakdown = []
    strengths = []
    tradeoffs = []
    weighted_score = 0.0
    requested_weight = 0.0
    verifiable_weight = 0.0
    confidence_weight = 0.0
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
        actual, confidence = _school_value(school, attribute, target)
        match = _matches(actual, target, desired) if confidence else None
        compatibility = 1.0 if match else 0.0
        weighted_score += compatibility * weight
        requested_weight += weight
        if match is not None:
            verifiable_weight += weight
        confidence_weight += confidence * weight
        label = attribute.split(":", 1)[0].replace("_", " ")
        breakdown.append({
            "attribute": attribute,
            "preference": target,
            "school_value": actual,
            "matched": match,
            "status": "matched" if match is True else "not_matched" if match is False else "unknown",
            "importance": importance,
            "weight": round(weight, 2),
            "confidence": round(confidence, 2),
            "contribution": round(compatibility * weight, 2),
            "possible_contribution": round(weight, 2) if match is not None else 0.0,
            **evidence_details(attribute, school, actual, bool(confidence)),
        })
        if match is True:
            strengths.append(label)
        elif match is False:
            tradeoffs.append(label)

    score = 100.0 if not requested_weight else 0.0 if not verifiable_weight else weighted_score / verifiable_weight * 100.0
    profile_confidence = 1.0 if not requested_weight else confidence_weight / requested_weight
    return {
        **school,
        "match_score": round(score, 1),
        "profile_confidence": round(profile_confidence, 2),
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
    ranked.sort(key=lambda item: (item["match_score"], item["profile_confidence"], item.get("name") or ""), reverse=True)
    return ranked[:limit]
