import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from pydantic import ValidationError

from SystemCode.src.backend.domain.catalogue import EvaluatedSchool
from SystemCode.src.backend.domain.models import FeedbackRequest
from SystemCode.src.backend.services.feedback_service import (
    FeedbackSchoolMismatchError, FeedbackService, FeedbackSnapshotNotFoundError,
)


class FeedbackServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "feedback.sqlite3"
        self.service = FeedbackService(self.database)
        self.trace_id = uuid.uuid4()
        self.session_id = uuid.uuid4()
        self.centre = EvaluatedSchool.model_validate({
            "school_id": "CENTRE:A",
            "name": "Example Preschool",
            "status": "estimated",
            "eligible": True,
            "eligible_level": "Pre-Nursery (3 yrs old)",
            "programme_id": "full_day",
            "fee_before_subsidy": 900,
            "net_monthly_fee": 160,
            "preferred_programme": "full_day",
            "preferred_programme_available": True,
            "programme_options": [],
            "match_score": 85,
        })

    def tearDown(self):
        self.directory.cleanup()

    def request(self, **changes):
        values = {
            "trace_id": self.trace_id,
            "anonymous_session_id": self.session_id,
            "school_id": "CENTRE:A",
            "event_type": "rated",
            "reason": "good_match",
            "rating": 5,
            "consent": True,
            **changes,
        }
        return FeedbackRequest(**values)

    def test_records_minimal_snapshot_and_consented_feedback(self):
        self.service.record_snapshot(
            str(self.trace_id), [self.centre], catalogue_version="123"
        )
        event_id = self.service.record_feedback(self.request())
        self.assertTrue(uuid.UUID(event_id))
        with closing(sqlite3.connect(self.database)) as connection:
            snapshot = connection.execute(
                "SELECT catalogue_version, recommendations_json FROM recommendation_snapshots"
            ).fetchone()
            feedback = connection.execute(
                "SELECT event_type, rating FROM feedback_events"
            ).fetchone()
        self.assertEqual(snapshot[0], "123")
        self.assertNotIn("gross_household_income", snapshot[1])
        self.assertEqual(feedback, ("rated", 5))

    def test_rejects_feedback_without_consent(self):
        with self.assertRaises(ValidationError):
            self.request(consent=False)

    def test_rejects_unknown_snapshot_and_mismatched_school(self):
        with self.assertRaises(FeedbackSnapshotNotFoundError):
            self.service.record_feedback(self.request())
        self.service.record_snapshot(
            str(self.trace_id), [self.centre], catalogue_version="123"
        )
        with self.assertRaises(FeedbackSchoolMismatchError):
            self.service.record_feedback(self.request(school_id="CENTRE:B"))

    def test_snapshot_is_immutable_for_a_trace_id(self):
        self.service.record_snapshot(
            str(self.trace_id), [self.centre], catalogue_version="123"
        )
        changed = self.centre.model_copy(update={"net_monthly_fee": 999})
        with self.assertRaisesRegex(ValueError, "different recommendation snapshot"):
            self.service.record_snapshot(
                str(self.trace_id), [changed], catalogue_version="123"
            )


if __name__ == "__main__":
    unittest.main()
