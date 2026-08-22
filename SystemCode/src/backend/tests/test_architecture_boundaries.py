import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from SystemCode.src.backend import main
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.policy_repository import (
    PolicyConfigurationError, PolicyRepository, PolicyUnavailableError,
)
from SystemCode.src.backend.repositories.school_repository import (
    SchoolNotFoundError, SchoolRepository,
)
from SystemCode.src.backend.services.evaluation_service import EvaluationService


class RepositoryBoundaryTests(unittest.TestCase):
    def test_school_repository_resolves_ids_and_rejects_unknown_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.json"
            path.write_text(json.dumps([{"school_id": "CENTRE:A", "centre_name_x": "Trusted Name"}]), encoding="utf-8")
            repository = SchoolRepository(path)
            self.assertEqual(repository.get("CENTRE:A")["name"], "Trusted Name")
            with self.assertRaises(SchoolNotFoundError):
                repository.get_many(["CENTRE:A", "CENTRE:MISSING"])

    def test_evaluation_uses_repository_fee_not_caller_school_object(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.json"
            level = "Pre-Nursery (3 yrs old)"
            path.write_text(json.dumps([{
                "school_id": "CENTRE:A", "centre_code": "A", "centre_name_x": "Trusted",
                "care_levels": [level], "base_fee": 9999,
                "services_menu": [{"class_of_licence": "Class B (Child Care)",
                    "levels_offered": level, "type_of_service": "Full Day",
                    "type_of_citizenship": "SC", "fees": 610, "last_updated": "2026-07-17"}],
            }]), encoding="utf-8")
            result = EvaluationService(SchoolRepository(path)).evaluate(
                ["CENTRE:A"], {}, FamilyDetails(
                    dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10),
                    gross_household_income=4500,
                )
            )[0]
            self.assertEqual(result["fee_before_subsidy"], 610)

    def test_api_rejects_legacy_client_supplied_school_objects(self):
        response = TestClient(main.app).post("/api/evaluate", json={
            "shortlist": [{"school_id": "CENTRE:A", "base_fee": 1}],
            "family": {"dob": "2023-06-10", "admission_date": "2026-06-10",
                       "gross_household_income": 4500},
        })
        self.assertEqual(response.status_code, 422)

    def test_unknown_school_id_is_a_404_before_evaluation(self):
        response = TestClient(main.app).post("/api/evaluate", json={
            "school_ids": ["CENTRE:DOES_NOT_EXIST"], "profile": {},
            "family": {"dob": "2023-06-10", "admission_date": "2026-06-10",
                       "gross_household_income": 4500},
        })
        self.assertEqual(response.status_code, 404)


class DatedPolicyRepositoryTests(unittest.TestCase):
    def test_selects_policy_by_effective_date(self):
        repository = PolicyRepository(main.REPO_ROOT / "SystemCode/src/backend/resources/policy")
        self.assertEqual(repository.for_date(dt.date(2026, 1, 1))["policy_id"],
                         "ecda-preschool-subsidies-2025-01-01")
        with self.assertRaises(PolicyUnavailableError):
            repository.for_date(dt.date(2024, 12, 31))

    def test_rejects_overlapping_policy_periods(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = {"policy_id": "one", "effective_from": "2025-01-01", "effective_to": "2025-12-31"}
            second = {"policy_id": "two", "effective_from": "2025-12-01", "effective_to": None}
            (root / "one.json").write_text(json.dumps(first), encoding="utf-8")
            (root / "two.json").write_text(json.dumps(second), encoding="utf-8")
            with self.assertRaises(PolicyConfigurationError):
                PolicyRepository(root).policies()


if __name__ == "__main__":
    unittest.main()
