"""Conversation controller for incremental Stage 1 preference collection."""

from __future__ import annotations

import re

from stage1.nlp_mapper import (
    LANGUAGE_KEYWORDS,
    PEDAGOGY_KEYWORDS,
    map_text_to_filters,
    merge_preference_profile,
    summarize_profile,
)
from stage1.preference_schema import sync_preference_schema
from stage1.llm_extractor import merge_preference_profile_with_llm
from stage1.grounded_explainer import explain_school_comparison, explain_school_decision, synthesize_web_evidence
from stage1.intent_router import classify_intent
from stage1.web_rag import retrieve, retrieve_general_evidence

REQUIRED_MARKERS = ("must", "need", "required", "require", "essential")
PREFERRED_MARKERS = ("prefer", "preferred", "preference", "useful", "optional", "nice to have")
RECOMMEND_SELECTED_MARKERS = ("recommend", "best", "choose", "pick")


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _distance_acknowledgement(profile: dict) -> str | None:
    distance = profile.get("hard_constraints", {}).get("max_distance_km")
    if distance is None:
        return None
    return (
        f"Distance preference updated. I’ll only recommend preschools within "
        f"{float(distance):g} km of your home. Add another preference or click "
        "show recommendations."
    )


def _is_selected_school_question(text: str) -> bool:
    return "selected" in text and "preschool" in text and _contains_any(text, RECOMMEND_SELECTED_MARKERS)


def _is_suitability_question(text: str) -> bool:
    refers_to_school = "school" in text or "preschool" in text
    asks_suitability = "suitable" in text or "good fit" in text or "right for me" in text
    return refers_to_school and asks_suitability


def _find_closest(centres: list[dict]) -> tuple[str, dict | None]:
    if not centres:
        return "I need grounded preschool records with home distances before I can identify the nearest school.", None
    located = [centre for centre in centres if centre.get("distance_km") is not None]
    if not located:
        return "I cannot compare the preschools because their home distances are unavailable.", None
    closest = min(
        located,
        key=lambda centre: (float(centre["distance_km"]), str(centre.get("name") or "")),
    )
    distance = float(closest["distance_km"])
    distance_text = (
        "at the same mapped location as your postal code"
        if distance < 0.005
        else f"approximately {distance:.2f} km from your home"
    )
    return (
        f"{closest.get('name') or 'The nearest preschool'} is the closest preschool "
        f"in the grounded catalogue, {distance_text}. This is a location result, not an eligibility assessment.",
        closest,
    )


def _metric_summary(school: dict) -> str:
    details = [f"{float(school.get('match_score') or 0):.0f}% preference match"]
    if school.get("net_monthly_fee") is not None:
        details.append(f"${float(school['net_monthly_fee']):,.0f}/month estimated cost")
    if school.get("distance_km") is not None:
        details.append(f"{float(school['distance_km']):.2f} km from home")
    return ", ".join(details)


def _explain_top_ranked(centres: list[dict]) -> tuple[str, list[dict]]:
    if not centres:
        return "Please show recommendations first so I can explain the ranking.", []
    top = centres[0]
    name = top.get("name") or "The first preschool"
    answer = f"{name} is ranked first among the current eligible results with {_metric_summary(top)}."
    strengths = top.get("strengths") or []
    tradeoffs = top.get("tradeoffs") or []
    if strengths:
        answer += f" Its recorded preference matches are {', '.join(strengths)}."
    if tradeoffs:
        answer += f" Its recorded trade-offs are {', '.join(tradeoffs)}."
    confidence = top.get("profile_confidence")
    if confidence is not None:
        answer += f" Evidence coverage for the scored preferences is {float(confidence) * 100:.0f}%."
    answer += " Stage 1 orders by preference-match score, then evidence confidence; cost and distance do not change this ranking."
    return answer, [top]


def _compare_selected(centres: list[dict]) -> tuple[str, list[dict]]:
    if len(centres) < 2:
        return "Select at least two preschools in the Results panel so I can compare them.", []
    sections = []
    for school in centres:
        text = f"{school.get('name') or 'Preschool'}: {_metric_summary(school)}"
        if school.get("strengths"):
            text += f"; strengths: {', '.join(school['strengths'])}"
        if school.get("tradeoffs"):
            text += f"; trade-offs: {', '.join(school['tradeoffs'])}"
        sections.append(text + ".")
    return " ".join(sections), centres


