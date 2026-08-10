"""Optional grounded explanations for deterministic school decisions."""

from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from stage1.preference_schema import sync_preference_schema


class GroundedExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=1800)
    referenced_school_ids: list[str]


def grounded_explanations_enabled() -> bool:
    return os.getenv("OPENAI_GROUNDED_EXPLANATIONS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _school_facts(centres: list[dict]) -> list[dict]:
    allowed = (
        "school_id", "name", "match_score", "profile_confidence", "net_monthly_fee",
        "distance_km", "strengths", "tradeoffs", "eligible_level", "match_breakdown",
    )
    return [{key: centre.get(key) for key in allowed} for centre in centres]


def _preference_facts(profile: dict | None) -> list[dict]:
    if not profile:
        return []
    synced = sync_preference_schema(profile)
    allowed = ("attribute", "value", "importance", "evidence_class", "warning")
    return [
        {key: item.get(key) for key in allowed}
        for item in synced.get("preference_items", []) + synced.get("unsupported_preferences", [])
    ]


def _explain_with_openai(
    question: str,
    task: Literal["recommendation", "suitability", "ranking", "comparison", "tradeoffs", "provenance"],
    centres: list[dict],
    profile: dict | None,
    deterministic_answer: str,
    decided_school_id: str,
) -> GroundedExplanation:
    from openai import OpenAI

    model = os.getenv("OPENAI_EXPLANATION_MODEL", os.getenv("OPENAI_PREFERENCE_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout = float(os.getenv("OPENAI_EXPLANATION_TIMEOUT_SECONDS", "8"))
    client = OpenAI(timeout=timeout)
    instructions = """Explain a deterministic preschool decision using only the supplied JSON facts.
The application has already made the decision; do not select a different school or change the suitability verdict. Lead with the conclusion, then explain preference match, strengths, material trade-offs, cost, and distance when those facts are available. Treat unsupported preferences and evidence warnings as limitations, not verified school characteristics. Never invent programmes, quality claims, fees, distances, certifications, or outcomes. State when evidence is unavailable. Keep the answer concise and parent-friendly. referenced_school_ids must contain only IDs from the supplied schools that are actually discussed."""
    payload = json.dumps({
        "task": task,
        "user_question": question,
        "decided_school_id": decided_school_id,
        "deterministic_answer": deterministic_answer,
        "preferences": _preference_facts(profile),
        "selected_schools": _school_facts(centres),
    }, ensure_ascii=False)
    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=payload,
        text_format=GroundedExplanation,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("The model did not return a parsed grounded explanation")
    return response.output_parsed


def explain_school_decision(
    question: str,
    task: Literal["recommendation", "suitability"],
    centres: list[dict],
    profile: dict | None,
    deterministic_answer: str,
    decided_school_id: str | None,
) -> tuple[str, str, str | None]:
    """Return answer, method, and a safe fallback reason."""
    if not grounded_explanations_enabled() or not decided_school_id:
        return deterministic_answer, "deterministic", None
    try:
        explanation = _explain_with_openai(
            question, task, centres, profile, deterministic_answer, decided_school_id
        )
        allowed_ids = {str(centre.get("school_id")) for centre in centres if centre.get("school_id")}
        if decided_school_id not in allowed_ids:
            raise ValueError("The deterministic school is not in the selected context")
        if decided_school_id not in explanation.referenced_school_ids:
            raise ValueError("The grounded response omitted the decided school")
        if any(school_id not in allowed_ids for school_id in explanation.referenced_school_ids):
            raise ValueError("The grounded response referenced an unselected school")
        return explanation.answer, "llm_grounded", None
    except Exception as exc:
        return deterministic_answer, "deterministic_fallback", type(exc).__name__


def explain_school_comparison(
    question: str,
    task: Literal["ranking", "comparison", "tradeoffs", "provenance"],
    centres: list[dict],
    profile: dict | None,
    deterministic_answer: str,
    required_school_ids: list[str],
) -> tuple[str, str, str | None]:
    """Optionally phrase a comparison while requiring all relevant school IDs."""
    if not grounded_explanations_enabled() or not required_school_ids:
        return deterministic_answer, "deterministic", None
    try:
        explanation = _explain_with_openai(
            question,
            task,
            centres,
            profile,
            deterministic_answer,
            required_school_ids[0],
        )
        allowed_ids = {str(centre.get("school_id")) for centre in centres if centre.get("school_id")}
        referenced = set(explanation.referenced_school_ids)
        if any(school_id not in allowed_ids for school_id in referenced):
            raise ValueError("The grounded response referenced a school outside the supplied context")
        if any(school_id not in referenced for school_id in required_school_ids):
            raise ValueError("The grounded response omitted a required school")
        return explanation.answer, "llm_grounded", None
    except Exception as exc:
        return deterministic_answer, "deterministic_fallback", type(exc).__name__
