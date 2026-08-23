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
    """Return a repair choice when a new requirement conflicts with saved state."""
    lowered = text.casefold()
    incoming_required = any(
        marker in lowered for marker in ("must", "need", "required", "require", "essential")
    )
    old_language = current.get("hard_constraints", {}).get("language")
    new_language = incoming.get("hard_constraints", {}).get("language")
    if old_language and new_language and old_language != new_language:
        return {
            "attribute": "language",
            "existing": old_language,
            "incoming": new_language,
            "question": (
                f"You already require {old_language}, but this message requires {new_language}. "
                f"Say ‘keep {old_language}’ or ‘use {new_language}’."
            ),
        }

    existing_pedagogy = current.get("preferences", {}).get("pedagogy")
    incoming_pedagogy = incoming.get("preferences", {}).get("pedagogy")
    if existing_pedagogy and incoming_pedagogy:
        old_value = existing_pedagogy.get("value")
        new_value = incoming_pedagogy.get("value")
        old_required = any(
            item.get("attribute") == "pedagogy" and item.get("importance") == "required"
            for item in current.get("preference_items", [])
        )
        opposing = (
            old_value == new_value
            and existing_pedagogy.get("desired", True)
            != incoming_pedagogy.get("desired", True)
        )
        if opposing or (old_value != new_value and old_required and incoming_required):
            old_label = old_value if existing_pedagogy.get("desired", True) else f"avoid {old_value}"
            new_label = new_value if incoming_pedagogy.get("desired", True) else f"avoid {new_value}"
            return {
                "attribute": "pedagogy",
                "existing": old_label,
                "incoming": new_label,
                "incoming_preference": dict(incoming_pedagogy),
                "question": (
                    f"Your saved teaching-approach requirement is {old_label}, while the new one is "
                    f"{new_label}. Say ‘keep {old_label}’ or ‘use {new_label}’."
                ),
            }
    return None


def resolve_contradiction(profile: dict[str, Any], text: str) -> tuple[dict[str, Any], bool]:
    pending = profile.get("pending_contradiction")
    if not pending:
        return profile, False
    lowered = text.casefold().strip()
    use_new = "use new" in lowered or (
        "use " in lowered and str(pending["incoming"]).casefold() in lowered
    )
    keep_old = "keep existing" in lowered or "keep current" in lowered or (
        "keep " in lowered and str(pending["existing"]).casefold() in lowered
    )
    if not use_new and not keep_old:
        return profile, False
    updated = dict(profile)
    if use_new:
        if pending["attribute"] == "language":
            updated.setdefault("hard_constraints", {})["language"] = pending["incoming"]
        elif pending["attribute"] == "pedagogy":
            updated.setdefault("preferences", {})["pedagogy"] = pending["incoming_preference"]
    updated.pop("pending_contradiction", None)
    updated["recognized"] = [f"resolved {pending['attribute']} contradiction"]
    return sync_preference_schema(updated), True


def propose_constraint_relaxation(profile: Mapping[str, Any]) -> dict[str, Any] | None:
    """Choose the smallest deterministic relaxation after a confirmed empty search."""
    hard = profile.get("hard_constraints", {})
    distance = hard.get("max_distance_km")
    if distance is not None:
        old_value = float(distance)
        new_value = max(old_value + 1, old_value * 1.5)
        return {
            "kind": "distance",
            "attribute": "max_distance_km",
            "old_value": old_value,
            "new_value": round(new_value, 1),
            "question": (
                f"No schools matched all current constraints. The smallest available change is "
                f"to expand the home-distance limit from {old_value:g} km to {new_value:g} km. "
                "Say ‘apply relaxation’ to approve it, or ‘keep constraints’ to decline."
            ),
        }
    language = hard.get("language")
    if language:
        return {
            "kind": "downgrade_language",
            "attribute": "language",
            "old_value": language,
            "new_value": language,
            "question": (
                f"No schools matched all current constraints. I can change {language} from a "
                "required language to a preferred language. Say ‘apply relaxation’ to approve "
                "it, or ‘keep constraints’ to decline."
            ),
        }
    required = next(
        (item for item in profile.get("preference_items", []) if item.get("importance") == "required"),
        None,
    )
    if required:
        label = str(required["attribute"]).replace("_", " ")
        return {
            "kind": "downgrade_preference",
            "attribute": required["attribute"],
            "old_value": required["value"],
            "new_value": required["value"],
            "question": (
                f"No schools matched all current constraints. I can change {label} from required "
                "to preferred. Say ‘apply relaxation’ to approve it, or ‘keep constraints’ to decline."
            ),
        }
    return None


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
