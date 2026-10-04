import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from SystemCode.src.backend import main
from SystemCode.src.backend.domain.catalogue import SchoolRecord
from SystemCode.src.backend.domain.models import SchoolRatingRequest
from SystemCode.src.backend.services.school_rating_service import SchoolRatingService


class SchoolRatingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = SchoolRatingService(Path(self.temporary.name) / "school-ratings.sqlite3")
        self.session_id = uuid.uuid4()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def request(self, **changes) -> SchoolRatingRequest:
        values = {
            "anonymous_session_id": self.session_id,
            "overall": 5,
            "relationship": "visited",
            "consent": True,
            **changes,
        }
        return SchoolRatingRequest(**values)

    def test_keeps_written_reviews_and_drops_blank_text(self) -> None:
        self.service.record("CENTRE:A", self.request(
            review_text="  Warm teachers and a calm drop-off.  ",
        ))
        self.service.record("CENTRE:A", self.request(
            anonymous_session_id=uuid.uuid4(), overall=3, review_text="   ",
        ))
        summary = self.service.summary("CENTRE:A")
        self.assertEqual(summary.count, 2)
        self.assertEqual(len(summary.reviews), 1)
        self.assertEqual(summary.reviews[0].review_text, "Warm teachers and a calm drop-off.")
        self.assertEqual(summary.reviews[0].relationship, "visited")

    def test_records_consented_rating_and_summary(self) -> None:
        rating_id, summary = self.service.record("CENTRE:A", self.request())
        self.assertTrue(uuid.UUID(rating_id))
        self.assertEqual(summary.school_id, "CENTRE:A")
        self.assertEqual(summary.average, 5.0)
        self.assertEqual(summary.count, 1)
        self.assertEqual(summary.evidence_category, "parent_sentiment")

    def test_updates_the_same_session_rating(self) -> None:
        self.service.record("CENTRE:A", self.request(overall=2))
        self.service.record("CENTRE:A", self.request(overall=4))
        summary = self.service.summary("CENTRE:A")
        self.assertEqual(summary.count, 1)
        self.assertEqual(summary.average, 4.0)

    def test_averages_distinct_sessions(self) -> None:
        self.service.record("CENTRE:A", self.request(overall=5))
        self.service.record("CENTRE:A", self.request(
            anonymous_session_id=uuid.uuid4(), overall=3, relationship="enrolled",
        ))
        summary = self.service.summary("CENTRE:A")
        self.assertEqual(summary.count, 2)
        self.assertEqual(summary.average, 4.0)

    def test_empty_summary_and_batch_lookup(self) -> None:
        self.service.record("CENTRE:A", self.request())
        summaries = self.service.summaries(["CENTRE:A", "CENTRE:B"])
        self.assertEqual(summaries["CENTRE:A"].count, 1)
        self.assertEqual(summaries["CENTRE:B"].count, 0)
        self.assertIsNone(summaries["CENTRE:B"].average)

    def test_rejects_missing_consent(self) -> None:
        with self.assertRaises(ValidationError):
            self.request(consent=False)


class SchoolRatingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = SchoolRatingService(Path(self.temporary.name) / "school-ratings.sqlite3")
        self._original = main.SCHOOL_RATING_SERVICE
        main.SCHOOL_RATING_SERVICE = self.service
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.SCHOOL_RATING_SERVICE = self._original
        self.temporary.cleanup()

    def payload(self, **changes) -> dict:
        values = {
            "anonymous_session_id": str(uuid.uuid4()),
            "overall": 4,
            "relationship": "enrolled",
            "consent": True,
            **changes,
        }
        return values

    def test_unknown_school_is_404(self) -> None:
        response = self.client.post(
            "/api/schools/CENTRE:DOES_NOT_EXIST/ratings", json=self.payload()
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_consent_is_422(self) -> None:
        response = self.client.post(
            "/api/schools/CENTRE:A/ratings", json=self.payload(consent=False)
        )
        self.assertEqual(response.status_code, 422)

    def test_records_rating_for_known_school(self) -> None:
        school = SchoolRecord.model_validate({
            "school_id": "CENTRE:A", "name": "Example Preschool",
        })
        with patch.object(main.SCHOOL_REPOSITORY, "get", return_value=school):
            response = self.client.post("/api/schools/CENTRE:A/ratings", json=self.payload(
                review_text="The visit was organised and the classrooms were bright.",
            ))
            summary = self.client.get("/api/schools/CENTRE:A/ratings")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "recorded")
        self.assertEqual(body["summary"]["count"], 1)
        self.assertEqual(body["summary"]["average"], 4.0)
        self.assertEqual(body["summary"]["reviews"][0]["review_text"], "The visit was organised and the classrooms were bright.")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["count"], 1)
        self.assertEqual(len(summary.json()["reviews"]), 1)


if __name__ == "__main__":
    unittest.main()