def _explain_tradeoffs(centres: list[dict]) -> tuple[str, list[dict]]:
    if not centres:
        return "Select at least one preschool in the Results panel so I can explain its trade-offs.", []
    sections = []
    for school in centres:
        tradeoffs = school.get("tradeoffs") or []
        if tradeoffs:
            sections.append(f"{school.get('name') or 'This preschool'} has recorded trade-offs for {', '.join(tradeoffs)}.")
        else:
            sections.append(f"{school.get('name') or 'This preschool'} has no recorded preference mismatches, although missing evidence may still limit the assessment.")
    return " ".join(sections), centres


def _explain_provenance(centres: list[dict]) -> tuple[str, list[dict]]:
    if not centres:
        return "Select at least one preschool in the Results panel so I can explain its evidence sources.", []
    sections = []
    for school in centres:
        breakdown = school.get("match_breakdown") or []
        if not breakdown:
            sections.append(f"{school.get('name') or 'This preschool'} has no weighted preference evidence to explain.")
            continue
        facts = []
        for item in breakdown:
            label = item["attribute"].split(":", 1)[0].replace("_", " ")
            if item.get("evidence_state") == "unknown":
                facts.append(f"{label}: evidence unavailable")
            else:
                source = item.get("source") or "unknown source"
                reliability = item.get("source_reliability") or "unknown reliability"
                freshness = item.get("freshness") or "unknown freshness"
                facts.append(f"{label}: {source}, {reliability} reliability, {freshness} freshness")
        sections.append(f"{school.get('name') or 'This preschool'} — " + "; ".join(facts) + ".")
    return " ".join(sections), centres


