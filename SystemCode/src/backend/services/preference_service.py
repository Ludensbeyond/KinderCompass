from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

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

    def _what_if(
        self, message: str, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails | None,
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
        baseline = self.evaluation.evaluate(school_ids, profile, family, include_ineligible=True)
        scenario = self.evaluation.evaluate(school_ids, profile, scenario_family, include_ineligible=True)
        baseline_by_id = {item.school_id: item for item in baseline}
        sections = []
        for changed in scenario[:5]:
            original = baseline_by_id.get(changed.school_id)
            name = changed.name
            if original and original.net_monthly_fee is not None and changed.net_monthly_fee is not None:
                sections.append(
                    f"{name}: estimated monthly fee changes from ${original.net_monthly_fee:,.0f} "
                    f"to ${changed.net_monthly_fee:,.0f}."
                )
            else:
                sections.append(f"{name}: scenario status is {changed.status.replace('_', ' ')}.")
        assumptions = ", ".join(key.replace("_", " ") + f"={value:g}" for key, value in changes.items())
        return self._direct_answer(
            profile,
            f"What-if only ({assumptions}); your saved family details were not changed. " + " ".join(sections),
            status="what_if",
            evidence_category="calculated_estimate",
        )

    def _explain_exclusion(
        self, message: str, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails | None,
    ) -> dict[str, Any]:
        if not school_ids or not family:
            return self._direct_answer(profile, "No Stage 2 exclusions are available for the current recommendation result.")
        evaluated = self.evaluation.evaluate(school_ids, profile, family, include_ineligible=True)
        named = [item for item in evaluated if item.name.casefold() in message.casefold()]
        targets = named or evaluated[:3]
        explanations = []
        for item in targets:
            reason = item.get("reason") or item.status.replace("_", " ")
            explanations.append(f"{item.name} was excluded at Stage 2 because {reason}.")
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
        if intent.intent == "run_what_if_scenario":
            result = self._what_if(
                message, selected_school_ids or eligible_school_ids, current, family
            )
            return enrich_decision_state(before, result, intent=intent.intent)
        if intent.intent == "explain_school_exclusion":
            result = self._explain_exclusion(
                message, excluded_school_ids, current, family
            )
            return enrich_decision_state(before, result, intent=intent.intent)
        selected_ids = selected_school_ids or ([active["school_id"]] if active.get("school_id") else [])
        selected = self._rebuild(selected_ids, current, family)
        eligible = self._rebuild(eligible_school_ids, current, family)
        if intent.intent == "find_closest_preschool" and not eligible:
            eligible = self.schools.all()
        if home_postal_code:
            if selected:
                selected = self.locations.attach_distances(selected, home_postal_code)
            if eligible:
                eligible = self.locations.attach_distances(eligible, home_postal_code)
        web_index, general_index = self._resources()
        result = update_conversation(
            profile, message, selected, eligible, web_index, general_index, intent,
            self.schools.facet_summary(),
        )
        return enrich_decision_state(before, result, intent=intent.intent)
