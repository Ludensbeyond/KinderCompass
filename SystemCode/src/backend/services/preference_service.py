from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from SystemCode.src.backend.agents.config import WebRagAnswerMode, get_web_rag_answer_mode
from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    ConversationRequestContext,
    EvidenceCitation,
    EvidenceIndexContext,
    SelectedSchoolAgentRequest,
)
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from SystemCode.src.backend.services.decision_state_service import enrich_decision_state
from stage1.conversation import update_conversation
from stage1.intent_router import classify_intent
from stage1.nlp_mapper import summarize_profile
from stage1.scorer import rank_schools
from stage1.web_rag import load_json


class PreferenceService:
    def __init__(
        self, schools: SchoolRepository, evaluation: EvaluationService,
        locations: LocationService, repo_root: Path,
    ):
        self.schools = schools
        self.evaluation = evaluation
        self.locations = locations
        self.repo_root = repo_root

    @staticmethod
    def _run_selected_school_agent(
        index: dict[str, Any], request: SelectedSchoolAgentRequest,
        deterministic_answer: str, deterministic_citations: list[EvidenceCitation],
    ) -> Any:
        # Keep LangGraph and its provider-facing dependencies out of the
        # deterministic request path.
        from SystemCode.src.backend.agents.graph import run_selected_school_evidence_graph

        return run_selected_school_evidence_graph(
            index,
            request,
            deterministic_answer=deterministic_answer,
            deterministic_citations=deterministic_citations,
        )

    def _apply_selected_school_answer_mode(
        self, result: dict[str, Any], *, message: str,
        selected: list[dict[str, Any]], web_index: dict | None,
    ) -> dict[str, Any]:
        """Map internal answer metadata and optionally replace it via the graph."""

        result["answer_method"] = result.get("web_answer_method") or "deterministic"
        result["fallback_reason"] = result.get("web_answer_fallback_reason")
        if get_web_rag_answer_mode() is not WebRagAnswerMode.AGENT:
            return result

        try:
            if len(selected) != 1 or not web_index:
                raise ValueError("agent execution requires one authoritative school and an evidence index")
            school = selected[0]
            school_id = str(school.get("school_id") or "")
            request = SelectedSchoolAgentRequest(
                question=message,
                school_id=school_id,
                school_name=str(school.get("name") or "this preschool"),
            )
            deterministic_citations = [
                EvidenceCitation(
                    citation_id=str(citation["chunk_id"]),
                    school_id=school_id,
                    chunk_id=str(citation["chunk_id"]),
                    url=str(citation["url"]),
                    title=str(citation["title"]),
                    retrieved_at=citation["retrieved_at"],
                )
                for citation in result.get("citations", [])
            ]
            agent_result = self._run_selected_school_agent(
                web_index, request, result["question"], deterministic_citations,
            )
            result["question"] = agent_result.answer
            result["citations"] = [
                {
                    "url": citation.url,
                    "title": citation.title,
                    "retrieved_at": citation.retrieved_at.isoformat(),
                    "chunk_id": citation.chunk_id,
                    "evidence_scope": "school",
                }
                for citation in agent_result.citations
            ]
            result["answer_method"] = agent_result.answer_method
            result["fallback_reason"] = agent_result.fallback_reason
            result["evidence_scope"] = "school" if agent_result.citations else "unavailable"
            result["evidence_category"] = (
                "school_published_claim" if agent_result.citations else "unknown"
            )
        except Exception as exc:
            result["answer_method"] = "deterministic_fallback"
            result["fallback_reason"] = type(exc).__name__
        return result

    def _resources(self) -> tuple[dict | None, dict | None]:
        configured = os.getenv("WEB_RAG_INDEX_PATH", "").strip()
        web_path = Path(configured) if configured else self.repo_root / "SystemCode/src/backend/output/web_rag_pilot_index.json"
        general_path = self.repo_root / "SystemCode/src/backend/resources/web_rag/general_knowledge_index.json"
        def safe_load(path: Path):
            try:
                return load_json(path) if path.is_file() else None
            except (OSError, ValueError):
                return None
        return safe_load(web_path), safe_load(general_path)

    def _rebuild(
        self, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails | None,
    ) -> list[dict[str, Any]]:
        if not school_ids:
            return []
        if family:
            return self.evaluation.evaluate(school_ids, profile, family, include_ineligible=True)
        return rank_schools(profile, self.schools.get_many(school_ids), limit=len(school_ids))

    @staticmethod
    def _context_school(record: Any) -> AuthoritativeSchoolContext:
        if hasattr(record, "model_dump"):
            facts = record.model_dump(mode="json")
        else:
            # Ranking and distance helpers return ordinary dictionaries. Pydantic
            # converts any dates nested in those dictionaries to JSON-safe values.
            from pydantic import TypeAdapter

            facts = TypeAdapter(dict[str, Any]).dump_python(dict(record), mode="json")
        return AuthoritativeSchoolContext(
            school_id=str(facts.get("school_id") or ""), facts=facts,
        )

    def build_conversation_context(
        self, *, message: str, profile: dict[str, Any] | None,
        selected_school_ids: list[str], eligible_school_ids: list[str],
        excluded_school_ids: list[str], family: FamilyDetails | None,
        home_postal_code: str | None, include_full_catalogue: bool = False,
    ) -> ConversationRequestContext:
        """Resolve all browser identifiers into one bounded server-owned context."""

        current = deepcopy(profile or {})
        active = current.get("active_school") or {}
        selected_ids = selected_school_ids or (
            [active["school_id"]] if active.get("school_id") else []
        )
        selected = self._rebuild(selected_ids, current, family)
        if active.get("school_id") and selected:
            resolved_active = next(
                (item for item in selected if item.get("school_id") == active["school_id"]),
                None,
            )
            if resolved_active:
                current["active_school"] = {
                    "school_id": resolved_active["school_id"],
                    "name": resolved_active["name"],
                }
        eligible = self._rebuild(eligible_school_ids, current, family)
        effective_eligible_ids = list(eligible_school_ids)
        if include_full_catalogue and not eligible:
            eligible = self.schools.all()
            effective_eligible_ids = [str(item["school_id"]) for item in eligible]
        excluded = self._rebuild(excluded_school_ids, current, family)

        if home_postal_code:
            if selected:
                selected = self.locations.attach_distances(selected, home_postal_code)
            if eligible:
                eligible = self.locations.attach_distances(eligible, home_postal_code)
            if excluded:
                excluded = self.locations.attach_distances(excluded, home_postal_code)

        web_index, general_index = self._resources()
        return ConversationRequestContext(
            message=message,
            profile=current,
            family=family.model_dump() if family else None,
            home_postal_code=home_postal_code,
            selected_school_ids=selected_ids,
            eligible_school_ids=effective_eligible_ids,
            excluded_school_ids=excluded_school_ids,
            selected_schools=[self._context_school(item) for item in selected],
            eligible_schools=[self._context_school(item) for item in eligible],
            excluded_schools=[self._context_school(item) for item in excluded],
            selected_school_evidence=EvidenceIndexContext(
                scope="school", available=web_index is not None, index=web_index,
            ),
            general_knowledge_evidence=EvidenceIndexContext(
                scope="general", available=general_index is not None, index=general_index,
            ),
            catalogue_version=self.schools.catalogue_version,
        )

    def _what_if(
        self, message: str, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails | None,
        baseline: list[Any] | None = None,
    ) -> dict[str, Any]:
        if not family or not school_ids:
            return self._direct_answer(profile, "Show recommendations first so I can run a fee or eligibility what-if scenario.")
        changes: dict[str, Any] = {}
        hours = re.search(r"(?:working|work) hours(?:\s+per\s+month)?\D{0,12}(\d+(?:\.\d+)?)", message, re.I)
        income = re.search(r"(?:income|ghi)\D{0,12}(\d+(?:\.\d+)?)", message, re.I)
        if hours:
            changes["working_hours_per_month"] = float(hours.group(1))
        if income:
            changes["gross_household_income"] = float(income.group(1))
        if not changes:
            return self._direct_answer(
                profile,
                "Specify a hypothetical gross monthly income or working hours per month, for example: ‘What if my working hours are 55?’",
            )
        scenario_family = family.model_copy(update=changes)
        baseline = baseline or self.evaluation.evaluate(
            school_ids, profile, family, include_ineligible=True,
        )
        scenario = self.evaluation.evaluate(school_ids, profile, scenario_family, include_ineligible=True)
        value = lambda item, key: item.get(key) if hasattr(item, "get") else getattr(item, key, None)
        baseline_by_id = {value(item, "school_id"): item for item in baseline}
        sections = []
        for changed in scenario[:5]:
            changed_id = value(changed, "school_id")
            original = baseline_by_id.get(changed_id)
            name = value(changed, "name")
            original_fee = value(original, "net_monthly_fee") if original else None
            changed_fee = value(changed, "net_monthly_fee")
            if original_fee is not None and changed_fee is not None:
                sections.append(
                    f"{name}: estimated monthly fee changes from ${original_fee:,.0f} "
                    f"to ${changed_fee:,.0f}."
                )
            else:
                status = str(value(changed, "status") or "unavailable").replace("_", " ")
                sections.append(f"{name}: scenario status is {status}.")
        assumptions = ", ".join(key.replace("_", " ") + f"={value:g}" for key, value in changes.items())
        return self._direct_answer(
            profile,
            f"What-if only ({assumptions}); your saved family details were not changed. " + " ".join(sections),
            status="what_if",
            evidence_category="calculated_estimate",
        )

    def _explain_exclusion(
        self, message: str, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails | None,
        evaluated: list[Any] | None = None,
    ) -> dict[str, Any]:
        if not school_ids or not family:
            return self._direct_answer(profile, "No Stage 2 exclusions are available for the current recommendation result.")
        evaluated = evaluated or self.evaluation.evaluate(
            school_ids, profile, family, include_ineligible=True,
        )
        value = lambda item, key: item.get(key) if hasattr(item, "get") else getattr(item, key, None)
        named = [
            item for item in evaluated
            if str(value(item, "name") or "").casefold() in message.casefold()
        ]
        targets = named or evaluated[:3]
        explanations = []
        for item in targets:
            reason = value(item, "reason") or str(value(item, "status")).replace("_", " ")
            explanations.append(
                f"{value(item, 'name')} was excluded at Stage 2 because {reason}."
            )
        return self._direct_answer(
            profile, " ".join(explanations), status="exclusion_explanation",
            evidence_category="authoritative_fact",
        )

    @staticmethod
    def _direct_answer(
        profile: dict[str, Any], question: str, *, status: str = "comparison",
        evidence_category: str = "unknown",
    ) -> dict[str, Any]:
        return {
            "profile": profile,
            "understood": summarize_profile(profile),
            "ready_to_search": bool(profile.get("hard_constraints") or profile.get("preferences")),
            "status": status,
            "question": question,
            "citations": [],
            "ranking_affected": False,
            "evidence_category": evidence_category,
        }

    def handle(
        self, *, message: str, profile: dict[str, Any] | None,
        selected_school_ids: list[str], eligible_school_ids: list[str],
        excluded_school_ids: list[str], family: FamilyDetails | None, home_postal_code: str | None,
    ) -> dict[str, Any]:
        current = profile or {}
        before = deepcopy(current)
        active = current.get("active_school") or {}
        intent = classify_intent(message, active.get("name"))
        context = self.build_conversation_context(
            message=message,
            profile=profile,
            selected_school_ids=selected_school_ids,
            eligible_school_ids=eligible_school_ids,
            excluded_school_ids=excluded_school_ids,
            family=family,
            home_postal_code=home_postal_code,
            include_full_catalogue=intent.intent == "find_closest_preschool",
        )
        if intent.intent == "run_what_if_scenario":
            baseline = (
                context.selected_schools if selected_school_ids
                else context.eligible_schools
            )
            result = self._what_if(
                message, selected_school_ids or eligible_school_ids, current, family,
                [item.facts for item in baseline],
            )
            return enrich_decision_state(before, result, intent=intent.intent)
        if intent.intent == "explain_school_exclusion":
            result = self._explain_exclusion(
                message, excluded_school_ids, current, family,
                [item.facts for item in context.excluded_schools],
            )
            return enrich_decision_state(before, result, intent=intent.intent)
        selected = [item.facts for item in context.selected_schools]
        eligible = [item.facts for item in context.eligible_schools]
        web_index = context.selected_school_evidence.index
        general_index = context.general_knowledge_evidence.index
        result = update_conversation(
            profile, message, selected, eligible, web_index, general_index, intent,
            self.schools.facet_summary(),
        )
        if intent.intent == "ask_selected_school_evidence":
            result = self._apply_selected_school_answer_mode(
                result, message=message, selected=selected, web_index=web_index,
            )
        return enrich_decision_state(before, result, intent=intent.intent)
