"""Request-local new-flow capabilities, with no model or persistence calls."""

from copy import deepcopy
from typing import Callable

from langchain_core.tools import StructuredTool

from ..agents.contracts import InitialConversationContext, PublicCitation
from ..agents.structured_contracts import (
    CalculationArguments, GeneralGuidanceArguments, NearbyArguments,
    PreferenceChoice, PreferencePatch, ResetContinueArguments, SchoolEvidenceArguments,
    SchoolFactsArguments, SearchArguments, StructuredToolResult,
)
from ..agents.tools import GeneralKnowledgeRetriever
from ..domain.models import FamilyDetails
from ..pipeline.stage1.dialogue_manager import resolve_constraint_relaxation, resolve_contradiction
from ..pipeline.stage1.preference_schema import make_preference_item, sync_preference_schema
from ..pipeline.stage1.scorer import rank_schools
from ..pipeline.stage1.web_rag import retrieve
from ..repositories.school_repository import SchoolRepository
from .evaluation_service import EvaluationService
from .location_service import LocationService


def _remove_attribute(profile: dict, attribute: str) -> None:
    hard_key = {"care_level": "level"}.get(attribute, attribute)
    profile.setdefault("hard_constraints", {}).pop(hard_key, None)
    preferences = profile.setdefault("preferences", {})
    for key in list(preferences):
        if key == attribute or (attribute == "language" and key.startswith("language:")):
            preferences.pop(key)
    for field in ("preference_items", "unsupported_preferences"):
        profile[field] = [i for i in profile.get(field, []) if i["attribute"] != attribute]


def _apply_choice(profile: dict, choice: PreferenceChoice) -> None:
    _remove_attribute(profile, choice.attribute)
    item = make_preference_item(choice.attribute, choice.value, choice.importance)
    if item["evidence_class"] == "unsupported":
        if not choice.desired:
            raise ValueError("unsupported preferences cannot be negated")
        profile.setdefault("unsupported_preferences", []).append(item)
    elif choice.attribute in {"care_level", "max_distance_km"}:
        key = "level" if choice.attribute == "care_level" else choice.attribute
        profile["hard_constraints"][key] = choice.value
    elif choice.attribute == "language" and choice.importance == "required" and choice.desired:
        profile["hard_constraints"]["language"] = choice.value
    else:
        key = f"language:{choice.value}" if choice.attribute == "language" else choice.attribute
        profile["preferences"][key] = {
            "value": choice.value, "weight": 4, "desired": choice.desired,
        }
    if item["evidence_class"] != "unsupported":
        profile.setdefault("preference_items", []).append(item)


