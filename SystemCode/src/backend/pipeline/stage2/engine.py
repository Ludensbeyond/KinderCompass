"""Versioned, explainable preschool eligibility and subsidy estimates."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from numbers import Real
from pathlib import Path
from typing import Any

from SystemCode.src.backend.repositories.policy_repository import PolicyRepository


POLICY_PATH = Path(__file__).resolve().parents[2] / "resources" / "policy" / "ecda_preschool_subsidies_2025-01-01.json"
POLICY_REPOSITORY = PolicyRepository(POLICY_PATH.parent)
LEVEL_BY_AGE_MONTHS = (
    (2, 18, "Infant (2 to 18 mths)", "infant_care"),
    (18, 36, "Playgroup (18 mths to 2 yrs old)", "child_care"),
    (36, 48, "Pre-Nursery (3 yrs old)", "child_care"),
    (48, 60, "Nursery (4 yrs old)", "child_care"),
    (60, 72, "Kindergarten 1 (5 yrs old)", "child_care"),
    (72, 84, "Kindergarten 2 (6 yrs old)", "child_care"),
)
SERVICE_PROGRAMME_IDS = {
    "Full Day": "full_day", "Half Day AM": "half_day_am", "Half Day PM": "half_day_pm",
    "Flexi Care 1": "flexi_care_1", "Flexi Care 1 AM": "flexi_care_1_am",
    "Flexi Care 1 PM": "flexi_care_1_pm", "Flexi Care 2": "flexi_care_2",
    "Flexi Care 3": "flexi_care_3",
}
PROGRAMME_CATEGORIES = {
    "full_day": "full_day", "half_day": "half_day", "half_day_am": "half_day",
    "half_day_pm": "half_day", "flexi_care_1": "flexi_care_1",
    "flexi_care_1_am": "flexi_care_1", "flexi_care_1_pm": "flexi_care_1",
    "flexi_care_2": "flexi_care_2", "flexi_care_3": "flexi_care_3",
}


def load_policy(applicable_date: dt.date | None = None) -> dict[str, Any]:
    """Return the single policy version effective on the requested date."""
    return POLICY_REPOSITORY.for_date(applicable_date or dt.date.today())


def age_in_months(dob: dt.date, admission_date: dt.date) -> int:
    if admission_date < dob:
        raise ValueError("Admission date cannot be before date of birth")
    months = (admission_date.year - dob.year) * 12 + admission_date.month - dob.month
    return months - int(admission_date.day < dob.day)


def placement_for_age(months: int) -> tuple[str | None, str | None]:
    for lower, upper, level, scheme in LEVEL_BY_AGE_MONTHS:
        if lower <= months < upper:
            return level, scheme
    return None, None


def _normalise_programme(value: str | None) -> str | None:
    if not value:
        return None
    programme_id = SERVICE_PROGRAMME_IDS.get(value, value)
    return PROGRAMME_CATEGORIES.get(programme_id)


def programme_id_for_service(service_type: str | None) -> str | None:
    return SERVICE_PROGRAMME_IDS.get(str(service_type or ""))


def subsidy_category(programme_id: str | None) -> str | None:
    return PROGRAMME_CATEGORIES.get(str(programme_id or ""))


def _select_service(menu: Iterable[Mapping[str, Any]], *, level: str, citizenship: str,
                    programme: str, service_type: str | None = None) -> dict[str, Any] | None:
    candidates = []
    for item in menu:
        if item.get("levels_offered") != level or item.get("type_of_citizenship") != citizenship:
            continue
        if service_type and item.get("type_of_service") != service_type:
            continue
        if _normalise_programme(str(item.get("type_of_service") or "")) != programme:
            continue
        try:
            fee = float(item["fees"])
        except (KeyError, TypeError, ValueError):
            continue
        candidates.append({**dict(item), "fees": fee})
    return min(candidates, key=lambda item: item["fees"], default=None)


def _income_band(policy: dict[str, Any], ghi: float, pci: float | None, use_pci: bool):
    key = "per_capita_income_max" if use_pci else "household_income_max"
    value = pci if use_pci else ghi
    return next((band for band in policy["additional_subsidy_bands"] if value is not None and value <= band[key]), None)


def evaluate_preschool_eligibility(
    dob: dt.date, admission_date: dt.date, ghi: Real, base_fee: Real | None = None,
    basic_subsidy: Real | None = None, care_levels: Iterable[str] | None = None, *,
    services_menu: Iterable[Mapping[str, Any]] | None = None, citizenship: str = "SC",
    programme_type: str = "full_day", working_hours_per_month: float = 56,
    household_size: int = 1, non_earning_dependants: int = 0,
    special_approval: bool = False, service_type: str | None = None,
) -> dict[str, Any]:
    """Estimate placement, programme fee, and potential subsidy from reported facts."""
    if float(ghi) < 0:
        raise ValueError("Gross household income cannot be negative")
    if household_size < 1 or non_earning_dependants < 0:
        raise ValueError("Household size and dependant counts are invalid")

    months = age_in_months(dob, admission_date)
    eligible_level, scheme = placement_for_age(months)
    if eligible_level is None:
        return {"eligible": False, "status": "ineligible", "eligible_level": None,
                "age_on_admission_months": months, "reason": "Age outside standard preschool brackets"}
    offered_levels = list(care_levels or [])
    if offered_levels and eligible_level not in offered_levels:
        return {"eligible": False, "status": "ineligible", "eligible_level": eligible_level,
                "age_on_admission_months": months, "reason": "Preschool does not offer the required care level"}

    programme = _normalise_programme(programme_type)
    if not programme:
        return {"eligible": False, "status": "needs_information", "eligible_level": eligible_level,
                "age_on_admission_months": months, "reason": "The selected programme is not supported by the subsidy estimator"}
    menu = list(services_menu or [])
    service = _select_service(menu, level=eligible_level, citizenship=citizenship,
                              programme=programme, service_type=service_type)
    fee = service["fees"] if service else float(base_fee) if base_fee is not None and not menu else None
    if fee is None:
        return {"eligible": False, "status": "fee_unavailable", "eligible_level": eligible_level,
                "age_on_admission_months": months, "reason": "Programme-specific fee data is unavailable for this preschool"}

    policy = load_policy(admission_date)
    source = {key: policy[key] for key in ("policy_id", "effective_from", "effective_to", "authority", "source_url")}
    warnings = ["This is an estimate and is not an ECDA subsidy approval.",
                "GST treatment and additional centre charges may vary."]
    if programme == "flexi_care_2":
        return {"eligible": True, "status": "manual_review", "eligible_level": eligible_level,
                "age_on_admission_months": months, "scheme": scheme, "programme": programme,
                "programme_id": programme_id_for_service(service.get("type_of_service")) if service else programme_type,
                "fee_before_subsidy": fee, "net_monthly_fee": fee,
                "reason": "A Flexi-care 2 fee is available, but no separately verified subsidy table is configured.",
                "warnings": warnings, "policy_source": source, "selected_service": service}
    if service and service.get("class_of_licence") == "Class C (Kindergarten)":
        return {"eligible": True, "status": "manual_review", "eligible_level": eligible_level,
                "age_on_admission_months": months, "scheme": "kifas", "programme": programme,
                "programme_id": programme_id_for_service(service.get("type_of_service")) if service else programme_type,
                "fee_before_subsidy": fee, "net_monthly_fee": fee,
                "reason": "Kindergarten fees require a separate KiFAS eligibility assessment.",
                "warnings": warnings, "policy_source": source, "selected_service": service}
    if citizenship != "SC":
        return {"eligible": True, "status": "estimated", "eligible_level": eligible_level,
                "age_on_admission_months": months, "scheme": "none", "programme": programme,
                "programme_id": programme_id_for_service(service.get("type_of_service")) if service else programme_type,
                "fee_before_subsidy": fee, "basic_subsidy": 0.0, "additional_subsidy": 0.0,
                "minimum_copayment": 0.0, "net_monthly_fee": fee,
                "reasons": ["The reported child citizenship is not eligible for this ECDA subsidy estimate."],
                "warnings": warnings, "policy_source": source, "selected_service": service}
    if special_approval:
        return {"eligible": True, "status": "manual_review", "eligible_level": eligible_level,
                "age_on_admission_months": months, "scheme": scheme, "programme": programme,
                "programme_id": programme_id_for_service(service.get("type_of_service")) if service else programme_type,
                "fee_before_subsidy": fee, "net_monthly_fee": fee,
                "reason": "Reported circumstances may require ECDA Special Approval and supporting documents.",
                "warnings": warnings, "policy_source": source, "selected_service": service}

    working = working_hours_per_month >= float(policy["working_hours_threshold"])
    status_key = "working" if working else "non_working"
    derived_basic = float(policy["basic_subsidies"][scheme][status_key][programme])
    # Compatibility for existing notebooks; the API no longer asks users to supply this amount.
    applied_basic = float(basic_subsidy) if basic_subsidy is not None and not menu else derived_basic
    pci_qualified = household_size >= 5 and non_earning_dependants >= 3
    pci = round(float(ghi) / household_size, 2)
    band = _income_band(policy, float(ghi), pci, pci_qualified) if working else None
    additional, minimum_copayment = (band[scheme][programme] if band else (0, 0))
    net = max(float(minimum_copayment), fee - applied_basic - float(additional))
    return {
        "eligible": True, "status": "estimated", "eligible_level": eligible_level,
        "age_on_admission_months": months, "scheme": scheme, "programme": programme,
        "programme_id": programme_id_for_service(service.get("type_of_service")) if service else programme_type,
        "fee_before_subsidy": fee, "base_fee": fee, "basic_subsidy": applied_basic,
        "additional_subsidy": float(additional), "minimum_copayment": float(minimum_copayment),
        "net_monthly_fee": round(net, 2), "working_status": status_key,
        "income_assessment_method": "per_capita_income" if pci_qualified else "household_income",
        "per_capita_income": pci, "reasons": [
            f"Child age at admission is {months} completed months.",
            f"The {status_key.replace('_', '-')} {programme.replace('_', ' ')} policy table was applied.",
        ], "warnings": warnings, "policy_source": source, "selected_service": service,
    }


def evaluate_shortlist(
    shortlist: Iterable[Mapping[str, Any]], *, dob: dt.date, admission_date: dt.date,
    ghi: Real, basic_subsidy: Real | None = None, include_ineligible: bool = False, **family: Any,
) -> list[dict[str, Any]]:
    evaluated = []
    for school in shortlist:
        outcome = evaluate_preschool_eligibility(
            dob=dob, admission_date=admission_date, ghi=ghi, base_fee=school.get("base_fee"),
            basic_subsidy=basic_subsidy, care_levels=school.get("care_levels"),
            services_menu=school.get("services_menu"), **family,
        )
        enriched = {**dict(school), **outcome}
        if outcome["eligible"] or include_ineligible:
            evaluated.append(enriched)
    return evaluated