def _answer_web_evidence(
    text: str, centres: list[dict], web_rag_index: dict | None
) -> tuple[str, list[dict], str, str | None]:
    if not centres:
        return "Select one preschool in the Results panel so I can search its official webpage.", [], "deterministic", None
    if len(centres) > 1:
        return "Select only one preschool so webpage evidence cannot be mixed between schools.", [], "deterministic", None
    school = centres[0]
    school_id = school.get("school_id")
    if not school_id or not web_rag_index:
        return "Webpage evidence is unavailable for this preschool.", [], "deterministic", None
    matches = retrieve(web_rag_index, str(school_id), text, limit=3)
    if not matches:
        return (
            f"I could not find relevant webpage evidence for {school.get('name') or 'this preschool'}. "
            "That means the information is unavailable, not that the answer is no.",
            [], "deterministic", None,
        )
    query_terms = {
        token for token in re.findall(r"[a-z0-9]+", text.casefold())
        if token not in {
            "a", "an", "are", "does", "do", "for", "have", "how", "is", "it", "school",
            "preschool", "selected", "the", "this", "use", "uses", "what", "which", "branch",
            "centre", "center", "kind", "taught",
        }
    }
    candidates: list[tuple[float, int, str, dict]] = []
    seen: set[str] = set()
    for match_index, match in enumerate(matches):
        raw = " ".join(str(match.get("text") or "").split())
        sentences = re.split(r"(?<=[.!?])\s+|\s+[|•]\s+", raw)
        for sentence_index, sentence in enumerate(sentences):
            sentence = sentence.strip(" -")
            words = sentence.split()
            if len(words) < 5:
                continue
            sentence_terms = set(re.findall(r"[a-z0-9]+", sentence.casefold()))
            overlap = len(query_terms & sentence_terms)
            intent_bonus = 0
            if "curriculum" in query_terms:
                intent_bonus = 2 * len(sentence_terms & {
                    "curriculum", "montessori", "reggio", "literature", "activity", "play", "inquiry",
                })
            elif "outdoor" in query_terms:
                intent_bonus = 2 * len(sentence_terms & {"outdoor", "garden", "playground"})
            elif query_terms & {"fee", "fees", "cost", "price"}:
                intent_bonus = 2 * int(bool(sentence_terms & {"fee", "fees", "cost", "price", "subsidies"}))
                intent_bonus += 4 * int(bool(re.search(r"(?:\$|sgd)\s*\d", sentence.casefold())))
            elif query_terms & {"language", "languages"}:
                intent_bonus = 4 * len(sentence_terms & {
                    "english", "chinese", "mandarin", "malay", "tamil", "bilingual",
                })
            score = overlap * 3 + intent_bonus + float(match.get("relevance") or 0) - match_index * 0.1 - sentence_index * 0.01
            if score <= 0:
                continue
            key = re.sub(r"\W+", " ", sentence.casefold()).strip()
            if key in seen:
                continue
            seen.add(key)
            candidates.append((score, match_index, sentence, match))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    passages = []
    citations = []
    used_chunks: set[str] = set()
    total_words = 0
    for _, _, sentence, match in candidates:
        words = sentence.split()
        if len(words) > 18:
            focus_terms = set(query_terms)
            if "curriculum" in query_terms:
                focus_terms.update({"curriculum", "montessori", "reggio", "literature-based", "activity-based", "play-based", "inquiry"})
            elif "outdoor" in query_terms:
                focus_terms.update({"outdoor", "garden", "playground"})
            elif query_terms & {"fee", "fees", "cost", "price"}:
                focus_terms.update({"fee", "fees", "cost", "price", "subsidies"})
            elif query_terms & {"language", "languages"}:
                focus_terms.update({"english", "chinese", "mandarin", "malay", "tamil", "bilingual"})
            anchor = next(
                (index for index, word in enumerate(words) if word.casefold().strip(".,:;()[]") in focus_terms),
                0,
            )
            start = max(0, anchor - 5)
            end = min(len(words), start + 18)
            start = max(0, end - 18)
            sentence = ("..." if start else "") + " ".join(words[start:end]).rstrip(",;:") + ("..." if end < len(words) else "")
            words = sentence.split()
        sentence = re.sub(r"\b_?DSC\d+\b|\bpartners-[a-z-]+\b", "", sentence, flags=re.IGNORECASE)
        if "outdoor" in query_terms:
            sentence = re.split(r"\s+Age group:\s*", sentence, maxsplit=1, flags=re.IGNORECASE)[0]
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if passages and total_words + len(words) > 65:
            continue
        citation = match["citation"]
        chunk_id = citation["chunk_id"]
        if chunk_id not in used_chunks:
            citations.append({**citation, "evidence_scope": "school"})
            used_chunks.add(chunk_id)
        marker = citations.index(next(item for item in citations if item["chunk_id"] == chunk_id)) + 1
        passages.append(f"{sentence} [{marker}]")
        total_words += len(words)
        if len(passages) == 1:
            break
    if not passages:
        fallback = (
            f"I found a relevant page for {school.get('name') or 'this preschool'}, "
            "but not a concise passage that answers the question."
        )
        return synthesize_web_evidence(
            text, str(school_id), school.get("name") or "this preschool", matches, fallback, []
        )
    lead = "According to the preschool's official webpage, "
    if "curriculum" in query_terms:
        lead += "its curriculum includes the following: "
    answer = lead + " ".join(passages)
    return synthesize_web_evidence(
        text, str(school_id), school.get("name") or "this preschool", matches, answer, citations
    )


