"""Decision-aware selection of the next useful preschool preference question."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable, Mapping


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
