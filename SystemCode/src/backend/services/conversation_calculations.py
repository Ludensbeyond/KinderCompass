"""Deterministic calculated conversation capabilities shared by agents and HTTP flow."""

from __future__ import annotations

import re
from typing import Any, Protocol

from SystemCode.src.backend.domain.models import FamilyDetails
from stage1.nlp_mapper import summarize_profile


class SchoolEvaluator(Protocol):
    """The narrow evaluation boundary required by calculated chat answers."""

    def evaluate(
        self, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails,
        *, include_ineligible: bool = False,
    ) -> list[Any]: ...


def direct_answer(
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


def run_what_if_scenario(
    message: str, school_ids: list[str], profile: dict[str, Any],
    family: FamilyDetails | None, evaluator: SchoolEvaluator,
    baseline: list[Any] | None = None,
) -> dict[str, Any]:
    """Calculate a temporary family scenario without changing saved inputs."""

    if not family or not school_ids:
        return direct_answer(
            profile,
            "Show recommendations first so I can run a fee or eligibility what-if scenario.",
        )
    changes: dict[str, Any] = {}
    hours = re.search(
        r"(?:working|work) hours(?:\s+per\s+month)?\D{0,12}(\d+(?:\.\d+)?)",
        message, re.I,
    )
    income = re.search(r"(?:income|ghi)\D{0,12}(\d+(?:\.\d+)?)", message, re.I)
    if hours:
        changes["working_hours_per_month"] = float(hours.group(1))
    if income:
        changes["gross_household_income"] = float(income.group(1))
    if not changes:
        return direct_answer(
            profile,
            "Specify a hypothetical gross monthly income or working hours per month, "
            "for example: ‘What if my working hours are 55?’",
        )
    scenario_family = family.model_copy(update=changes)
    baseline = baseline or evaluator.evaluate(
        school_ids, profile, family, include_ineligible=True,
    )
    scenario = evaluator.evaluate(
        school_ids, profile, scenario_family, include_ineligible=True,
    )
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
    assumptions = ", ".join(
        key.replace("_", " ") + f"={changed_value:g}"
        for key, changed_value in changes.items()
    )
    return direct_answer(
        profile,
        f"What-if only ({assumptions}); your saved family details were not changed. "
        + " ".join(sections),
        status="what_if",
        evidence_category="calculated_estimate",
    )


def explain_school_exclusion(
    message: str, school_ids: list[str], profile: dict[str, Any],
    family: FamilyDetails | None, evaluator: SchoolEvaluator,
    evaluated: list[Any] | None = None,
) -> dict[str, Any]:
    """Explain Stage 2 results using only evaluated repository records."""

    if not school_ids or not family:
        return direct_answer(
            profile,
            "No Stage 2 exclusions are available for the current recommendation result.",
        )
    evaluated = evaluated or evaluator.evaluate(
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
    return direct_answer(
        profile, " ".join(explanations), status="exclusion_explanation",
        evidence_category="authoritative_fact",
    )