def _answer_general_knowledge(
    text: str,
    general_knowledge_index: dict | None,
    topics: list | None = None,
    relationship: str = "unknown",
) -> tuple[str, list[dict]]:
    if not general_knowledge_index:
        return "General early-childhood guidance is unavailable.", []
    lowered = text.lower()
    structured_topics = topics or []
    if relationship == "different_categories" and len(structured_topics) >= 2:
        chunks = list(general_knowledge_index.get("chunks", []))
        selected: list[tuple[object, dict]] = []
        for topic in structured_topics:
            name = str(getattr(topic, "name", "") or "").strip()
            normalized = name.lower().replace("2.0", "").strip()
            match = next(
                (
                    item for item in chunks
                    if normalized
                    and (
                        normalized in str(item.get("topic") or "").lower()
                        or str(item.get("topic") or "").lower().replace("2.0", "").strip() in normalized
                    )
                ),
                None,
            )
            if match and all(match.get("chunk_id") != item.get("chunk_id") for _, item in selected):
                selected.append((topic, match))
        if len(selected) >= 2:
            category_labels = {
                "pedagogy": "an educational approach",
                "curriculum_framework": "a curriculum framework",
                "quality_framework": "a quality-improvement framework",
                "subsidy_policy": "a subsidy policy",
                "school_attribute": "a school attribute",
                "other": "an early-childhood concept",
            }
            explanations = []
            for topic, item in selected:
                category = str(getattr(topic, "category", "other"))
                label = category_labels.get(category, "an early-childhood concept")
                explanations.append(
                    f"{getattr(topic, 'name', item.get('topic'))} is {label}: "
                    f"{str(item.get('text') or '').strip()}"
                )
            answer = (
                "These are different kinds of things, so they are not direct alternatives. "
                + " ".join(explanations)
                + " Consider each on its own terms rather than treating one as a substitute for the other."
            )
            citations = [
                {
                    "url": item["source_url"],
                    "title": item.get("title") or item["source_url"],
                    "retrieved_at": item["retrieved_at"],
                    "chunk_id": item["chunk_id"],
                    "evidence_scope": "general",
                    "authority": item.get("authority"),
                    "effective_from": item.get("effective_from"),
                }
                for _, item in selected
            ]
            return answer, citations
    if "montessori" in lowered and "spark" in lowered:
        chunks = list(general_knowledge_index.get("chunks", []))
        montessori = next(
            (item for item in chunks if "montessori" in str(item.get("topic") or "").lower()),
            None,
        )
        spark = next(
            (item for item in chunks if "spark" in str(item.get("topic") or "").lower()),
            None,
        )
        if montessori and spark:
            answer = (
                "Montessori and SPARK are different kinds of things, so they are not direct "
                "alternatives. Montessori is an educational approach: "
                f"{str(montessori.get('text') or '').strip()} "
                "SPARK 2.0 is a preschool quality-improvement framework: "
                f"{str(spark.get('text') or '').strip()} "
                "In practical terms, Montessori describes how a preschool may organise teaching "
                "and learning, while SPARK concerns how a preschool reflects on and improves "
                "quality. A preschool may therefore use a Montessori approach and also participate "
                "in SPARK. Consider them separately: whether the educational approach suits your "
                "child, and what current quality evidence the specific preschool can provide."
            )
            citations = [
                {
                    "url": item["source_url"],
                    "title": item.get("title") or item["source_url"],
                    "retrieved_at": item["retrieved_at"],
                    "chunk_id": item["chunk_id"],
                    "evidence_scope": "general",
                    "authority": item.get("authority"),
                    "effective_from": item.get("effective_from"),
                }
                for item in (montessori, spark)
            ]
            return answer, citations
    pedagogy_names = ("montessori", "reggio emilia", "play-based", "play based")
    is_comparison = (
        ("difference between" in lowered or "compare" in lowered)
        and sum(name in lowered for name in pedagogy_names) >= 2
    )
    matches = retrieve_general_evidence(
        general_knowledge_index, text, limit=2, min_relevance=0.1 if is_comparison else 0.25
    )
    if not matches:
        return "I could not find relevant guidance in the curated early-childhood knowledge base.", []
    selected = matches[:2] if is_comparison else matches[:1]
    answer = " ".join(str(item.get("text") or "").strip() for item in selected)
    citations = [{**item["citation"], "evidence_scope": "general"} for item in selected]
    return answer, citations


def _comparison_turn(profile: dict, text: str, task: str, answer: str, centres: list[dict]) -> dict:
    required_ids = [str(centre["school_id"]) for centre in centres if centre.get("school_id")]
    grounded, method, fallback = explain_school_comparison(
        text, task, centres, profile, answer, required_ids  # type: ignore[arg-type]
    )
    profile["explanation_method"] = method
    if fallback:
        profile["explanation_fallback_reason"] = fallback
    else:
        profile.pop("explanation_fallback_reason", None)
    return {
        "profile": profile,
        "understood": summarize_profile(profile),
        "status": "comparison",
        "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")),
        "question": grounded,
    }


