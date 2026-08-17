"""Reusable Stage 2 age-compliance and preschool cost calculations."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from numbers import Real
from typing import Any


AGE_TO_CARE_LEVEL = {
    2: "Playgroup (18 mths to 2 yrs old)",
    3: "Pre-Nursery (3 yrs old)",
    4: "Nursery (4 yrs old)",
    5: "Kindergarten 1 (5 yrs old)",
    6: "Kindergarten 2 (6 yrs old)",
}


def _additional_subsidy(ghi: Real) -> float:
    if ghi < 0:
        raise ValueError("Gross household income cannot be negative")
    if ghi <= 3000:
        return 400.0
    if ghi <= 6000:
        return 250.0
    if ghi <= 12000:
        return 100.0
    return 0.0


def evaluate_preschool_eligibility(
    dob: dt.date,
    admission_date: dt.date,
    ghi: Real,
    base_fee: Real,
    basic_subsidy: Real,
    care_levels: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Evaluate age eligibility and calculate one preschool's monthly cost."""
    if admission_date < dob:
        raise ValueError("Admission date cannot be before date of birth")
    if base_fee < 0 or basic_subsidy < 0:
        raise ValueError("Fees and subsidies cannot be negative")

    calendar_age = admission_date.year - dob.year
    eligible_level = AGE_TO_CARE_LEVEL.get(calendar_age)
    if eligible_level is None:
        return {
            "eligible": False,
            "eligible_level": None,
            "reason": "Age outside standard preschool brackets",
        }

    offered_levels = list(care_levels or [])
    if offered_levels and eligible_level not in offered_levels:
        return {
            "eligible": False,
            "eligible_level": eligible_level,
            "reason": "Preschool does not offer the required care level",
        }

    additional_subsidy = _additional_subsidy(ghi)
    net_fee = max(0.0, float(base_fee) - float(basic_subsidy) - additional_subsidy)
    return {
        "eligible": True,
        "eligible_level": eligible_level,
        "additional_subsidy": additional_subsidy,
        "net_monthly_fee": net_fee,
    }


def evaluate_shortlist(
    shortlist: Iterable[Mapping[str, Any]],
    *,
    dob: dt.date,
    admission_date: dt.date,
    ghi: Real,
    basic_subsidy: Real,
    include_ineligible: bool = False,
) -> list[dict[str, Any]]:
    """Enrich Stage 1 records with Stage 2 eligibility and cost results."""
    evaluated = []
    for school in shortlist:
        if school.get("base_fee") is None:
            if include_ineligible:
                evaluated.append(
                    {
                        **dict(school),
                        "eligible": False,
                        "eligible_level": None,
                        "reason": "Fee data is unavailable for this preschool",
                    }
                )
            continue
        outcome = evaluate_preschool_eligibility(
            dob=dob,
            admission_date=admission_date,
            ghi=ghi,
            base_fee=school["base_fee"],
            basic_subsidy=basic_subsidy,
            care_levels=school.get("care_levels"),
        )
        enriched = {**dict(school), **outcome}
        if outcome["eligible"] or include_ineligible:
            evaluated.append(enriched)
    return evaluated
