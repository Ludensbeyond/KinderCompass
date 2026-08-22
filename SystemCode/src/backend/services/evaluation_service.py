from __future__ import annotations

from typing import Any

from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from stage1.scorer import rank_schools
from stage2.engine import evaluate_shortlist


class EvaluationService:
    def __init__(self, schools: SchoolRepository):
        self.schools = schools

    def evaluate(
        self, school_ids: list[str], profile: dict[str, Any], family: FamilyDetails,
        *, include_ineligible: bool = False,
    ) -> list[dict[str, Any]]:
        trusted = self.schools.get_many(school_ids)
        if profile.get("hard_constraints") or profile.get("preferences"):
            trusted = rank_schools(profile, trusted, limit=len(trusted))
        return evaluate_shortlist(
            trusted, dob=family.dob, admission_date=family.admission_date,
            ghi=family.gross_household_income, citizenship=family.citizenship,
            programme_type=family.programme_type,
            working_hours_per_month=family.working_hours_per_month,
            household_size=family.household_size,
            non_earning_dependants=family.non_earning_dependants,
            special_approval=family.special_approval,
            include_ineligible=include_ineligible,
        )
