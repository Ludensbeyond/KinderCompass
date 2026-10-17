"""Prepare new-flow context without interpreting the message or computing facts."""

from copy import deepcopy

from SystemCode.src.backend.agents.contracts import (
    InitialConversationContext, PendingConversationDecision, SchoolIdentityContext,
)
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.conversation_history_service import HistoryLease


CAPABILITIES = (
    "read_school_facts", "search_school_evidence", "search_general_guidance",
    "search_rank_compare_schools", "calculate_fees_scenario", "find_nearby_schools",
    "update_preferences", "reset_continue_preferences",
)


def current_state_support(context: InitialConversationContext):
    """Scalar support for current user inputs, never catalogue facts."""
    from ..agents.structured_contracts import StructuredToolResult
    from ..pipeline.stage1.preference_schema import sync_preference_schema

    current = sync_preference_schema(context.profile)
    return StructuredToolResult(
        result_id="context:current", tool_name="update_preferences", status="ok",
        data={
            "profile": {
                "hard_constraints": {k: v for k, v in current.get("hard_constraints", {}).items()
                                     if k in {"language", "level", "max_distance_km"}},
                "preference_items": current.get("preference_items", []),
                "unsupported_preferences": current.get("unsupported_preferences", []),
            },
            "family": context.family.model_dump(mode="json") if context.family else None,
            "home_postal_code": context.home_postal_code,
        }, catalogue_version=context.catalogue_version, state_revision=0,
    )


class ConversationContextService:
    def __init__(self, schools: SchoolRepository):
        self.schools = schools

    def build(self, *, message: str, profile: dict | None = None,
              selected_school_ids: list[str] | None = None,
              family: FamilyDetails | None = None, home_postal_code: str | None = None,
              history: HistoryLease | None = None) -> InitialConversationContext:
        current = deepcopy(profile or {})
        ids = list(dict.fromkeys(selected_school_ids or []))
        active_id = (current.get("active_school") or {}).get("school_id")
        if active_id and active_id not in ids:
            ids.append(active_id)
        if len(ids) > 50:
            raise ValueError("Initial context supports at most 50 selected schools")
        identities = [SchoolIdentityContext(school_id=s.school_id, name=s.name)
                      for s in self.schools.get_many(ids)] if ids else []
        if "active_school" in current:
            current.pop("active_school")
            active = next((s for s in identities if s.school_id == active_id), None)
            if active:
                current["active_school"] = active.model_dump()
        pending = [PendingConversationDecision(kind=kind, details=current[key])
                   for key, kind in (
                       ("pending", "preference_strength"),
                       ("pending_contradiction", "contradiction"),
                       ("pending_relaxation", "relaxation"),
                   ) if current.get(key)]
        return InitialConversationContext(
            message=message, profile=current, pending_decisions=pending,
            selected_schools=identities,
            family=family.model_dump() if family else None,
            home_postal_code=home_postal_code,
            recent_exchanges=list(history.exchanges) if history else [],
            older_turns_omitted=history.omitted if history else False,
            catalogue_version=self.schools.catalogue_version,
            capabilities=list(CAPABILITIES),
        )
