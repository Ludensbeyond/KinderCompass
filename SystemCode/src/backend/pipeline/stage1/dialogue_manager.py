"""Decision-aware selection of the next useful preschool preference question."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable, Mapping

from stage1.preference_schema import sync_preference_schema


QUESTION_ORDER = ("language", "pedagogy", "spark_certified", "transport", "food")
QUESTIONS = {
    "language": "Would a second language such as Chinese, Malay, or Tamil help narrow the options?",
    "pedagogy": "Would you like to narrow the options by teaching approach, such as Montessori, play-based, or Reggio Emilia?",
    "spark_certified": "Should SPARK certification be considered when ranking the schools?",
    "transport": "Would school transport help distinguish between the remaining options?",
    "food": "Do you need a food requirement such as halal food or no pork?",
}


def catalogue_facets(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    schools = list(records)
    total = len(schools)
    language_counts: Counter[str] = Counter()
    pedagogy_counts: Counter[str] = Counter()
    binary = {key: 0 for key in ("spark_certified", "transport", "food")}
    evidence = {key: 0 for key in (*binary, "language", "pedagogy")}
    for school in schools:
        languages = {
            item.strip() for item in str(school.get("second_languages_offered") or "").split("|")
            if item.strip()
        }
        if languages:
            evidence["language"] += 1
            language_counts.update(languages)
        pedagogy = str(school.get("pedagogy") or "").strip()
        if pedagogy and pedagogy.casefold() not in {"na", "general"}:
            evidence["pedagogy"] += 1
            pedagogy_counts[pedagogy] += 1
        spark = school.get("spark_certified")
        if spark not in (None, "", "na"):
            evidence["spark_certified"] += 1
            binary["spark_certified"] += int(str(spark).casefold() == "yes")
        transport = school.get("provision_of_transport")
        if transport not in (None, "", "na"):
            evidence["transport"] += 1
            binary["transport"] += int(str(transport).casefold() == "yes")
        food = str(school.get("food_offered") or "").casefold()
        if food and food != "na":
            evidence["food"] += 1
            binary["food"] += int("halal" in food or "no pork" in food)
    return {
        "total": total,
        "evidence": evidence,
        "positive": binary,
        "categories": {
            "language": dict(language_counts),
            "pedagogy": dict(pedagogy_counts),
        },
    }


def _requested(profile: Mapping[str, Any], attribute: str) -> bool:
    hard = profile.get("hard_constraints", {})
    preferences = profile.get("preferences", {})
    if attribute == "language":
        return bool(hard.get("language")) or any(
            str(key).startswith("language:") for key in preferences
        )
    return attribute in preferences


def _entropy_score(attribute: str, facets: Mapping[str, Any]) -> float:
    total = int(facets.get("total") or 0)
    evidence_count = int(facets.get("evidence", {}).get(attribute) or 0)
    if total <= 0 or evidence_count <= 0:
        return 0.0
    coverage = evidence_count / total
    if attribute in {"language", "pedagogy"}:
        counts = list(facets.get("categories", {}).get(attribute, {}).values())
        denominator = sum(counts)
        if denominator <= 0:
            return 0.0
        entropy = -sum(
            (count / denominator) * math.log2(count / denominator)
            for count in counts if count
        )
        normalized = entropy / math.log2(max(2, len(counts)))
        return coverage * normalized
    positive = int(facets.get("positive", {}).get(attribute) or 0)
    probability = min(1.0, positive / evidence_count)
    if probability in {0.0, 1.0}:
        return 0.0
    entropy = -probability * math.log2(probability) - (1 - probability) * math.log2(1 - probability)
    return coverage * entropy


def next_best_question(profile: Mapping[str, Any], facets: Mapping[str, Any] | None) -> tuple[str, str] | None:
    if not facets:
        return None
    candidates = [item for item in QUESTION_ORDER if not _requested(profile, item)]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda item: (-_entropy_score(item, facets), QUESTION_ORDER.index(item)),
    )
    attribute = ranked[0]
    if _entropy_score(attribute, facets) <= 0:
        return None
    return attribute, QUESTIONS[attribute]


def detect_contradiction(
    current: Mapping[str, Any], incoming: Mapping[str, Any], text: str
) -> dict[str, Any] | None:
    """Require a decision before replacing any supported saved preference."""
    current_hard = current.get("hard_constraints", {})
    incoming_hard = incoming.get("hard_constraints", {})
    current_prefs = current.get("preferences", {})
    incoming_prefs = incoming.get("preferences", {})

    def label(value: Any, desired: bool = True) -> str:
        rendered = "yes" if value is True else "no" if value is False else str(value)
        return rendered if desired else f"avoid {rendered}"

    candidates = []
    for key, new_value in incoming_hard.items():
        candidates.append(({"level": "care_level", "max_distance_km": "max_distance_km"}.get(key, key), key, new_value, True, True))
    for key, new_pref in incoming_prefs.items():
        attribute = "language" if key.startswith("language:") else key
        hard_key = {"care_level": "level"}.get(attribute, attribute)
        if hard_key in incoming_hard:
            continue
        candidates.append((attribute, key, new_pref.get("value"), new_pref.get("desired", True), False))

    for attribute, key, new_value, new_desired, incoming_is_hard in candidates:
        hard_key = {"care_level": "level"}.get(attribute, attribute)
        if hard_key in current_hard:
            old_value, old_desired, old_key, old_is_hard = current_hard[hard_key], True, hard_key, True
        else:
            old_key = next((candidate_key for candidate_key in current_prefs
                            if ("language" if candidate_key.startswith("language:") else candidate_key) == attribute), None)
            if old_key is None:
                continue
            old_pref = current_prefs[old_key]
            old_value, old_desired, old_is_hard = old_pref.get("value"), old_pref.get("desired", True), False
        if old_value == new_value and old_desired == new_desired:
            continue
        old_label, new_label = label(old_value, old_desired), label(new_value, new_desired)
        question = (
            f"You already require {old_label}, but this change says {new_label}. "
            f"Say ‘keep {old_label}’ or ‘use {new_label}’."
            if old_is_hard else
            f"Your current {attribute.replace('_', ' ')} preference is {old_label}, and this change says "
            f"{new_label}. Say ‘keep {old_label}’ or ‘use {new_label}’."
        )
        return {
            "attribute": attribute,
            "existing": old_value,
            "incoming": new_value,
            "existing_key": old_key,
            "incoming_key": key,
            "existing_hard": old_is_hard,
            "incoming_hard": incoming_is_hard,
            "existing_desired": old_desired,
            "incoming_desired": new_desired,
            "incoming_profile": dict(incoming),
            "incoming_preference": dict(incoming_prefs.get(key, {})),
            "existing_label": old_label,
            "incoming_label": new_label,
            "question": question,
        }
    return None


def resolve_contradiction(profile: dict[str, Any], text: str) -> tuple[dict[str, Any], bool]:
    pending = profile.get("pending_contradiction")
    if not pending:
        return profile, False
    lowered = text.casefold().strip()
    new_label = str(pending.get("incoming_label", pending["incoming"])).casefold()
    old_label = str(pending.get("existing_label", pending["existing"])).casefold()
    use_new = "use new" in lowered or ("use " in lowered and new_label in lowered)
    keep_old = "keep existing" in lowered or "keep current" in lowered or ("keep " in lowered and old_label in lowered)
    if not use_new and not keep_old:
        return profile, False
    updated = dict(profile)
    if use_new:
        attribute = pending["attribute"]
        hard_key = {"care_level": "level"}.get(attribute, attribute)
        updated.setdefault("hard_constraints", {}).pop(hard_key, None)
        for key in list(updated.setdefault("preferences", {})):
            if ("language" if key.startswith("language:") else key) == attribute:
                updated["preferences"].pop(key)
        updated["preference_items"] = [
            item for item in updated.get("preference_items", [])
            if item.get("attribute") != attribute
        ]
        updated["unsupported_preferences"] = [
            item for item in updated.get("unsupported_preferences", [])
            if item.get("attribute") != attribute
        ]
        incoming = pending.get("incoming_profile") or {}
        if hard_key in incoming.get("hard_constraints", {}):
            updated.setdefault("hard_constraints", {})[hard_key] = incoming["hard_constraints"][hard_key]
        for key, value in incoming.get("preferences", {}).items():
            if ("language" if key.startswith("language:") else key) == attribute:
                updated.setdefault("preferences", {})[key] = value
        for field in ("preference_items", "unsupported_preferences"):
            updated.setdefault(field, []).extend(
                item for item in incoming.get(field, []) if item.get("attribute") == attribute
            )
    updated.pop("pending_contradiction", None)
    updated["recognized"] = [f"resolved {pending['attribute']} contradiction"]
    return sync_preference_schema(updated), True


def propose_constraint_relaxation(
    profile: Mapping[str, Any], *, trace: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Propose only a supported change shown by Stage 1 diagnostics to help."""
    trace = trace or {}
    hard = profile.get("hard_constraints", {})
    distance = hard.get("max_distance_km")
    if distance is not None and trace.get("distance_outside_radius", 0) > 0:
        old_value = float(distance)
        nearest = trace.get("nearest_outside_distance_km")
        if nearest is None:
            return None
        new_value = max(old_value + 0.1, float(nearest) + 0.05)
        new_value = round(new_value, 1)
        return {
            "kind": "distance",
            "attribute": "max_distance_km",
            "old_value": old_value,
            "new_value": round(new_value, 1),
            "question": (
                f"No candidates were within {old_value:g} km. The nearest school with known coordinates "
                f"outside that limit is about {float(nearest):g} km away. Expand the limit to {new_value:g} km? "
                "Say ‘apply relaxation’ to approve it, or ‘keep constraints’ to decline."
            ),
        }
    relaxable = set(trace.get("individually_relaxable_required_preferences", []))
    required = next((
        item for item in profile.get("preference_items", [])
        if item.get("importance") == "required"
        and item.get("attribute") in relaxable
        and item.get("attribute") not in {"care_level", "max_distance_km"}
    ), None)
    if required:
        label = str(required["attribute"]).replace("_", " ")
        return {
            "kind": "downgrade_preference",
            "attribute": required["attribute"],
            "old_value": required["value"],
            "new_value": required["value"],
            "question": (
                f"No candidates remained when {label} was required. Relaxing this preference alone "
                "would return candidates. Change it to preferred? Say ‘apply relaxation’ to approve "
                "or ‘keep constraints’ to decline."
            ),
        }
    return None


