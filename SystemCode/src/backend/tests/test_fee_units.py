import json
import tempfile
import unittest
from pathlib import Path

from SystemCode.src.backend.domain.fee_units import is_monthly_programme_fee
from SystemCode.src.backend.repositories.school_repository import SchoolRepository


def service(service_type: str, fee: float = 100, remarks: str | None = None) -> dict:
    return {
        "class_of_licence": "Class B (Child Care)",
        "levels_offered": "Pre-Nursery (3 yrs old)",
        "type_of_service": service_type,
        "type_of_citizenship": "SC",
        "fees": fee,
        "remarks": remarks,
    }


class MonthlyFeeClassificationTests(unittest.TestCase):
    def test_accepts_all_supported_monthly_programme_variants(self):
        for service_type in (
            "Full Day",
            "Half Day AM",
            "Half Day PM",
            "Flexi Care 1",
            "Flexi Care 1 AM",
            "Flexi Care 1 PM",
            "Flexi Care 2",
            "Flexi Care 3",
        ):
            with self.subTest(service_type=service_type):
                self.assertTrue(is_monthly_programme_fee(service(service_type)))

    def test_rejects_non_programme_and_explicit_non_monthly_rates(self):
        self.assertFalse(is_monthly_programme_fee(service("Emergency Care", fee=15)))
        for remarks in (
            "$15 per hour",
            "Daily fee applies",
            "Fees charged per session",
            "Termly fees",
        ):
            with self.subTest(remarks=remarks):
                self.assertFalse(
                    is_monthly_programme_fee(service("Full Day", remarks=remarks))
                )

    def test_repository_base_fee_uses_lowest_monthly_programme(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.json"
            path.write_text(
                json.dumps([{
                    "school_id": "CENTRE:A",
                    "centre_name_x": "Trusted",
                    "base_fee": 15,
                    "services_menu": [
                        service("Emergency Care", fee=15),
                        service("Full Day", fee=610),
                        service("Flexi Care 1 AM", fee=320),
                    ],
                }]),
                encoding="utf-8",
            )

            school = SchoolRepository(path).get("CENTRE:A")

            self.assertEqual(school["base_fee"], 320)
            self.assertTrue(school["has_fee_data"])


if __name__ == "__main__":
    unittest.main()
