"""Deterministic natural-language preference extraction for Stage 1."""

from copy import deepcopy
import re

from stage1.distance_policy import NEAR_HOME_RADIUS_KM, distance_opt_out
from stage1.preference_schema import make_preference_item, sync_preference_schema

LEVEL_KEYWORDS = {
    "infant care": "Infant (2 to 18 mths)",
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

KINDERGARTEN_LEVEL_PHRASES = frozenset({"k1", "k2", "kindergarten 1", "kindergarten 2"})

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


_IMPORTANCE_CUES = (
    ("nice_to_have", re.compile(r"\b(?:nice[ -]+to[ -]+have|optional|low[ -]+priority|if possible|bonus)\b")),
    ("high_priority", re.compile(r"\b(?:high[ -]+priority|very important|top[ -]+priority)\b")),
    ("preferred", re.compile(r"\b(?:not required|not essential|not needed|preferred|prefer)\b")),
    ("required", re.compile(r"\b(?:non[ -]?negotiable|must(?: have)?|required|require|essential|need(?:ed)?)\b")),
)

_PREFERENCE_MENTION_PATTERNS = (
    ("pedagogy", ("montessori", "play-based", "play based", "bilingual", "reggio", "play")),
    ("language:Chinese", ("chinese", "mandarin")),
    ("language:Malay", ("malay",)),
    ("language:Tamil", ("tamil",)),
    ("spark_certified", ("spark",)),
    ("operator_scheme", ("anchor operator", "partner operator")),
    ("transport", ("transport",)),
    ("food", ("halal", "no pork")),
    ("full_day", ("full day", "full-day")),
)


def _explicit_importance(text: str) -> dict[str, str]:
    """Associate each explicit importance cue with the nearest preference in its clause."""
    mentions = []
    occupied = []
    patterns = sorted(
        ((phrase, attribute) for attribute, phrases in _PREFERENCE_MENTION_PATTERNS for phrase in phrases),
        key=lambda item: len(item[0]), reverse=True,
    )
    for phrase, attribute in patterns:
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, flags=re.IGNORECASE):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            mentions.append((match.start(), match.end(), attribute))
            occupied.append((match.start(), match.end()))
    mentions.sort()

    boundaries = [-1] + [match.start() for match in re.finditer(r"[,;.!?]", text)] + [len(text)]
    result: dict[str, str] = {}
    for start, end in zip(boundaries, boundaries[1:]):
        clause_start, clause_end = start + 1, end
        clause_mentions = [item for item in mentions if item[0] >= clause_start and item[1] <= clause_end]
        if not clause_mentions:
            continue
        clause = text[clause_start:clause_end]
        clause_cues = []
        for importance, pattern in _IMPORTANCE_CUES:
            for cue in pattern.finditer(clause):
                if importance == "required" and re.search(
                    r"\bnot\s+(?:required|essential|needed|need|require)\b",
                    clause[max(0, cue.start() - 8):cue.end()],
                ):
                    continue
                clause_cues.append((clause_start + cue.start(), clause_start + cue.end(), importance))
        if len(clause_cues) == 1 and clause_cues[0][1] <= clause_mentions[0][0]:
            # A leading requirement/preference cue governs the following list
            # in constructions such as "Need Montessori with Chinese and SPARK".
            for mention in clause_mentions:
                result[mention[2]] = clause_cues[0][2]
            continue
        for mention in clause_mentions:
            if clause_cues:
                result[mention[2]] = min(
                    clause_cues,
                    key=lambda cue: min(abs(cue[0] - mention[1]), abs(mention[0] - cue[1])),
                )[2]
    return result


def map_text_to_filters(text: str) -> dict:
    """Extract hard constraints and weighted preferences from parent text."""
    lowered = (text or "").strip().lower()
    hard_constraints = {}
    preferences = {}
    recognized = []
    unsupported_preferences = []
    importance_by_attribute = _explicit_importance(lowered)

    for phrase, level in LEVEL_KEYWORDS.items():
        if phrase in lowered:
            hard_constraints["level"] = level
            recognized.append(phrase)
            break

    for phrase, pedagogy in PEDAGOGY_KEYWORDS.items():
        if phrase in lowered:
            avoids = any(marker in lowered for marker in (f"no {phrase}", f"not {phrase}", f"don't want {phrase}", f"do not want {phrase}"))
            preferences["pedagogy"] = _preference(pedagogy, weight=4, desired=not avoids)
            recognized.append(phrase)
            break

    for phrase, language in LANGUAGE_KEYWORDS.items():
        if phrase in lowered:
            required = importance_by_attribute.get(f"language:{language}") == "required"
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
        avoids = any(phrase in lowered for phrase in (
            "no transport", "without transport", "don't need transport", "do not need transport",
            "don't want transport", "do not want transport",
        ))
        preferences["transport"] = _preference(True, 3, not avoids)
        recognized.append("transport")
    if "halal" in lowered or "no pork" in lowered:
        food_value = "halal" if "halal" in lowered else "no_pork"
        avoids = any(phrase in lowered for phrase in ("not halal", "non-halal", "don't need halal", "do not need halal"))
        preferences["food"] = _preference(food_value, 4, not avoids)
        recognized.append("halal food")
    if "full day" in lowered or "full-day" in lowered:
        preferences["full_day"] = _preference(True, 4)
        recognized.append("full day")

    distance_match = re.search(r"(?:less than|under|within|maximum|max|up to)?\s*(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:er|re)s?)\b", lowered)
    if distance_match and float(distance_match.group(1)) > 0:
        hard_constraints["max_distance_km"] = float(distance_match.group(1))
        recognized.append(f"within {distance_match.group(1)} km")
    elif re.search(
        r"\b(?:near(?:by)?|close to)\s+(?:my\s+)?(?:home|house|place)\b|\bnear\s+home\b|\bnear\s+my\s+place\b",
        lowered,
    ):
        hard_constraints["max_distance_km"] = NEAR_HOME_RADIUS_KM
        recognized.append("near home")

    seen_unsupported = set()
    for phrase, (attribute, value) in UNSUPPORTED_KEYWORDS.items():
        if phrase in lowered and attribute not in seen_unsupported:
            unsupported_preferences.append(make_preference_item(attribute, value, "preferred", 0.9))
            recognized.append(phrase)
            seen_unsupported.add(attribute)

    profile = sync_preference_schema({
        "hard_constraints": hard_constraints,
        "preferences": preferences,
        "unsupported_preferences": unsupported_preferences,
        "recognized": recognized,
        "source_text": text,
        "skip_default_distance": distance_opt_out(lowered),
    })
    for item in profile["preference_items"]:
        key = f"language:{item['value']}" if item["attribute"] == "language" else item["attribute"]
        if key in importance_by_attribute:
            item["importance"] = importance_by_attribute[key]
    return profile


