from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from SystemCode.src.backend.agents.config import (
    ConversationAgentMode,
    WebRagAnswerMode,
    disable_agent_entry_points,
    get_conversation_agent_mode,
    get_web_rag_answer_mode,
)
from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    ConversationRequestContext,
    ConversationExecutionMetadata,
    EvidenceCitation,
    EvidenceIndexContext,
    SelectedSchoolAgentRequest,
)
from SystemCode.src.backend.agents.observability import (
    build_conversation_observation,
    emit_conversation_observation,
)
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from SystemCode.src.backend.services.decision_state_service import enrich_decision_state
from SystemCode.src.backend.services.conversation_calculations import (
    explain_school_exclusion,
    run_what_if_scenario,
)
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

    @staticmethod
    def _run_conversation_agent(
        context: ConversationRequestContext, tools: list[Any],
        deterministic_fallback: Any,
    ) -> Any:
        """Load the full-conversation graph only in shadow or agent mode."""

        from SystemCode.src.backend.agents.validation import run_conversation_supervisor

        return run_conversation_supervisor(context, tools, deterministic_fallback)

    def _conversation_tools(self, context: ConversationRequestContext) -> list[Any]:
        """Build the complete context-bound capability registry lazily."""

        from SystemCode.src.backend.agents.tools import (
            create_decision_and_calculation_tools,
            create_evidence_tools,
            create_preference_state_tools,
            create_structured_school_facts_tool,
        )

        return [
            *create_preference_state_tools(
                context, candidate_facets=self.schools.facet_summary(),
            ),
            *create_decision_and_calculation_tools(context, self.evaluation),
            create_structured_school_facts_tool(context, self.schools),
            *create_evidence_tools(context),
        ]

    @staticmethod
    def _observe_conversation_agent(
        metadata: ConversationExecutionMetadata,
        *,
        mode: Literal["shadow", "agent"],
        deterministic_response: dict[str, Any] | None = None,
        agent_response: dict[str, Any] | None = None,
    ) -> None:
        """Keep telemetry best-effort and isolated from the served response."""

        try:
            observation = build_conversation_observation(
                metadata,
                mode=mode,
                deterministic_response=deterministic_response,
                agent_response=agent_response,
            )
            emit_conversation_observation(observation)
        except Exception:
            pass

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
        intent: Any | None = None,
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
                    key: resolved_active[key]
                    for key in ("school_id", "centre_code", "name")
                    if resolved_active.get(key) is not None
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
            deterministic_intent=getattr(intent, "intent", None),
            deterministic_intent_method=getattr(intent, "method", None),
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
        return run_what_if_scenario(
            message, school_ids, profile, family, self.evaluation, baseline,
        )

    def _explain_exclusion(
        self, message: str, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails | None,
        evaluated: list[Any] | None = None,
    ) -> dict[str, Any]:
        return explain_school_exclusion(
            message, school_ids, profile, family, self.evaluation, evaluated,
        )

    def _handle_deterministic(
        self, *, message: str, current: dict[str, Any], before: dict[str, Any],
        conversation_profile: dict[str, Any] | None,
        intent: Any, context: ConversationRequestContext,
        selected_school_ids: list[str], eligible_school_ids: list[str],
        excluded_school_ids: list[str], family: FamilyDetails | None,
    ) -> dict[str, Any]:
        """Run the existing controller exactly once for one resolved context."""

        # The resolved context has already replaced any client-carried school
        # label with repository-owned identity data. Both deterministic and
        # agent paths must continue from that same authoritative profile.
        current = deepcopy(context.profile)
        conversation_profile = current

        if intent.intent == "run_what_if_scenario":
            baseline = (
                context.selected_schools if selected_school_ids
                else context.eligible_schools
            )
            result = self._what_if(
                message,
                selected_school_ids or eligible_school_ids,
                current,
                family,
                [item.facts for item in baseline],
            )
            return enrich_decision_state(before, result, intent=intent.intent)
        if intent.intent == "explain_school_exclusion":
            result = self._explain_exclusion(
                message,
                excluded_school_ids,
                current,
                family,
                [item.facts for item in context.excluded_schools],
            )
            return enrich_decision_state(before, result, intent=intent.intent)

        selected = [item.facts for item in context.selected_schools]
        eligible = [item.facts for item in context.eligible_schools]
        web_index = context.selected_school_evidence.index
        result = update_conversation(
            conversation_profile,
            message,
            selected,
            eligible,
            web_index,
            context.general_knowledge_evidence.index,
            intent,
            self.schools.facet_summary(),
        )
        if intent.intent == "ask_selected_school_evidence":
            result = self._apply_selected_school_answer_mode(
                result, message=message, selected=selected, web_index=web_index,
            )
        return enrich_decision_state(before, result, intent=intent.intent)

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
            intent=intent,
        )
        mode = get_conversation_agent_mode()

        def deterministic_result() -> dict[str, Any]:
            return self._handle_deterministic(
                message=message, current=current, before=before,
                conversation_profile=profile,
                intent=intent, context=context,
                selected_school_ids=selected_school_ids,
                eligible_school_ids=eligible_school_ids,
                excluded_school_ids=excluded_school_ids,
                family=family,
            )

        if mode is ConversationAgentMode.DETERMINISTIC:
            return deterministic_result()

        # A full-conversation run owns model orchestration in shadow and agent
        # modes. Disable the older selected-school graph in every legacy result
        # used by those modes so one request cannot enter two graphs.
        if mode is ConversationAgentMode.SHADOW:
            with disable_agent_entry_points():
                served = deterministic_result()
            try:
                tools = self._conversation_tools(context)
                run = self._run_conversation_agent(
                    context, tools, lambda: deepcopy(served),
                )
                if isinstance(getattr(run, "metadata", None), ConversationExecutionMetadata):
                    self._observe_conversation_agent(
                        run.metadata,
                        mode="shadow",
                        deterministic_response=served,
                        agent_response=run.response,
                    )
            except Exception:
                # Shadow execution can never alter or fail the served response.
                self._observe_conversation_agent(
                    ConversationExecutionMetadata(
                        mode="shadow", validation_succeeded=False,
                        termination_reason="error", fallback_reason="validation_error",
                    ),
                    mode="shadow",
                )
            return served

        try:
            tools = self._conversation_tools(context)
            run = self._run_conversation_agent(context, tools, deterministic_result)
        except Exception:
            with disable_agent_entry_points():
                fallback = deterministic_result()
            fallback["answer_method"] = "deterministic_fallback"
            fallback["fallback_reason"] = "validation_error"
            self._observe_conversation_agent(
                ConversationExecutionMetadata(
                    mode="agent", validation_succeeded=False,
                    termination_reason="error", fallback_reason="validation_error",
                ),
                mode="agent",
            )
            return fallback
        if isinstance(getattr(run, "metadata", None), ConversationExecutionMetadata):
            self._observe_conversation_agent(
                run.metadata, mode="agent",
            )
        if run.metadata.validation_succeeded:
            return enrich_decision_state(before, run.response, intent=intent.intent)
        return run.response
