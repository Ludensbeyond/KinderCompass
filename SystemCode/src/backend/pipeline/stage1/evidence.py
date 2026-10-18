"""Evidence provenance, value-state, and freshness metadata for school attributes."""

from __future__ import annotations

import datetime as dt
from typing import Any


EVIDENCE_PROVENANCE = {
    "pedagogy": {"source": "KinderCompass derivation", "method": "derived_from_centre_name", "reliability": "limited"},
    "language": {"source": "ECDA/LifeSG preschool dataset", "method": "structured_record", "reliability": "direct"},
    "spark_certified": {"source": "ECDA/LifeSG preschool dataset", "method": "structured_record", "reliability": "direct"},
    "operator_scheme": {"source": "ECDA/LifeSG preschool dataset", "method": "structured_record", "reliability": "partial"},
    "transport": {"source": "ECDA/LifeSG preschool dataset", "method": "structured_record", "reliability": "direct"},
    "food": {"source": "ECDA/LifeSG preschool dataset", "method": "structured_record", "reliability": "partial"},
    "full_day": {"source": "ECDA/LifeSG preschool dataset", "method": "structured_record", "reliability": "direct"},
    "care_level": {"source": "ECDA/LifeSG service records", "method": "structured_record", "reliability": "direct"},
    "max_distance_km": {"source": "OneMap and preschool coordinates", "method": "calculated", "reliability": "calculated"},
}

GRAPH_RETRIEVAL_RELS = {
    "language": "TEACHES_IN",
    "care_level": "SERVES_LEVEL",
    "pedagogy": "USES_PEDAGOGY",
}


def _canonical_attribute(attribute: str) -> str:
    return "language" if attribute.startswith("language:") else attribute


def freshness(last_updated: Any, today: dt.date | None = None) -> str:
    """Classify source freshness without claiming a date when none is available."""
    if not last_updated:
        return "unknown"
    try:
        source_date = dt.date.fromisoformat(str(last_updated)[:10])
    except ValueError:
        return "unknown"
    age_days = ((today or dt.date.today()) - source_date).days
    if age_days < 0:
        return "future_dated"
    return "current" if age_days <= 365 else "stale"


def value_state(actual: Any, available: bool | float, evidence_state: str) -> str:
    if float(available or 0) <= 0:
        return "unknown"
    if evidence_state != "verified":
        return {
            "derived": "inferred_value",
            "calculated": "calculated_value",
            "partially_supported": "partially_supported_value",
        }.get(evidence_state, "recorded_value")
    if isinstance(actual, bool):
        return "confirmed_yes" if actual else "confirmed_no"
    return "confirmed_value"


def retrieval_steps(school: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise a Cypher retrieval_path into a list of relationship steps."""
    path = school.get("retrieval_path") or []
    if not isinstance(path, list):
        return []
    steps = []
    for step in path:
        if not isinstance(step, dict) or not step.get("rel"):
            continue
        steps.append({
            "rel": str(step["rel"]),
            "label": step.get("label"),
            "name": step.get("name"),
        })
    return steps


def evidence_details(attribute: str, school: dict[str, Any], actual: Any, available: bool | float) -> dict[str, Any]:
    """Return stable provenance metadata for one scored attribute."""
    canonical = _canonical_attribute(attribute)
    provenance = EVIDENCE_PROVENANCE.get(canonical, {
        "source": "Unknown source", "method": "unknown", "reliability": "unknown",
    })
    method = provenance["method"]
    strength = float(available or 0)
    state = (
        "unknown" if strength <= 0 else
        "derived" if method.startswith("derived") else
        "calculated" if method == "calculated" else
        "partially_supported" if provenance["reliability"] == "partial" else
        "verified" if provenance["reliability"] == "direct" else
        "recorded"
    )
    source_date = school.get("last_updated")
    details = {
        "evidence_state": state,
        "value_state": value_state(actual, available, state),
        "source": provenance["source"],
        "source_method": method,
        "source_reliability": provenance["reliability"],
        "availability": strength,
        "source_date": source_date,
        "freshness": freshness(source_date),
    }
    steps = retrieval_steps(school)
    if steps:
        details["retrieval_path"] = steps
        expected_rel = GRAPH_RETRIEVAL_RELS.get(canonical)
        if expected_rel and any(step["rel"] == expected_rel for step in steps):
            details["retrieval_method"] = "graph_traversal"
    return details
