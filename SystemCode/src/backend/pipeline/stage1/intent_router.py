"""Validated hybrid intent routing for operational and open-ended preschool chat."""

from __future__ import annotations

import os
import re
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
    "run_what_if_scenario",
    "explain_school_exclusion",
    "ask_selected_school_evidence",
    "ask_general_knowledge",
    "ask_combined_evidence",
    "reset_preferences",
    "needs_clarification",
]

TopicCategory = Literal[
    "pedagogy",
    "curriculum_framework",
    "quality_framework",
    "subsidy_policy",
    "school_attribute",
    "other",
]


class TopicEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    category: TopicCategory


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentName
    confidence: float = Field(ge=0, le=1)
    clarification: str | None = None
    method: Literal["rules", "llm", "rules_fallback"] = "rules"
    topics: list[TopicEntity] = Field(default_factory=list, max_length=5)
    relationship: Literal[
        "single_concept",
        "comparable",
        "different_categories",
        "combined_school_and_general",
        "unknown",
    ] = "unknown"
    message_type: Literal["preference", "question", "operation", "mixed", "unknown"] = "unknown"


def _rules(text: str, active_school_name: str | None = None) -> IntentResult | None:
    lowered = (text or "").strip().lower()
    if any(phrase in lowered for phrase in ("start over", "clear preferences", "reset preferences")):
        return IntentResult(intent="reset_preferences", confidence=1)
    if re.search(
        r"\b(?:less than|under|within|maximum|max|up to)\s+\d+(?:\.\d+)?\s*(?:km|kilomet(?:er|re)s?)\b",
        lowered,
    ):
        return IntentResult(intent="update_preferences", confidence=1)
    if "what if" in lowered or re.search(r"\bif my (?:income|working hours|work hours)\b", lowered):
        return IntentResult(intent="run_what_if_scenario", confidence=1)
    if "why" in lowered and any(
        phrase in lowered for phrase in ("excluded", "not eligible", "not shown", "left out")
    ):
        return IntentResult(intent="explain_school_exclusion", confidence=1)
    if any(word in lowered for word in ("closest", "nearest")) and any(
        word in lowered for word in ("school", "preschool", "centre", "center")
    ):
        return IntentResult(intent="find_closest_preschool", confidence=1)
    if "trade-off" in lowered or "tradeoff" in lowered or "trade off" in lowered:
        return IntentResult(intent="explain_selected_tradeoffs", confidence=1)
    if any(phrase in lowered for phrase in ("where did", "where does", "source of", "how reliable", "information missing", "evidence missing")):
        return IntentResult(intent="explain_evidence_provenance", confidence=1)
    asks_about_school = any(
        phrase in lowered for phrase in ("this school", "this preschool", "selected school", "selected preschool")
    )
    if active_school_name and re.search(r"\b(it|its|that school|that preschool)\b", lowered):
        asks_about_school = True
    asks_for_fact = lowered.startswith(("does ", "do ", "is ", "are ", "what ", "which ", "how ", "tell me "))
    asks_for_decision = any(
        phrase in lowered
        for phrase in ("suitable", "good fit", "right for me", "recommend", "best", "choose", "pick")
    )
    general_topics = (
        "montessori", "reggio", "play-based", "play based", "pedagogy", "curriculum approach",
        "early years development framework", "eydf", "nurturing early learners", "nel framework",
        "outdoor learning", "child-led", "child led", "spark 2.0", "curriculum", "literature-based",
        "basic subsidy", "additional subsidy", "preschool subsidy", "childcare subsidy",
        "infant care subsidy", "infant-care subsidy", "kifas", "fee assistance",
        "household income", "per capita income", "working mother", "working applicant",
        "january 2027", "$15,000 income ceiling", "subsidy income ceiling",
    )
    subsidy_topics = general_topics[16:]
    asks_for_explanation = any(
        phrase in lowered for phrase in ("what is", "what does that mean", "explain", "difference between", "how does it work")
    )
    if asks_about_school and asks_for_explanation and any(topic in lowered for topic in general_topics):
        return IntentResult(intent="ask_combined_evidence", confidence=1)
    if asks_about_school and asks_for_fact and not asks_for_decision:
        return IntentResult(intent="ask_selected_school_evidence", confidence=1)
    if not asks_about_school and any(topic in lowered for topic in subsidy_topics):
        return IntentResult(intent="ask_general_knowledge", confidence=1)
    if asks_for_explanation and any(topic in lowered for topic in general_topics):
        return IntentResult(intent="ask_general_knowledge", confidence=1)
    if any(word in lowered for word in ("compare", "difference", "versus", " vs ")) and any(
        topic in lowered for topic in general_topics
    ):
        return IntentResult(intent="ask_general_knowledge", confidence=1)
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


