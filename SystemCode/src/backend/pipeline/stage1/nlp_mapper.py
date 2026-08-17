"""Deterministic natural-language preference extraction for Stage 1."""

from copy import deepcopy
import re

from stage1.preference_schema import make_preference_item, sync_preference_schema

LEVEL_KEYWORDS = {
    "infant": "Infant (2 to 18 mths)",
    "playgroup": "Playgroup (18 mths to 2 yrs old)",
    "pre-nursery": "Pre-Nursery (3 yrs old)",
    "pre nursery": "Pre-Nursery (3 yrs old)",
    "nursery": "Nursery (4 yrs old)",
    "kindergarten 1": "Kindergarten 1 (5 yrs old)",
    "k1": "Kindergarten 1 (5 yrs old)",
    "kindergarten 2": "Kindergarten 2 (6 yrs old)",
    "k2": "Kindergarten 2 (6 yrs old)",
}

PEDAGOGY_KEYWORDS = {
    "montessori": "Montessori",
    "play-based": "Play-based",
    "play based": "Play-based",
    "play": "Play-based",
    "bilingual": "Bilingual",
    "reggio": "Reggio Emilia",
}

LANGUAGE_KEYWORDS = {"chinese": "Chinese", "mandarin": "Chinese", "malay": "Malay", "tamil": "Tamil"}

UNSUPPORTED_KEYWORDS = {
    "hands-on": ("hands_on_learning", True),
    "hands on": ("hands_on_learning", True),
    "child-led": ("child_led_learning", True),
    "child led": ("child_led_learning", True),
    "independent learning": ("child_led_learning", True),
    "few worksheets": ("low_worksheet_use", True),
    "fewer worksheets": ("low_worksheet_use", True),
    "not too many worksheets": ("low_worksheet_use", True),
    "primary school readiness": ("primary_school_readiness", True),
    "ready for primary school": ("primary_school_readiness", True),
    "atmosphere": ("atmosphere", True),
}


def _preference(value, weight=5, desired=True):
    return {"value": value, "weight": weight, "desired": desired}


def map_text_to_filters(text: str) -> dict:
    """Extract hard constraints and weighted preferences from parent text."""
    lowered = (text or "").strip().lower()
    hard_constraints = {}
    preferences = {}
    recognized = []
    unsupported_preferences = []

    for phrase, level in LEVEL_KEYWORDS.items():
        if phrase in lowered:
            hard_constraints["level"] = level
            recognized.append(phrase)
            break

    for phrase, pedagogy in PEDAGOGY_KEYWORDS.items():
        if phrase in lowered:
            avoids = any(marker in lowered for marker in (f"no {phrase}", f"not {phrase}", f"don't want {phrase}", f"do not want {phrase}"))
            preferences["pedagogy"] = _preference(pedagogy, desired=not avoids)
            recognized.append(phrase)
            break

    for phrase, language in LANGUAGE_KEYWORDS.items():
        if phrase in lowered:
            required = any(marker in lowered for marker in ("must", "need", "required", "require"))
            if required:
                hard_constraints["language"] = language
            else:
                preferences[f"language:{language}"] = _preference(language, 4)
            recognized.append(phrase)

    if "spark" in lowered:
        preferences["spark_certified"] = _preference(True, 4, "not spark" not in lowered and "no spark" not in lowered)
        recognized.append("spark")
    if "anchor operator" in lowered:
        preferences["operator_scheme"] = _preference("Anchor Operator Scheme", 3)
        recognized.append("anchor operator")
    elif "partner operator" in lowered:
        preferences["operator_scheme"] = _preference("Partner Operator Scheme", 3)
        recognized.append("partner operator")
    if "transport" in lowered:
        avoids = any(phrase in lowered for phrase in ("no transport", "without transport", "don't need transport", "do not need transport"))
        preferences["transport"] = _preference(True, 3, not avoids)
        recognized.append("transport")
    if "halal" in lowered or "no pork" in lowered:
        preferences["food"] = _preference("halal", 4)
        recognized.append("halal food")
    if "full day" in lowered or "full-day" in lowered:
        preferences["full_day"] = _preference(True, 4)
        recognized.append("full day")

    distance_match = re.search(r"(?:less than|under|within|maximum|max|up to)?\s*(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:er|re)s?)\b", lowered)
    if distance_match and float(distance_match.group(1)) > 0:
        hard_constraints["max_distance_km"] = float(distance_match.group(1))
        recognized.append(f"within {distance_match.group(1)} km")

    seen_unsupported = set()
    for phrase, (attribute, value) in UNSUPPORTED_KEYWORDS.items():
        if phrase in lowered and attribute not in seen_unsupported:
            unsupported_preferences.append(make_preference_item(attribute, value, "preferred", 0.9))
            recognized.append(phrase)
            seen_unsupported.add(attribute)

    return sync_preference_schema({
        "hard_constraints": hard_constraints,
        "preferences": preferences,
        "unsupported_preferences": unsupported_preferences,
        "recognized": recognized,
        "source_text": text,
    })


def merge_preference_profile(current: dict | None, text: str) -> dict:
    """Merge one chat turn into a cumulative, user-correctable profile."""
    lowered = (text or "").strip().lower()
    if any(phrase in lowered for phrase in ("start over", "clear preferences", "reset preferences")):
        return map_text_to_filters("")

    incoming = map_text_to_filters(text)
    merged = deepcopy(current) if current else map_text_to_filters("")
    merged.setdefault("hard_constraints", {})
    merged.setdefault("preferences", {})

    for key, value in incoming["hard_constraints"].items():
        merged["hard_constraints"][key] = value
    for key, value in incoming["preferences"].items():
        merged["preferences"][key] = value
    unsupported_by_attribute = {
        item["attribute"]: item for item in merged.get("unsupported_preferences", [])
    }
    unsupported_by_attribute.update({
        item["attribute"]: item for item in incoming.get("unsupported_preferences", [])
    })
    merged["unsupported_preferences"] = list(unsupported_by_attribute.values())

    # A parent can downgrade a previously required language to a preference.
    for phrase, language in LANGUAGE_KEYWORDS.items():
        if phrase in lowered and any(marker in lowered for marker in ("preferred", "preference", "not required", "optional")):
            if merged["hard_constraints"].get("language") == language:
                merged["hard_constraints"].pop("language", None)
            merged["preferences"][f"language:{language}"] = _preference(language, 4)

    merged["recognized"] = incoming["recognized"]
    merged["source_text"] = text
    return sync_preference_schema(merged)


def summarize_profile(profile: dict) -> list[str]:
    """Return concise user-facing descriptions of stored preferences."""
    summary = []
    hard = profile.get("hard_constraints", {})
    if hard.get("level"):
        summary.append(f"Required care level: {hard['level']}")
    if hard.get("language"):
        summary.append(f"Required language: {hard['language']}")
    if hard.get("max_distance_km"):
        distance = float(hard["max_distance_km"])
        summary.append(f"Required distance: within {distance:g} km from home")
    for attribute, preference in profile.get("preferences", {}).items():
        label = attribute.split(":", 1)[0].replace("_", " ").title()
        value = preference.get("value")
        desired = preference.get("desired", True)
        if attribute.startswith("language:"):
            summary.append(f"Preferred language: {value}")
        elif isinstance(value, bool):
            summary.append(f"{label}: {'preferred' if desired else 'not preferred'}")
        else:
            summary.append(f"{label}: {value}{'' if desired else ' (avoid)'}")
    for item in profile.get("unsupported_preferences", []):
        label = item["attribute"].replace("_", " ").title()
        summary.append(f"{label}: noted, not used for ranking")
    return summary