def merge_preference_profile(current: dict | None, text: str) -> dict:
    """Merge one chat turn into a cumulative, user-correctable profile."""
    lowered = (text or "").strip().lower()
    if any(phrase in lowered for phrase in ("start over", "clear preferences", "reset preferences")):
        return map_text_to_filters("")

    incoming = map_text_to_filters(text)
    merged = deepcopy(current) if current else map_text_to_filters("")
    merged.setdefault("hard_constraints", {})
    merged.setdefault("preferences", {})

    explicit_importance = _explicit_importance(lowered)
    metadata_by_key = {
        (item["attribute"], str(item["value"])): item
        for item in merged.get("preference_items", [])
    }

    if distance_opt_out(lowered):
        merged["hard_constraints"].pop("max_distance_km", None)
        merged["skip_default_distance"] = True
    elif incoming["hard_constraints"].get("max_distance_km") is not None or any(
        token in incoming.get("recognized", []) for token in ("near home",)
    ):
        merged.pop("skip_default_distance", None)

    for key, value in incoming["hard_constraints"].items():
        merged["hard_constraints"][key] = value
    for key, value in incoming["preferences"].items():
        merged["preferences"][key] = value
    for item in incoming.get("preference_items", []):
        attribute_key = f"language:{item['value']}" if item["attribute"] == "language" else item["attribute"]
        if attribute_key in explicit_importance:
            metadata_by_key[(item["attribute"], str(item["value"]))] = item
    merged["preference_items"] = list(metadata_by_key.values())
    unsupported_by_attribute = {
        item["attribute"]: item for item in merged.get("unsupported_preferences", [])
    }
    unsupported_by_attribute.update({
        item["attribute"]: item for item in incoming.get("unsupported_preferences", [])
    })
    merged["unsupported_preferences"] = list(unsupported_by_attribute.values())

    # A parent can downgrade a previously required language to a preference.
    for phrase, language in LANGUAGE_KEYWORDS.items():
        language_importance = explicit_importance.get(f"language:{language}")
        if phrase in lowered and language_importance in {"high_priority", "preferred", "nice_to_have"}:
            if merged["hard_constraints"].get("language") == language:
                merged["hard_constraints"].pop("language", None)
            merged["preferences"][f"language:{language}"] = _preference(language, 4)

    merged["recognized"] = incoming["recognized"]
    merged["source_text"] = text
    return sync_preference_schema(merged)


def summarize_profile(profile: dict, *, home_postal_code: str | None = None) -> list[str]:
    """Return concise user-facing descriptions of stored preferences."""
    from stage1.distance_policy import DEFAULT_HOME_RADIUS_KM, effective_search_radius_km

    summary = []
    hard = profile.get("hard_constraints", {})
    if hard.get("level"):
        summary.append(f"Required care level: {hard['level']}")
    if hard.get("language"):
        summary.append(f"Required language: {hard['language']}")
    if hard.get("max_distance_km") is not None:
        distance = float(hard["max_distance_km"])
        summary.append(f"Required distance: within {distance:g} km from home")
    elif effective_search_radius_km(profile, home_postal_code) == DEFAULT_HOME_RADIUS_KM:
        summary.append(f"Distance (default): within {DEFAULT_HOME_RADIUS_KM:g} km from home")
    for attribute, preference in profile.get("preferences", {}).items():
        label = attribute.split(":", 1)[0].replace("_", " ").title()
        value = preference.get("value")
        desired = preference.get("desired", True)
        if attribute.startswith("language:"):
            summary.append(f"Preferred language: {value}")
        elif isinstance(value, bool):
            stored = next((
                item.get("importance") for item in profile.get("preference_items", [])
                if item.get("attribute") == attribute and item.get("value") is value
            ), None)
            strength = stored.replace("_", " ") if isinstance(stored, str) else ("preferred" if desired else "not preferred")
            summary.append(f"{label}: {strength}")
        else:
            summary.append(f"{label}: {value}{'' if desired else ' (avoid)'}")
    for item in profile.get("unsupported_preferences", []):
        label = item["attribute"].replace("_", " ").title()
        summary.append(f"{label}: noted, not used for ranking")
    return summary