def _recommend_selected(centres: list[dict]) -> str:
    if not centres:
        return "Please select at least one preschool in the Results panel, then ask me again."
    ranked = sorted(
        centres,
        key=lambda centre: (
            -float(centre.get("match_score") or 0),
            float(centre.get("net_monthly_fee")) if centre.get("net_monthly_fee") is not None else float("inf"),
            float(centre.get("distance_km")) if centre.get("distance_km") is not None else float("inf"),
            str(centre.get("name") or ""),
        ),
    )
    best = ranked[0]
    details = [f"a {float(best.get('match_score') or 0):.0f}% preference match"]
    if best.get("net_monthly_fee") is not None:
        details.append(f"an estimated monthly cost of ${float(best['net_monthly_fee']):,.0f}")
    if best.get("distance_km") is not None:
        details.append(f"a distance of {float(best['distance_km']):.2f} km from home")
    reason = ", ".join(details)
    return f"I recommend {best.get('name') or 'the highest-ranked preschool'} based on {reason}. Preference match is prioritised, with cost and distance used as tie-breakers."


def _recommended_school_id(centres: list[dict]) -> str | None:
    if not centres:
        return None
    ranked = sorted(
        centres,
        key=lambda centre: (
            -float(centre.get("match_score") or 0),
            float(centre.get("net_monthly_fee")) if centre.get("net_monthly_fee") is not None else float("inf"),
            float(centre.get("distance_km")) if centre.get("distance_km") is not None else float("inf"),
            str(centre.get("name") or ""),
        ),
    )
    return ranked[0].get("school_id")


def _assess_selected(centres: list[dict]) -> str:
    if not centres:
        return "Please select one preschool in the Results panel, then ask me again."
    if len(centres) > 1:
        return "You have selected more than one preschool. Select only the school you want me to assess, or ask me which selected preschool I recommend."

    school = centres[0]
    name = school.get("name") or "This preschool"
    score = float(school.get("match_score") or 0)
    verdict = "appears suitable" if score >= 70 else "may be suitable" if score >= 50 else "may not be the strongest fit"
    evidence = [f"an {score:.0f}% preference match"]
    strengths = school.get("strengths") or []
    tradeoffs = school.get("tradeoffs") or []
    if strengths:
        evidence.append(f"strengths in {', '.join(strengths)}")
    if school.get("net_monthly_fee") is not None:
        evidence.append(f"an estimated monthly cost of ${float(school['net_monthly_fee']):,.0f}")
    if school.get("distance_km") is not None:
        evidence.append(f"a distance of {float(school['distance_km']):.2f} km from home")
    answer = f"{name} {verdict} based on " + ", ".join(evidence) + "."
    if tradeoffs:
        answer += f" Consider these trade-offs: {', '.join(tradeoffs)}."
    return answer


def _resolve_pending(current: dict, text: str) -> tuple[dict, bool]:
    pending = current.get("pending") if current else None
    lowered = text.lower()
    if not pending:
        return current, False
    required = _contains_any(lowered, REQUIRED_MARKERS)
    preferred = _contains_any(lowered, PREFERRED_MARKERS)
    if not required and not preferred:
        return current, False

    profile = merge_preference_profile(current, "")
    kind, value = pending["kind"], pending["value"]
    if kind == "language":
        profile["hard_constraints"].pop("language", None)
        profile["preferences"].pop(f"language:{value}", None)
        if required:
            profile["hard_constraints"]["language"] = value
        else:
            profile["preferences"][f"language:{value}"] = {"value": value, "weight": 4, "desired": True}
    elif kind == "pedagogy":
        profile["preferences"]["pedagogy"] = {"value": value, "weight": 5 if required else 4, "desired": True}
    profile.pop("pending", None)
    profile["recognized"] = [value.lower()]
    return sync_preference_schema(profile), True


