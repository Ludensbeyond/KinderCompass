from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from stage1.conversation import update_conversation
from stage1.intent_router import classify_intent
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

    def handle(
        self, *, message: str, profile: dict[str, Any] | None,
        selected_school_ids: list[str], eligible_school_ids: list[str],
        family: FamilyDetails | None, home_postal_code: str | None,
    ) -> dict[str, Any]:
        current = profile or {}
        active = current.get("active_school") or {}
        intent = classify_intent(message, active.get("name"))
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
        return update_conversation(
            profile, message, selected, eligible, web_index, general_index, intent,
        )
