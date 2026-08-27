"""Optional grounded explanations for deterministic school decisions."""

from __future__ import annotations

import json
import os
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from stage1.preference_schema import sync_preference_schema


class GroundedExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=1800)
    referenced_school_ids: list[str]


class WebEvidenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=800)
    citation_ids: list[str]
    evidence_available: bool


def grounded_explanations_enabled() -> bool:
    return os.getenv("OPENAI_GROUNDED_EXPLANATIONS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def web_rag_answers_enabled() -> bool:
    if os.getenv("WEB_RAG_ANSWER_MODE", "deterministic").strip().lower() == "agent":
        return False
    return os.getenv("OPENAI_WEB_RAG_ANSWERS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _focused_web_passage(question: str, text: str, *, window_words: int = 28) -> str:
    """Keep evidence-rich windows so facts are not buried in long mixed-content chunks."""
    lowered = question.casefold()
    if "language" in lowered or "languages" in lowered:
        anchors = r"\b(?:english|chinese|mandarin|malay|tamil|bilingual|dual-language|speech\s*&\s*drama)\b"
    elif any(term in lowered for term in ("fee", "fees", "cost", "subsid")):
        anchors = r"(?:\$|sgd)\s*\d|\b(?:fees?|subsid(?:y|ies)|full day|half day)\b"
    elif any(term in lowered for term in ("outdoor", "playground", "garden")):
        anchors = r"\b(?:outdoor|playground|garden)\b"
    elif "curriculum" in lowered:
        anchors = r"\b(?:curriculum|literature-based|activity-based|play-based|thematic|montessori|reggio|learn through play)\b"
    elif any(term in lowered for term in ("enrichment", "activities", "activity", "experience")):
        anchors = r"\b(?:enrichment|s\.t\.e\.a\.m|steam|coding|robotics|field trips?|electrical circuits?|activities)\b"
    else:
        return text
    words = text.split()
    folded_words = [word.casefold() for word in words]
    joined = " ".join(folded_words)
    spans = []
    character_starts = []
    offset = 0
    for word in folded_words:
        character_starts.append(offset)
        offset += len(word) + 1
    for match in re.finditer(anchors, joined, flags=re.IGNORECASE):
        anchor_index = max(
            (index for index, start in enumerate(character_starts) if start <= match.start()),
            default=0,
        )
        start = max(0, anchor_index - window_words // 2)
        end = min(len(words), start + window_words)
        spans.append((start, end))
    if not spans:
        return text
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return " ... ".join(" ".join(words[start:end]) for start, end in merged[:4])


def _answer_web_evidence_with_openai(
    question: str, school_id: str, school_name: str, matches: list[dict]
) -> WebEvidenceAnswer:
    from openai import OpenAI

    model = os.getenv(
        "OPENAI_WEB_RAG_MODEL", os.getenv("OPENAI_EXPLANATION_MODEL", "gpt-4o-mini")
    ).strip() or "gpt-4o-mini"
    timeout = float(os.getenv("OPENAI_WEB_RAG_TIMEOUT_SECONDS", "8"))
    passages = [
        {
            "citation_id": item["citation"]["chunk_id"],
            "text": _focused_web_passage(question, item.get("text", "")),
            "source_title": item["citation"].get("title"),
            "source_url": item["citation"].get("url"),
        }
        for item in matches
    ]
    response = OpenAI(timeout=timeout).responses.parse(
        model=model,
        instructions=(
            "Answer the parent's question using only the supplied official-webpage passages. "
            "Write at most two short, direct sentences. Do not mention facts absent from the passages, "
            "do not infer that missing evidence means no, and do not discuss another school. "
            "Prefer concrete evidence over generic summaries. Preserve exact named curriculum methods, "
            "programme names, languages, activities, fee amounts, and subsidy wording when they answer the question. "
            "When evidence answers the question, set evidence_available true and cite every supporting "
            "passage by its exact citation_id. If the passages do not answer it, set evidence_available "
            "false, use no citation IDs, and say the webpage evidence is unavailable."
        ),
        input=json.dumps({
            "question": question,
            "school_id": school_id,
            "school_name": school_name,
            "passages": passages,
        }, ensure_ascii=False),
        text_format=WebEvidenceAnswer,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("The model did not return a parsed webpage-evidence answer")
    return response.output_parsed


def synthesize_web_evidence(
    question: str,
    school_id: str,
    school_name: str,
    matches: list[dict],
    deterministic_answer: str,
    deterministic_citations: list[dict],
) -> tuple[str, list[dict], str, str | None]:
    """Generate a cited answer, falling back safely on any failure."""
    if not web_rag_answers_enabled():
        return deterministic_answer, deterministic_citations, "deterministic", None
    try:
        result = _answer_web_evidence_with_openai(question, school_id, school_name, matches)
        allowed = {item["citation"]["chunk_id"]: item["citation"] for item in matches}
        if not result.evidence_available:
            raise ValueError("The model rejected evidence that passed retrieval")
        if not result.citation_ids:
            raise ValueError("An evidence answer requires at least one citation")
        if any(citation_id not in allowed for citation_id in result.citation_ids):
            raise ValueError("The model cited a passage outside the retrieved context")
        citation_ids = list(dict.fromkeys(result.citation_ids))
        citations = [{**allowed[citation_id], "evidence_scope": "school"} for citation_id in citation_ids]
        return result.answer, citations, "llm_grounded", None
    except Exception as exc:
        return deterministic_answer, deterministic_citations, "deterministic_fallback", type(exc).__name__


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
