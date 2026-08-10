"""Closed-set conversational intent routing with deterministic precedence."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


IntentName = Literal[
    "update_preferences",
    "find_closest_preschool",
    "recommend_selected_preschool",
    "assess_selected_preschool",
    "explain_top_ranked_preschool",
    "compare_selected_preschools",
    "explain_selected_tradeoffs",
    "explain_evidence_provenance",
    "reset_preferences",
    "needs_clarification",
]


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentName
    confidence: float = Field(ge=0, le=1)
    clarification: str | None = None
    method: Literal["rules", "llm", "rules_fallback"] = "rules"


def _rules(text: str) -> IntentResult | None:
    lowered = (text or "").strip().lower()
    if any(phrase in lowered for phrase in ("start over", "clear preferences", "reset preferences")):
        return IntentResult(intent="reset_preferences", confidence=1)
    if any(word in lowered for word in ("closest", "nearest")) and any(
        word in lowered for word in ("school", "preschool", "centre", "center")
    ):
        return IntentResult(intent="find_closest_preschool", confidence=1)
    if "trade-off" in lowered or "tradeoff" in lowered or "trade off" in lowered:
        return IntentResult(intent="explain_selected_tradeoffs", confidence=1)
    if any(phrase in lowered for phrase in ("where did", "where does", "source of", "how reliable", "information missing", "evidence missing")):
        return IntentResult(intent="explain_evidence_provenance", confidence=1)
    if any(word in lowered for word in ("compare", "difference", "versus", " vs ")):
        return IntentResult(intent="compare_selected_preschools", confidence=1)
    if ("why" in lowered and any(phrase in lowered for phrase in ("ranked first", "ranked highest", "top ranked", "top-ranked"))) or "why is this first" in lowered:
        return IntentResult(intent="explain_top_ranked_preschool", confidence=1)
    if "selected" in lowered and any(word in lowered for word in ("recommend", "best", "choose", "pick")):
        return IntentResult(intent="recommend_selected_preschool", confidence=1)
    if any(word in lowered for word in ("school", "preschool")) and any(
        phrase in lowered for phrase in ("suitable", "good fit", "right for me")
    ):
        return IntentResult(intent="assess_selected_preschool", confidence=1)
    return None


def _llm_enabled() -> bool:
    return os.getenv("OPENAI_INTENT_CLASSIFICATION_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _classify_with_openai(text: str) -> IntentResult:
    from openai import OpenAI

    client = OpenAI(timeout=float(os.getenv("OPENAI_INTENT_TIMEOUT_SECONDS", "8")))
    response = client.responses.parse(
        model=os.getenv("OPENAI_INTENT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        instructions=(
            "Classify the newest preschool-chat message into exactly one allowed intent. "
            "find_closest_preschool asks for the nearest current eligible result; "
            "update_preferences includes maximum-distance constraints such as within 1.5 km. "
            "explain_top_ranked_preschool asks why the first result ranked highest; "
            "compare_selected_preschools compares two or more selected results; "
            "explain_selected_tradeoffs asks about drawbacks of selected results. "
            "explain_evidence_provenance asks where selected-school facts came from, how reliable they are, or what evidence is missing. "
            "Use needs_clarification when meaning is genuinely ambiguous and provide one short question."
        ),
        input=text,
        text_format=IntentResult,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("The model did not return a parsed intent")
    result = response.output_parsed
    result.method = "llm"
    return result


def classify_intent(text: str) -> IntentResult:
    """Apply exact rules first, then an optional closed-set LLM classifier."""
    deterministic = _rules(text)
    if deterministic:
        return deterministic
    if not _llm_enabled():
        return IntentResult(intent="update_preferences", confidence=1)
    try:
        result = _classify_with_openai(text)
        if result.confidence < 0.7:
            return IntentResult(
                intent="needs_clarification",
                confidence=result.confidence,
                clarification=result.clarification or "Could you clarify what you would like me to do?",
                method="llm",
            )
        return result
    except Exception:
        return IntentResult(intent="update_preferences", confidence=1, method="rules_fallback")