class ConversationToolService:
    """One instance per turn. Export only after final validation; abort on failure.

    Export is a detached candidate, not a persistent commit. HTTP/session commit
    belongs to Step 6; response validation and the model loop belong to Steps 4–5.
    A failing invocation closes the transaction and discards all staged changes.
    """

    def __init__(self, context: InitialConversationContext, schools: SchoolRepository,
                 evaluation: EvaluationService, locations: LocationService, *,
                 school_index_loader: Callable[[], dict | None] | None = None,
                 general_retriever_loader: Callable[[], GeneralKnowledgeRetriever | None] | None = None):
        self._context = context.model_copy(deep=True)
        self._profile = sync_preference_schema(deepcopy(context.profile))
        self._initial_profile = deepcopy(self._profile)
        self.schools, self.evaluation, self.locations = schools, evaluation, locations
        self._school_index_loader = school_index_loader
        self._general_retriever_loader = general_retriever_loader
        self._revision = 0
        self._calls = 0
        self._mutations = 0
        self._closed = False
        self._specs = {
            "read_school_facts": (SchoolFactsArguments, self._facts),
            "search_school_evidence": (SchoolEvidenceArguments, self._school_evidence),
            "search_general_guidance": (GeneralGuidanceArguments, self._general_evidence),
            "search_rank_compare_schools": (SearchArguments, self._search),
            "calculate_fees_scenario": (CalculationArguments, self._calculate),
            "find_nearby_schools": (NearbyArguments, self._nearby),
            "update_preferences": (PreferencePatch, self._patch),
            "reset_continue_preferences": (ResetContinueArguments, self._continue),
        }

    @property
    def staged_profile(self) -> dict:
        return deepcopy(self._profile)

    def abort(self) -> None:
        self._profile = deepcopy(self._initial_profile)
        self._closed = True

    def export_validated_state(self, *, response_validated: bool, shadow: bool = False) -> dict:
        if self._closed or not response_validated:
            self.abort()
            raise ValueError("cannot export an unvalidated or closed turn")
        result = sync_preference_schema(deepcopy(self._initial_profile if shadow else self._profile))
        self._closed = True
        return result

    def invoke(self, name: str, arguments: dict) -> StructuredToolResult:
        if self._closed:
            raise ValueError("turn is closed")
        try:
            # This is access filtering by server-owned capabilities, never message keywords.
            if name not in self._context.capabilities or name not in self._specs:
                raise ValueError("capability is unavailable")
            self._calls += 1
            if self._calls > 12:
                raise ValueError("turn tool-call limit exceeded")
            schema, function = self._specs[name]
            request = schema.model_validate(arguments)
            status, data, missing, citations = function(request)
            return StructuredToolResult(
                result_id=f"result:{self._calls}", tool_name=name, status=status,
                data=data, missing_inputs=missing, citations=citations,
                catalogue_version=self.schools.catalogue_version, state_revision=self._revision,
            )
        except Exception:
            self.abort()
            raise

    def registered_tools(self) -> list[StructuredTool]:
        transaction = self
        class TransactionTool(StructuredTool):
            def _parse_input(self, tool_input, tool_call_id=None):
                try:
                    return super()._parse_input(tool_input, tool_call_id)
                except Exception:
                    transaction.abort()
                    raise

        def bind(name):
            def run(**arguments):
                return self.invoke(name, arguments)
            return run
        return [TransactionTool.from_function(
            func=bind(name), name=name, args_schema=schema, infer_schema=False,
            description=f"{name.replace('_', ' ')} using validated inputs and server-owned data. Returns structured status and provenance.",
        ) for name, (schema, _) in self._specs.items() if name in self._context.capabilities]

    def _stage(self, candidate: dict, changed: list[str]):
        self._mutations += 1
        if self._mutations > 4:
            raise ValueError("turn mutation limit exceeded")
        self._profile = sync_preference_schema(candidate)
        self._revision += 1
        pending = {k: deepcopy(self._profile[k]) for k in
                   ("pending", "pending_contradiction", "pending_relaxation") if self._profile.get(k)}
        return ("needs_input" if pending else "ok", {
            "staged_profile": deepcopy(self._profile), "changed_fields": changed,
            "unresolved_decisions": pending,
        }, list(pending), [])

    def _patch(self, request: PreferencePatch):
        if any(self._profile.get(k) for k in ("pending", "pending_contradiction", "pending_relaxation")):
            return "needs_input", {}, ["pending_decision_resolution"], []
        candidate = deepcopy(self._profile)
        # A replacement of a positive required choice requires an explicit resolution.
        for choice in request.set:
            old = next((i for i in self._profile.get("preference_items", [])
                        if i["attribute"] == choice.attribute and i["importance"] == "required"), None)
            if choice.attribute in {"language", "pedagogy"} and old and (
                old["value"] != choice.value or not choice.desired
            ):
                if choice.attribute == "language" and (choice.importance != "required" or not choice.desired):
                    raise ValueError("resolve the required language before downgrading or negating it")
                candidate["pending_contradiction"] = {
                    "attribute": choice.attribute, "existing": old["value"],
                    "incoming": choice.value,
                    "typed_incoming": choice.model_dump(),
                    "incoming_preference": {"value": choice.value, "weight": 5 if choice.importance == "required" else 4, "desired": choice.desired},
                }
                return self._stage(candidate, ["pending_contradiction"])
        for attribute in request.remove:
            _remove_attribute(candidate, attribute)
        for choice in request.set:
            _apply_choice(candidate, choice)
        return self._stage(candidate, request.remove + [c.attribute for c in request.set])

    def _continue(self, request: ResetContinueArguments):
        candidate = deepcopy(self._profile)
        if request.operation == "reset":
            # Reset preference state while preserving the current school reference.
            candidate = {k: deepcopy(candidate[k]) for k in ("active_school",) if k in candidate}
            candidate.update(hard_constraints={}, preferences={}, recognized=[])
        elif request.operation == "resolve_strength":
            pending = candidate.get("pending")
            if not pending:
                return "needs_input", {}, ["pending_preference"], []
            _apply_choice(candidate, PreferenceChoice(
                attribute=pending["kind"], value=pending["value"], importance=request.choice,
            ))
            candidate.pop("pending")
        elif request.operation == "resolve_contradiction":
            if not candidate.get("pending_contradiction"):
                return "needs_input", {}, ["pending_contradiction"], []
            pending = candidate["pending_contradiction"]
            if "typed_incoming" in pending:
                if request.choice == "use_incoming":
                    _apply_choice(candidate, PreferenceChoice.model_validate(pending["typed_incoming"]))
                candidate.pop("pending_contradiction")
                return self._stage(candidate, [request.operation])
            # The choice is typed; this fixed adapter does not interpret user prose.
            candidate, resolved = resolve_contradiction(candidate,
                "keep existing" if request.choice == "keep_existing" else "use new")
            if not resolved:
                raise ValueError("invalid saved contradiction")
        else:
            if not candidate.get("pending_relaxation"):
                return "needs_input", {}, ["pending_relaxation"], []
            candidate, _ = resolve_constraint_relaxation(candidate,
                "apply relaxation" if request.choice == "approve" else "keep constraints")
        return self._stage(candidate, [request.operation])

    def _facts(self, request: SchoolFactsArguments):
        records = self.schools.get_structured_facts(request.school_ids, request.operation)
        return ("ok" if any(r["available"] for r in records) else "no_evidence",
                {"records": records}, [], [])

    def _records(self, ids: list[str]):
        return [r.model_dump(mode="json") for r in (self.schools.get_many(ids) if ids else self.schools.all())]

    def _rank(self, records: list[dict]):
        # Preserve existing hard language/level/distance semantics before scoring.
        hard = self._profile.get("hard_constraints", {})
        if hard.get("level"):
            records = [r for r in records if hard["level"] in r.get("care_levels", [])]
        if hard.get("language"):
            records = [r for r in records if hard["language"].casefold() in
                       {v.strip().casefold() for v in str(r.get("second_languages_offered") or "").split("|")}]
        if hard.get("max_distance_km"):
            if not self._context.home_postal_code:
                return None
            records = self.locations.attach_distances(records, self._context.home_postal_code)
            records = [r for r in records if r.get("distance_km") is not None and r["distance_km"] <= hard["max_distance_km"]]
        return rank_schools(self._profile, records, limit=len(records))

    def _search(self, request: SearchArguments):
        records = self._records(request.school_ids)
        if request.operation == "compare":
            from ..pipeline.stage1.scorer import score_school
            ranked = [score_school(self._profile, r) for r in records]
        else:
            ranked = self._rank(records)
        if ranked is None:
            return "needs_input", {}, ["home_postal_code"], []
        return ("ok" if ranked else "no_evidence", {
            "records": ranked[:request.limit], "operation": request.operation,
            "profile_used": deepcopy(self._profile), "total_matches": len(ranked),
            "truncated": len(ranked) > request.limit, "source": "generated_school_catalogue",
        }, [], [])

    def _calculate(self, request: CalculationArguments):
        self.schools.get_many(request.school_ids)  # Reject unknown IDs even without family inputs.
        if not self._context.family:
            return "needs_input", {}, ["family"], []
        inputs = self._context.family.model_dump()
        inputs.update(request.overrides.model_dump(exclude_unset=True))
        family = FamilyDetails.model_validate(inputs)
        evaluated = self.evaluation.evaluate(request.school_ids, deepcopy(self._profile), family, include_ineligible=True)
        return "ok", {
            "records": [r.model_dump(mode="json") for r in evaluated],
            "inputs_used": family.model_dump(mode="json"), "hypothetical": bool(request.overrides.model_fields_set),
            "profile_used": deepcopy(self._profile), "source": "deterministic_stage2",
        }, [], []

    def _nearby(self, request: NearbyArguments):
        postal = request.postal_code or self._context.home_postal_code
        if not postal:
            return "needs_input", {}, ["home_postal_code"], []
        records = self.locations.attach_distances(self._records([]), postal)
        known = [r for r in records if r.get("distance_km") is not None and
                 (request.radius_km is None or r["distance_km"] <= request.radius_km)]
        known.sort(key=lambda r: (r["distance_km"], r["school_id"]))
        return ("ok" if known else "no_evidence", {
            "records": known[:request.limit], "postal_code_used": postal,
            "distance_method": "haversine", "missing_location_count": sum(r.get("distance_km") is None for r in records),
            "total_matches": len(known), "truncated": len(known) > request.limit,
        }, [], [])

    def _school_evidence(self, request: SchoolEvidenceArguments):
        self.schools.get_many(request.school_ids)
        index = self._school_index_loader() if self._school_index_loader else None
        if index is None:
            return "unavailable", {}, [], []
        passages, citations = [], []
        for school_id in request.school_ids:
            for match in retrieve(index, school_id, request.query, limit=3):
                citation = match["citation"]
                citations.append(PublicCitation(
                    citation_id=match["chunk_id"], evidence_scope="school", school_id=school_id,
                    url=citation["url"], title=citation["title"], retrieved_at=citation["retrieved_at"],
                ))
                passages.append({"school_id": school_id, "chunk_id": match["chunk_id"],
                                 "text": match["text"], "evidence_category": "school_published_claim"})
        return "ok" if passages else "no_evidence", {
            "passages": passages,
            "missing_evidence_school_ids": [school_id for school_id in request.school_ids
                                            if not any(p["school_id"] == school_id for p in passages)],
        }, [], citations

    def _general_evidence(self, request: GeneralGuidanceArguments):
        retriever = self._general_retriever_loader() if self._general_retriever_loader else None
        if retriever is None:
            return "unavailable", {}, [], []
        from ..agents.contracts import GeneralKnowledgeEvidence
        passages = [GeneralKnowledgeEvidence.model_validate(r) for r in retriever.search(request.query, limit=3)]
        if len(passages) > 3:
            raise ValueError("retriever exceeded passage limit")
        return ("ok" if passages else "no_evidence", {
            "passages": [{"chunk_id": p.chunk_id, "text": p.text, "evidence_category": p.evidence_category} for p in passages],
        }, [], [p.citation for p in passages])