def describe_empty_search(trace: Mapping[str, Any]) -> str:
    """Explain the observed Stage 1 empty path without guessing at hidden causes."""
    if trace.get("database_candidates_after_hard_constraints") == 0:
        return (
            "The catalogue returned no schools for the current care-level, language, and location filters. "
            "Missing catalogue information may also prevent a school from being checked."
        )
    if trace.get("after_distance_filter") == 0:
        if trace.get("distance_missing_coordinates", 0) and not trace.get("distance_outside_radius", 0):
            return "No nearby match could be confirmed because the remaining schools have no usable coordinates."
        if trace.get("distance_outside_radius", 0):
            return "Schools with known coordinates were outside the requested distance. Schools without coordinates remain unknown."
    if trace.get("after_required_preference_enforcement") == 0:
        return (
            "No candidates remained after the required-preference check. Unknown, inferred, or stale evidence "
            "is not treated as a confirmed mismatch."
        )
    return "No preschool candidates are available for the current search."


def resolve_constraint_relaxation(
    profile: dict[str, Any], text: str
) -> tuple[dict[str, Any], str | None]:
    pending = profile.get("pending_relaxation")
    if not pending:
        return profile, None
    lowered = text.casefold().strip()
    approved = lowered in {"yes", "approve", "apply", "apply relaxation"} or "apply relaxation" in lowered
    declined = lowered in {"no", "decline", "keep constraints", "do not apply"} or "keep constraints" in lowered
    if not approved and not declined:
        return profile, "pending"
    updated = dict(profile)
    updated.pop("pending_relaxation", None)
    if declined:
        return sync_preference_schema(updated), "declined"
    if pending["kind"] == "distance":
        updated.setdefault("hard_constraints", {})["max_distance_km"] = pending["new_value"]
    elif pending["kind"] == "downgrade_language":
        language = updated.setdefault("hard_constraints", {}).pop("language")
        updated.setdefault("preferences", {})[f"language:{language}"] = {
            "value": language, "weight": 4, "desired": True,
        }
    elif pending["kind"] == "downgrade_preference":
        for item in updated.get("preference_items", []):
            if item.get("attribute") == pending["attribute"] and item.get("value") == pending["old_value"]:
                item["importance"] = "preferred"
    updated["recognized"] = [f"relaxed {pending['attribute']}"]
    return sync_preference_schema(updated), "approved"
