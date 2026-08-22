from __future__ import annotations

from typing import Any

from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from stage1.scorer import rank_schools
from stage2.engine import (
    age_in_months,
    evaluate_preschool_eligibility,
    placement_for_age,
    programme_id_for_service,
    subsidy_category,
)


class ProgrammeUnavailableError(ValueError):
    pass


class EvaluationService:
    def __init__(self, schools: SchoolRepository):
        self.schools = schools

    @staticmethod
    def _family_arguments(family: FamilyDetails) -> dict[str, Any]:
        return {
            "dob": family.dob,
            "admission_date": family.admission_date,
            "ghi": family.gross_household_income,
            "citizenship": family.citizenship,
            "working_hours_per_month": family.working_hours_per_month,
            "household_size": family.household_size,
            "non_earning_dependants": family.non_earning_dependants,
            "special_approval": family.special_approval,
        }

    def _estimate(
        self,
        school: dict[str, Any],
        family: FamilyDetails,
        *,
        programme_id: str,
        service_type: str | None = None,
    ) -> dict[str, Any]:
        return evaluate_preschool_eligibility(
            **self._family_arguments(family),
            base_fee=school.get("base_fee"),
            care_levels=school.get("care_levels"),
            services_menu=school.get("services_menu"),
            programme_type=programme_id,
            service_type=service_type,
        )

    def programme_options(
        self, school: dict[str, Any], family: FamilyDetails
    ) -> list[dict[str, Any]]:
        months = age_in_months(family.dob, family.admission_date)
        level, _ = placement_for_age(months)
        if not level:
            return []
        service_types = sorted(
            {
                str(item.get("type_of_service"))
                for item in school.get("services_menu") or []
                if item.get("levels_offered") == level
                and item.get("type_of_citizenship") == family.citizenship
                and programme_id_for_service(item.get("type_of_service"))
            },
            key=lambda item: (item != "Full Day", item),
        )
        options = []
        for service_type in service_types:
            programme_id = programme_id_for_service(service_type)
            result = self._estimate(
                school,
                family,
                programme_id=programme_id,
                service_type=service_type,
            )
            if result.get("eligible"):
                options.append({**result, "service_label": service_type})
        return options

    def _evaluate_school(
        self, school: dict[str, Any], family: FamilyDetails
    ) -> dict[str, Any]:
        options = self.programme_options(school, family)
        preferred_category = subsidy_category(family.programme_type)
        preferred = [
            item for item in options if item.get("programme") == preferred_category
        ]
        chosen = min(
            preferred or options,
            key=lambda item: item.get("fee_before_subsidy", float("inf")),
            default=None,
        )
        if chosen is None:
            chosen = self._estimate(
                school, family, programme_id=family.programme_type
            )
        return {
            **school,
            **chosen,
            "preferred_programme": family.programme_type,
            "preferred_programme_available": bool(preferred),
            "programme_options": options,
        }

    def evaluate(
        self,
        school_ids: list[str],
        profile: dict[str, Any],
        family: FamilyDetails,
        *,
        include_ineligible: bool = False,
    ) -> list[dict[str, Any]]:
        trusted = self.schools.get_many(school_ids)
        if profile.get("hard_constraints") or profile.get("preferences"):
            trusted = rank_schools(profile, trusted, limit=len(trusted))
        evaluated = [self._evaluate_school(school, family) for school in trusted]
        return [
            item for item in evaluated if item.get("eligible") or include_ineligible
        ]

    def estimate_programme(
        self, school_id: str, programme_id: str, family: FamilyDetails
    ) -> dict[str, Any]:
        school = self.schools.get(school_id)
        option = next(
            (
                item
                for item in self.programme_options(school, family)
                if item.get("programme_id") == programme_id
            ),
            None,
        )
        if option is None:
            raise ProgrammeUnavailableError(
                f"Programme {programme_id!r} is unavailable for school {school_id}"
            )
        return {"school_id": school_id, **option}
