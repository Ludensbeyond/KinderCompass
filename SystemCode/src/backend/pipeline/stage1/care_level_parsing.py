"""Parse and validate explicit care-level mentions in parent messages."""

from __future__ import annotations

import re

from stage1.nlp_mapper import KINDERGARTEN_LEVEL_PHRASES, LEVEL_KEYWORDS

_KINDERGARTEN_DISTANCE = re.compile(
    r"\bkindergarten\s*\d+(?:\.\d+)?\s*(?:km|kilomet)",
    re.IGNORECASE,
)


def explicit_care_level_from_message(message: str) -> str | None:
    """Return one catalogue care level named plainly in the message, if any."""
    lowered = (message or "").strip().lower()
    if not lowered:
        return None
    block_kindergarten = bool(_KINDERGARTEN_DISTANCE.search(lowered))
    for phrase in sorted(LEVEL_KEYWORDS, key=len, reverse=True):
        if block_kindergarten and phrase in KINDERGARTEN_LEVEL_PHRASES:
            continue
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered):
            return LEVEL_KEYWORDS[phrase]
    return None


def kindergarten_level_mentioned(message: str, care_level_value: str) -> bool:
    if not str(care_level_value).startswith("Kindergarten "):
        return False
    if _KINDERGARTEN_DISTANCE.search(message or ""):
        return False
    level = str(care_level_value).split()[1]
    word = {"1": "one", "2": "two"}[level]
    pattern = rf"(?<!\w)(?:k\s*{level}|kindergarten\s*(?:{level}|{word}))(?!\w)"
    return bool(re.search(pattern, message, re.IGNORECASE))


def message_requests_language_followup(message: str) -> bool:
    lowered = (message or "").strip().lower()
    if not lowered:
        return False
    cues = (
        "bilingual", "second language", "2nd language", "third language",
        "mandarin", "chinese", "malay", "tamil", "language medium",
        "speak chinese", "speak malay", "speak tamil",
    )
    if any(cue in lowered for cue in cues):
        return True
    return bool(re.search(r"\blanguage\b", lowered))


def care_level_supported_by_message(message: str, care_level_value: str) -> bool:
    if explicit_care_level_from_message(message) == care_level_value:
        return True
    if str(care_level_value).startswith("Kindergarten "):
        return kindergarten_level_mentioned(message, care_level_value)
    return False