def update_conversation(current: dict | None, text: str, selected_centres: list[dict] | None = None, eligible_centres: list[dict] | None = None, web_rag_index: dict | None = None, general_knowledge_index: dict | None = None, classified_intent=None) -> dict:
    """Update a profile and determine the next clarification or action."""
    lowered = (text or "").strip().lower()
    contextual_answer = None
    contextual_task = None
    decided_school_id = None
    intent = classified_intent or classify_intent(text)
    if intent.intent == "needs_clarification":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"] = intent.intent
        profile["intent_method"] = intent.method
        return {"profile": profile, "understood": summarize_profile(profile), "status": "needs_clarification", "ready_to_search": False, "question": intent.clarification}
    if intent.intent == "find_closest_preschool":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"] = intent.intent
        profile["intent_method"] = intent.method
        answer, closest = _find_closest(eligible_centres or [])
        if closest:
            profile["active_school"] = {
                key: closest.get(key) for key in ("school_id", "centre_code", "name") if closest.get(key) is not None
            }
        return {"profile": profile, "understood": summarize_profile(profile), "status": "comparison", "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")), "question": answer}
    if intent.intent == "explain_top_ranked_preschool":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        answer, context = _explain_top_ranked(eligible_centres or [])
        return _comparison_turn(profile, text, "ranking", answer, context)
    if intent.intent == "compare_selected_preschools":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        answer, context = _compare_selected(selected_centres or [])
        return _comparison_turn(profile, text, "comparison", answer, context)
    if intent.intent == "explain_selected_tradeoffs":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        answer, context = _explain_tradeoffs(selected_centres or [])
        return _comparison_turn(profile, text, "tradeoffs", answer, context)
    if intent.intent == "explain_evidence_provenance":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        answer, context = _explain_provenance(selected_centres or [])
        return _comparison_turn(profile, text, "provenance", answer, context)
    if intent.intent == "ask_selected_school_evidence":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        answer, citations, answer_method, fallback_reason = _answer_web_evidence(text, selected_centres or [], web_rag_index)
        return {
            "profile": profile,
            "understood": summarize_profile(profile),
            "status": "web_evidence",
            "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")),
            "question": answer,
            "citations": citations,
            "evidence_scope": "school" if citations else "unavailable",
            "ranking_affected": False,
            "web_answer_method": answer_method,
            "web_answer_fallback_reason": fallback_reason,
        }
    if intent.intent == "ask_general_knowledge":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        answer, citations = _answer_general_knowledge(
            text, general_knowledge_index, intent.topics, intent.relationship
        )
        return {
            "profile": profile, "understood": summarize_profile(profile), "status": "general_knowledge",
            "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")),
            "question": answer, "citations": citations,
            "evidence_scope": "general" if citations else "unavailable", "ranking_affected": False,
        }
    if intent.intent == "ask_combined_evidence":
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        profile["intent"], profile["intent_method"] = intent.intent, intent.method
        school_answer, school_citations, method, fallback = _answer_web_evidence(text, selected_centres or [], web_rag_index)
        general_answer, general_citations = _answer_general_knowledge(
            text, general_knowledge_index, intent.topics, intent.relationship
        )
        citations = school_citations + general_citations
        return {
            "profile": profile, "understood": summarize_profile(profile), "status": "combined_evidence",
            "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")),
            "question": f"School evidence: {school_answer} General guidance: {general_answer}",
            "citations": citations, "evidence_scope": "combined" if citations else "unavailable",
            "ranking_affected": False, "web_answer_method": method,
            "web_answer_fallback_reason": fallback,
        }
    if intent.intent == "recommend_selected_preschool" or _is_selected_school_question(lowered):
        contextual_answer = _recommend_selected(selected_centres or [])
        contextual_task = "recommendation"
        decided_school_id = _recommended_school_id(selected_centres or [])
    elif intent.intent == "assess_selected_preschool" or _is_suitability_question(lowered):
        contextual_answer = _assess_selected(selected_centres or [])
        contextual_task = "suitability"
        if len(selected_centres or []) == 1:
            decided_school_id = (selected_centres or [])[0].get("school_id")
    if contextual_answer:
        profile = sync_preference_schema(current or {"hard_constraints": {}, "preferences": {}, "recognized": []})
        answer, explanation_method, fallback_reason = explain_school_decision(
            text,
            contextual_task,
            selected_centres or [],
            profile,
            contextual_answer,
            decided_school_id,
        )
        profile["explanation_method"] = explanation_method
        if fallback_reason:
            profile["explanation_fallback_reason"] = fallback_reason
        else:
            profile.pop("explanation_fallback_reason", None)
        return {
            "profile": profile,
            "understood": summarize_profile(profile),
            "status": "comparison",
            "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")),
            "question": answer,
        }
    profile, resolved = _resolve_pending(current or {}, lowered)
    if resolved:
        queue = profile.get("pending_queue", [])
        if queue:
            profile["pending"] = queue.pop(0)
            if queue:
                profile["pending_queue"] = queue
            else:
                profile.pop("pending_queue", None)
            pending = profile["pending"]
            wording = "required or merely preferred" if pending["kind"] == "language" else "essential or merely preferred"
            return {
                "profile": profile,
                "understood": summarize_profile(profile),
                "status": "needs_clarification",
                "ready_to_search": False,
                "question": f"Next, is {pending['value']} {wording}?",
            }
        understood = summarize_profile(profile)
        return {
            "profile": profile,
            "understood": understood,
            "status": "ready_to_search",
            "ready_to_search": True,
            "question": "Preference updated. Add another preference or click show recommendations.",
        }

    if current and current.get("pending"):
        pending = current["pending"]
        wording = "required or merely preferred" if pending["kind"] == "language" else "essential or merely preferred"
        return {
            "profile": current,
            "understood": summarize_profile(current),
            "status": "needs_clarification",
            "ready_to_search": False,
            "question": f"Before we continue, is {pending['value']} {wording}?",
        }

    incoming = map_text_to_filters(text)
    profile = merge_preference_profile_with_llm(current, text)
    if profile.get("clarification_needed"):
        return {
            "profile": profile,
            "understood": summarize_profile(profile),
            "status": "needs_clarification",
            "ready_to_search": False,
            "question": profile["clarification_needed"],
        }
    if not profile.get("hard_constraints") and not profile.get("preferences"):
        if profile.get("unsupported_preferences"):
            unsupported = ", ".join(
                item["attribute"].replace("_", " ") for item in profile["unsupported_preferences"]
            )
            return {
                "profile": profile,
                "understood": summarize_profile(profile),
                "status": "unsupported_preferences",
                "ready_to_search": False,
                "question": f"I noted {unsupported}, but the current school data cannot verify or rank it. Add a supported preference such as language, SPARK, transport, halal food, full-day care, or maximum home distance.",
            }
        return {
            "profile": profile,
            "understood": [],
            "status": "needs_clarification",
            "ready_to_search": False,
            "question": "Tell me a preference such as Montessori, language, SPARK, transport, halal food, or full-day care.",
        }

    explicit_importance = _contains_any(lowered, REQUIRED_MARKERS + PREFERRED_MARKERS)
    if not explicit_importance:
        ambiguities = []
        for phrase, language in LANGUAGE_KEYWORDS.items():
            if phrase in lowered:
                ambiguities.append({"kind": "language", "value": language})
                break
        for phrase, pedagogy in PEDAGOGY_KEYWORDS.items():
            if phrase in lowered:
                ambiguities.append({"kind": "pedagogy", "value": pedagogy})
                break
        if ambiguities:
            profile["pending"] = ambiguities.pop(0)
            if ambiguities:
                profile["pending_queue"] = ambiguities
            pending = profile["pending"]
            wording = "required or merely preferred" if pending["kind"] == "language" else "essential or merely preferred"
            return {
                "profile": profile,
                "understood": summarize_profile(profile),
                "status": "needs_clarification",
                "ready_to_search": False,
                "question": f"Is {pending['value']} {wording}?",
            }

    if incoming.get("unsupported_preferences"):
        unsupported = ", ".join(
            item["attribute"].replace("_", " ") for item in incoming["unsupported_preferences"]
        )
        return {
            "profile": profile,
            "understood": summarize_profile(profile),
            "status": "ready_to_search",
            "ready_to_search": True,
            "question": f"I noted {unsupported}, but the current school data cannot verify or rank it. Your supported preferences are still available. Add another preference or click show recommendations.",
        }

    understood = summarize_profile(profile)
    if incoming.get("hard_constraints", {}).get("max_distance_km") is not None:
        question = _distance_acknowledgement(profile)
    else:
        question = "Would you like to add another preference or show recommendations?"
    return {
        "profile": profile,
        "understood": understood,
        "status": "ready_to_search",
        "ready_to_search": True,
        "question": question,
    }
