from __future__ import annotations

from copy import deepcopy
from typing import Any


MAX_RECENT_DECISIONS = 8
MAX_RECENT_TOPICS = 6


def _preference_values(profile: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    item_attributes: set[str] = set()
    for item in profile.get("preference_items") or []:
        attribute = str(item.get("attribute") or "unknown")
        item_attributes.add(attribute)
        values[f"preference:{attribute}"] = {
            "value": item.get("value"),
            "importance": item.get("importance"),
        }
    for attribute, value in (profile.get("hard_constraints") or {}).items():
        canonical_attribute = "care_level" if attribute == "level" else attribute
        if canonical_attribute not in item_attributes:
            values[f"required:{canonical_attribute}"] = value
    return values


def _changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    previous = _preference_values(before)
    current = _preference_values(after)
    changes = []
    for key in sorted(previous.keys() | current.keys()):
        if previous.get(key) == current.get(key):
            continue
        changes.append({
            "attribute": key.split(":", 1)[1],
            "from": previous.get(key),
            "to": current.get(key),
            "reason": "confirmed preference update",
        })
    return changes


def _unresolved(profile: dict[str, Any]) -> list[dict[str, Any]]:
    if profile.get("pending_contradiction"):
        pending = profile["pending_contradiction"]
        return [{"kind": "contradiction", "attribute": pending.get("attribute")}]
    if profile.get("pending_relaxation"):
        pending = profile["pending_relaxation"]
        return [{"kind": "constraint_relaxation", "attribute": pending.get("attribute")}]
    if profile.get("pending"):
        pending = profile["pending"]
        return [{"kind": "preference_importance", "attribute": pending.get("kind")}]
    next_attribute = profile.get("next_question_attribute")
    return [{"kind": "optional_clarification", "attribute": next_attribute}] if next_attribute else []


def enrich_decision_state(
    before: dict[str, Any] | None,
    result: dict[str, Any],
    *,
    intent: str,
) -> dict[str, Any]:
    """Attach bounded, structured conversation state without retaining turn text."""
    enriched = dict(result)
    profile = deepcopy(result.get("profile") or {})
    prior_state = (before or {}).get("decision_state") or {}

    topics = list(prior_state.get("recent_topics") or [])
    if not topics or topics[-1] != intent:
        topics.append(intent)

    decisions = list(prior_state.get("recent_decisions") or [])
    decisions.extend(_changes(before or {}, profile))
    unresolved = _unresolved(profile)
    current_goal = unresolved[0]["kind"] if unresolved else intent
    profile["decision_state"] = {
        "current_goal": current_goal,
        "recent_topics": topics[-MAX_RECENT_TOPICS:],
        "recent_decisions": decisions[-MAX_RECENT_DECISIONS:],
        "unresolved_questions": unresolved,
        "last_answer_status": result.get("status", "unknown"),
    }
    enriched["profile"] = profile
    return enriched
