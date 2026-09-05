import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from SystemCode.src.backend.domain.catalogue import EvaluatedSchool
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.services.preference_service import PreferenceService


def evaluated(school_id: str, name: str) -> EvaluatedSchool:
    return EvaluatedSchool.model_validate({
        "school_id": school_id,
        "name": name,
        "status": "estimated",
        "eligible": True,
        "preferred_programme": "full_day",
        "preferred_programme_available": True,
    })


class ConversationContextTests(unittest.TestCase):
    def test_service_builds_context_from_authoritative_server_sources(self):
        schools = Mock()
        schools.catalogue_version = "catalogue-123"
        evaluation = Mock()
        evaluation.evaluate.side_effect = [
            [evaluated("CENTRE:A", "Trusted A")],
            [evaluated("CENTRE:B", "Trusted B")],
            [evaluated("CENTRE:C", "Trusted C")],
        ]
        locations = Mock()
        locations.attach_distances.side_effect = lambda records, _: [
            {**record, "distance_km": index + 0.5}
            for index, record in enumerate(records)
        ]
        service = PreferenceService(schools, evaluation, locations, Path("."))
        family = FamilyDetails(
            dob=dt.date(2023, 1, 1),
            admission_date=dt.date(2026, 1, 1),
            gross_household_income=4_500,
        )
        indexes = ({"pages": []}, {"chunks": []})

        with patch.object(service, "_resources", return_value=indexes):
            context = service.build_conversation_context(
                message="Compare my selected schools.",
                profile={"preferences": {"spark_certified": {"value": True}}},
                selected_school_ids=["CENTRE:A"],
                eligible_school_ids=["CENTRE:B"],
                excluded_school_ids=["CENTRE:C"],
                family=family,
                home_postal_code="123456",
            )

        self.assertEqual(context.selected_schools[0].facts["name"], "Trusted A")
        self.assertEqual(context.eligible_schools[0].facts["distance_km"], 0.5)
        self.assertEqual(context.excluded_schools[0].school_id, "CENTRE:C")
        self.assertEqual(context.family.gross_household_income, 4_500)
        self.assertEqual(context.catalogue_version, "catalogue-123")
        self.assertTrue(context.selected_school_evidence.available)
        self.assertTrue(context.general_knowledge_evidence.available)
        self.assertEqual(evaluation.evaluate.call_count, 3)

    def test_active_school_id_is_resolved_instead_of_trusting_profile_facts(self):
        schools = Mock()
        schools.catalogue_version = "1"
        evaluation = Mock(return_value=None)
        evaluation.evaluate.return_value = [evaluated("CENTRE:A", "Trusted Name")]
        service = PreferenceService(schools, evaluation, Mock(), Path("."))

        with patch.object(service, "_resources", return_value=(None, None)):
            context = service.build_conversation_context(
                message="Tell me about this school.",
                profile={"active_school": {"school_id": "CENTRE:A", "name": "Forged Name"}},
                selected_school_ids=[], eligible_school_ids=[], excluded_school_ids=[],
                family=FamilyDetails(
                    dob=dt.date(2023, 1, 1), admission_date=dt.date(2026, 1, 1),
                    gross_household_income=4_500,
                ),
                home_postal_code=None,
            )

        self.assertEqual(context.selected_school_ids, ["CENTRE:A"])
        self.assertEqual(context.selected_schools[0].facts["name"], "Trusted Name")
        self.assertEqual(context.profile["active_school"]["name"], "Trusted Name")
        self.assertFalse(context.selected_school_evidence.available)


if __name__ == "__main__":
    unittest.main()
