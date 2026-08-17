"""Validated, evidence-aware preference schema for Stage 1."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


SCHEMA_VERSION = 2
IMPORTANCE_VALUES = {"required", "high_priority", "preferred", "nice_to_have"}
EVIDENCE_CLASSES = {"supported", "partially_supported", "unsupported"}

ATTRIBUTE_CATALOG = {
    "care_level": {
        "school_property": "care_levels",
        "evidence_class": "supported",
        "warning": None,
    },
    "language": {
        "school_property": "second_languages_offered",
        "evidence_class": "supported",
        "warning": "Evidence confirms that the language is offered, not its teaching intensity or quality.",
    },
    "spark_certified": {
        "school_property": "spark_certified",
        "evidence_class": "supported",
        "warning": None,
    },
    "transport": {
        "school_property": "provision_of_transport",
        "evidence_class": "supported",
        "warning": None,
    },
    "full_day": {
        "school_property": "weekday_full_day",
        "evidence_class": "supported",
        "warning": None,
    },
    "operator_scheme": {
        "school_property": "operator_scheme",
        "evidence_class": "partially_supported",
        "warning": "The dataset does not yet distinguish no operator scheme from missing scheme evidence.",
    },
    "food": {
        "school_property": "food_offered",
        "evidence_class": "partially_supported",
        "warning": "MUIS halal certification, halal-source food, and no-pork/no-lard policies are not equivalent.",
    },
    "pedagogy": {
        "school_property": "pedagogy",
        "evidence_class": "partially_supported",
        "warning": "Pedagogy is inferred from the centre name and is specific for only about 5% of records.",
    },
    "max_distance_km": {
        "school_property": "geometry",
        "evidence_class": "partially_supported",
        "warning": "Distance cannot be verified for schools without location data.",
    },
    "hands_on_learning": {
        "school_property": None,
        "evidence_class": "unsupported",
        "warning": "The current school dataset has no hands-on learning evidence.",
    },
    "child_led_learning": {
        "school_property": None,
        "evidence_class": "unsupported",
        "warning": "The current school dataset has no child-led learning evidence.",
    },
    "low_worksheet_use": {
        "school_property": None,
        "evidence_class": "unsupported",
        "warning": "The current school dataset has no worksheet-use evidence.",
    },
    "primary_school_readiness": {
        "school_property": None,
        "evidence_class": "unsupported",
        "warning": "The current school dataset has no primary-school-readiness evidence.",
    },
    "atmosphere": {
        "school_property": None,
        "evidence_class": "unsupported",
        "warning": "The current school dataset has no school-atmosphere evidence.",
    },
}

ALLOWED_VALUES = {
    "care_level": {
        "Infant (2 to 18 mths)",
        "Playgroup (18 mths to 2 yrs old)",
        "Pre-Nursery (3 yrs old)",
        "Nursery (4 yrs old)",
        "Kindergarten 1 (5 yrs old)",
        "Kindergarten 2 (6 yrs old)",
    },
    "language": {"Chinese", "Malay", "Tamil"},
    "spark_certified": {True, False},
    "transport": {True, False},
    "full_day": {True, False},
    "operator_scheme": {"Anchor Operator Scheme", "Partner Operator Scheme"},
    "food": {"halal"},
    "pedagogy": {"Montessori", "Play-based", "Bilingual", "Reggio Emilia"},
    "max_distance_km": set(),
    "hands_on_learning": {True},
    "child_led_learning": {True},
    "low_worksheet_use": {True},
    "primary_school_readiness": {True},
    "atmosphere": {True},
}


def make_preference_item(
    attribute: str,
    value: Any,
    importance: str = "preferred",
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Construct and validate one canonical preference item."""
    if attribute not in ATTRIBUTE_CATALOG:
        raise ValueError(f"Unknown preference attribute: {attribute}")
    if importance not in IMPORTANCE_VALUES:
        raise ValueError(f"Invalid preference importance: {importance}")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("Preference confidence must be a number from 0 to 1")
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("Preference value cannot be empty")
    if attribute == "max_distance_km":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0:
            raise ValueError("Maximum distance must be a positive number of kilometres")
        allowed_values = {value}
    else:
        allowed_values = ALLOWED_VALUES[attribute]
    boolean_attributes = {"spark_certified", "transport", "full_day"}
    if attribute in boolean_attributes and type(value) is not bool:
        raise ValueError(f"Value for {attribute} must be boolean")
    try:
        allowed = value in allowed_values
    except TypeError:
        allowed = False
    if not allowed:
        raise ValueError(f"Invalid value for {attribute}: {value}")
    evidence = ATTRIBUTE_CATALOG[attribute]
    return {
        "attribute": attribute,
        "value": value,
        "importance": importance,
        "confidence": round(float(confidence), 2),
        "evidence_class": evidence["evidence_class"],
        "school_property": evidence["school_property"],
        "warning": evidence["warning"],
    }


