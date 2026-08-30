"""Conservative spelling normalization for curated early-childhood topics."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable


WORD_RE = re.compile(r"[A-Za-z][A-Za-z-]*")
MIN_WORD_LENGTH = 5
MIN_SIMILARITY = 0.88
MIN_BEST_MATCH_MARGIN = 0.05


GENERAL_TOPIC_NAMES = (
    "Montessori",
    "Reggio Emilia",
    "play-based learning",
    "pedagogy",
    "curriculum approach",
    "Early Years Development Framework",
    "Nurturing Early Learners framework",
    "outdoor learning",
    "child-led learning",
    "SPARK 2.0",
    "Basic Subsidy",
    "Additional Subsidy",
    "preschool subsidy",
    "childcare subsidy",
    "infant-care subsidy",
    "Kindergarten Fee Assistance Scheme",
)


def normalize_topic_spelling(text: str, topics: Iterable[str]) -> str:
    """Correct clear token-level misspellings using only known topic vocabulary."""
    candidates = {
        word.casefold()
        for topic in topics
        for word in WORD_RE.findall(str(topic))
        if len(word) >= MIN_WORD_LENGTH
    }
    if not candidates:
        return text

    def replace(match: re.Match[str]) -> str:
        original = match.group(0)
        token = original.casefold()
        if len(token) < MIN_WORD_LENGTH or token in candidates:
            return original
        ranked = sorted(
            ((SequenceMatcher(None, token, candidate).ratio(), candidate) for candidate in candidates),
            reverse=True,
        )
        best_score, best = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0.0
        if best_score < MIN_SIMILARITY or best_score - second_score < MIN_BEST_MATCH_MARGIN:
            return original
        return best

    return WORD_RE.sub(replace, text)