def _classify_with_openai(text: str, active_school_name: str | None = None) -> IntentResult:
    from openai import OpenAI

    client = OpenAI(timeout=float(os.getenv("OPENAI_INTENT_TIMEOUT_SECONDS", "8")))
    response = client.responses.parse(
        model=os.getenv("OPENAI_INTENT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        instructions=(
            "First classify the newest message_type as preference, question, operation, or mixed. "
            "A preference states desired school criteria (for example, 'I want a school that teaches Chinese' "
            "or 'schools within 2 km') and must use update_preferences. A question asks for information or an "
            "answer. An operation asks the application to reset, compare, recommend, or locate something. "
            "A mixed message both changes criteria and asks a question; choose the intent for the requested "
            "immediate action, but never interpret a preference-only statement as a location lookup. "
            "Then classify it into exactly one allowed intent and "
            "extract up to five named early-childhood topics. Assign each topic its semantic "
            "category and describe their relationship. Use different_categories when a user "
            "contrasts concepts that answer different questions, such as Montessori pedagogy "
            "and the SPARK quality framework. Do not treat a quality or curriculum framework "
            "as a pedagogy. "
            "find_closest_preschool asks which school is geographically nearest to the user's home; "
            "update_preferences includes maximum-distance constraints such as within 1.5 km. "
            "explain_top_ranked_preschool asks why the first result ranked highest; "
            "compare_selected_preschools compares two or more selected results; "
            "explain_selected_tradeoffs asks about drawbacks of selected results. "
            "explain_evidence_provenance asks where selected-school facts came from, how reliable they are, or what evidence is missing. "
            "run_what_if_scenario asks how fees or eligibility would change under hypothetical family inputs without changing saved details. "
            "explain_school_exclusion asks why a school was removed from eligible recommendations. "
            "ask_selected_school_evidence asks a factual question about exactly one selected school, such as its curriculum, languages, fees, facilities, or philosophy. "
            "ask_general_knowledge explains an early-childhood curriculum, pedagogy, framework, or educational concept without making a claim about one school. "
            "ask_combined_evidence combines a selected school's verified claim with a separately sourced general explanation. "
            "Use needs_clarification when meaning is genuinely ambiguous and provide one short question."
        ),
        input=(
            f"Active school from the preceding chat turn: {active_school_name}\n"
            f"Newest user message: {text}"
            if active_school_name else text
        ),
        text_format=IntentResult,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("The model did not return a parsed intent")
    result = response.output_parsed
    result.method = "llm"
    if result.message_type == "preference" and result.intent != "update_preferences":
        result.intent = "update_preferences"
    return result


def classify_intent(text: str, active_school_name: str | None = None) -> IntentResult:
    """Protect explicit operations, then prioritize LLM semantics when enabled."""
    deterministic = _rules(text, active_school_name)
    llm_priority_intents = {
        "ask_general_knowledge",
        "ask_combined_evidence",
        "find_closest_preschool",
    }
    if deterministic and deterministic.intent not in llm_priority_intents:
        return deterministic
    if not _llm_enabled():
        return deterministic or IntentResult(intent="update_preferences", confidence=1)
    try:
        result = _classify_with_openai(text, active_school_name)
        if result.confidence < 0.7:
            return IntentResult(
                intent="needs_clarification",
                confidence=result.confidence,
                clarification=result.clarification or "Could you clarify what you would like me to do?",
                method="llm",
            )
        return result
    except Exception:
        if deterministic:
            return deterministic.model_copy(update={"method": "rules_fallback"})
        return IntentResult(intent="update_preferences", confidence=1, method="rules_fallback")