def validate_preference_item(item: dict[str, Any]) -> None:
    """Reject malformed or inconsistent preference items."""
    if not isinstance(item, dict):
        raise ValueError("Each preference item must be an object")
    expected = make_preference_item(
        item.get("attribute"), item.get("value"), item.get("importance"), item.get("confidence")
    )
    for field in ("evidence_class", "school_property", "warning"):
        if item.get(field) != expected[field]:
            raise ValueError(f"Preference {item.get('attribute')} has inconsistent {field}")


def _legacy_items(profile: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    hard = profile.get("hard_constraints", {})
    if hard.get("level"):
        items.append(make_preference_item("care_level", hard["level"], "required"))
    if hard.get("language"):
        items.append(make_preference_item("language", hard["language"], "required"))
    if hard.get("max_distance_km"):
        items.append(make_preference_item("max_distance_km", float(hard["max_distance_km"]), "required"))

    for legacy_attribute, preference in profile.get("preferences", {}).items():
        attribute = "language" if legacy_attribute.startswith("language:") else legacy_attribute
        if attribute not in ATTRIBUTE_CATALOG:
            raise ValueError(f"Legacy profile contains unknown preference: {legacy_attribute}")
        importance = "required" if attribute == "pedagogy" and float(preference.get("weight", 0)) >= 5 else "preferred"
        items.append(make_preference_item(attribute, preference.get("value"), importance))
    return items


def sync_preference_schema(profile: dict[str, Any]) -> dict[str, Any]:
    """Synchronise schema v2 metadata with the backward-compatible profile."""
    synced = deepcopy(profile)
    existing_metadata = {}
    for item in synced.get("preference_items", []):
        validate_preference_item(item)
        existing_metadata[(item["attribute"], str(item["value"]))] = (item["importance"], item["confidence"])
    supported_items = _legacy_items(synced)
    for item in supported_items:
        key = (item["attribute"], str(item["value"]))
        if key in existing_metadata:
            item["importance"], item["confidence"] = existing_metadata[key]
    unsupported_items = synced.get("unsupported_preferences", [])
    for item in unsupported_items:
        validate_preference_item(item)
        if item["evidence_class"] != "unsupported":
            raise ValueError("unsupported_preferences may only contain unsupported evidence")
    synced["schema_version"] = SCHEMA_VERSION
    synced["preference_items"] = supported_items
    synced["unsupported_preferences"] = unsupported_items
    validate_preference_profile(synced)
    return synced


def validate_preference_profile(profile: dict[str, Any]) -> None:
    """Validate the evidence-aware portion of a preference profile."""
    if not isinstance(profile, dict):
        raise ValueError("Preference profile must be an object")
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Preference profile must use schema version {SCHEMA_VERSION}")
    for item in profile.get("preference_items", []):
        validate_preference_item(item)
        if item["evidence_class"] == "unsupported":
            raise ValueError("Unsupported evidence belongs in unsupported_preferences")
    for item in profile.get("unsupported_preferences", []):
        validate_preference_item(item)
        if item["evidence_class"] != "unsupported":
            raise ValueError("Supported evidence belongs in preference_items")
