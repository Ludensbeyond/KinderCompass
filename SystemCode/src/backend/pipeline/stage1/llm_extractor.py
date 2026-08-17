"""Optional OpenAI preference extraction with deterministic fallback."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from stage1.nlp_mapper import map_text_to_filters, merge_preference_profile
from stage1.preference_schema import ALLOWED_VALUES, make_preference_item, sync_preference_schema


BOOLEAN_ATTRIBUTES = {"spark_certified", "transport", "full_day", "hands_on_learning", "child_led_learning", "low_worksheet_use", "primary_school_readiness", "atmosphere"}
RESET_PHRASES = ("start over", "clear preferences", "reset preferences")
DEFAULT_WEIGHTS = {
    "pedagogy": 5,
    "language": 4,
    "spark_certified": 4,
    "operator_scheme": 3,
    "transport": 3,
    "food": 4,
    "full_day": 4,
}


class ExtractedPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute: str
    value: str
    importance: Literal["required", "high_priority", "preferred", "nice_to_have"]
    confidence: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferences: list[ExtractedPreference]
    clarification: str | None


def llm_extraction_enabled() -> bool:
    return os.getenv("OPENAI_PREFERENCE_EXTRACTION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _canonical_context(profile: dict | None) -> list[dict]:
    if not profile:
        return []
    synced = sync_preference_schema(profile)
    return [
        {
            "attribute": item["attribute"],
            "value": item["value"],
            "importance": item["importance"],
        }
        for item in synced.get("preference_items", []) + synced.get("unsupported_preferences", [])
    ]


def _allowed_value_prompt() -> str:
    entries = []
    for attribute, values in ALLOWED_VALUES.items():
        if attribute == "max_distance_km":
            entries.append("- max_distance_km: any positive number of kilometres")
            continue
        rendered = sorted("true" if value is True else "false" if value is False else str(value) for value in values)
        entries.append(f"- {attribute}: {', '.join(rendered)}")
    return "\n".join(entries)


def _extract_with_openai(text: str, current: dict | None) -> ExtractionResult:
    from openai import OpenAI

    model = os.getenv("OPENAI_PREFERENCE_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    timeout = float(os.getenv("OPENAI_PREFERENCE_TIMEOUT_SECONDS", "8"))
    client = OpenAI(timeout=timeout)
    instructions = f"""Extract preschool preferences from only the newest user message.
Return only canonical attributes and values from this catalogue:
{_allowed_value_prompt()}

Use required only for non-negotiable requirements; high_priority for very important wording; preferred for ordinary preferences; and nice_to_have for optional or low-priority wording. Use confidence below 0.7 when the mapping is uncertain and provide one concise clarification question; otherwise clarification must be null. Do not infer personal, financial, location, date, or child identity data. Do not repeat an existing preference unless the newest message changes or confirms it."""
    payload = json.dumps(
        {"existing_preferences": _canonical_context(current), "newest_message": text},
        ensure_ascii=False,
    )
    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=payload,
        text_format=ExtractionResult,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("The model did not return a parsed preference result")
    return response.output_parsed


def _canonical_value(attribute: str, value: str):
    cleaned = value.strip()
    if attribute in BOOLEAN_ATTRIBUTES:
        lowered = cleaned.lower()
        if lowered not in {"true", "false"}:
            raise ValueError(f"Boolean preference {attribute} must use true or false")
        return lowered == "true"
    if attribute == "max_distance_km":
        return float(cleaned)
    return cleaned


def _merge_extraction(current: dict | None, result: ExtractionResult, source_text: str) -> dict:
    profile = deepcopy(current) if current else map_text_to_filters("")
    profile.setdefault("hard_constraints", {})
    profile.setdefault("preferences", {})
    unsupported = {item["attribute"]: item for item in profile.get("unsupported_preferences", [])}
    supported_metadata = {item["attribute"]: item for item in profile.get("preference_items", [])}

    for extracted in result.preferences:
        value = _canonical_value(extracted.attribute, extracted.value)
        item = make_preference_item(extracted.attribute, value, extracted.importance, extracted.confidence)
        attribute = item["attribute"]
        if item["evidence_class"] == "unsupported":
            unsupported[attribute] = item
            continue
        unsupported.pop(attribute, None)
        supported_metadata[attribute] = item
        if attribute == "care_level":
            profile["hard_constraints"]["level"] = value
        elif attribute == "max_distance_km":
            profile["hard_constraints"]["max_distance_km"] = value
        elif attribute == "language":
            profile["hard_constraints"].pop("language", None)
            for key in list(profile["preferences"]):
                if key.startswith("language:"):
                    profile["preferences"].pop(key)
            if extracted.importance == "required":
                profile["hard_constraints"]["language"] = value
            else:
                profile["preferences"][f"language:{value}"] = {"value": value, "weight": 4, "desired": True}
        else:
            weight = DEFAULT_WEIGHTS[attribute]
            if attribute == "pedagogy" and extracted.importance == "preferred":
                weight = 4
            profile["preferences"][attribute] = {"value": value, "weight": weight, "desired": True}

    profile["unsupported_preferences"] = list(unsupported.values())
    profile["preference_items"] = list(supported_metadata.values())
    profile["recognized"] = [item.attribute for item in result.preferences]
    profile["source_text"] = source_text
    profile["clarification_needed"] = result.clarification
    return sync_preference_schema(profile)


def merge_preference_profile_with_llm(current: dict | None, text: str) -> dict:
    """Use OpenAI when enabled; otherwise preserve deterministic extraction."""
    lowered = (text or "").strip().lower()
    if any(phrase in lowered for phrase in RESET_PHRASES):
        profile = merge_preference_profile(current, text)
        profile["extraction_method"] = "rules"
        return profile
    if not llm_extraction_enabled():
        profile = merge_preference_profile(current, text)
        profile["extraction_method"] = "rules"
        return profile
    try:
        result = _extract_with_openai(text, current)
        # Preserve exact, deterministic mappings even when the optional model
        # overlooks a phrase that the rules understand (for example "under 2km").
        rule_profile = merge_preference_profile(current, text)
        profile = _merge_extraction(rule_profile, result, text)
        profile["extraction_method"] = "llm"
        return profile
    except Exception as exc:
        profile = merge_preference_profile(current, text)
        profile["extraction_method"] = "rules_fallback"
        profile["llm_fallback_reason"] = type(exc).__name__
        return profile
