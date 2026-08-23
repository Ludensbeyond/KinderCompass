import tempfile
import unittest
import uuid
from pathlib import Path

from pydantic import ValidationError

from SystemCode.src.backend.domain.models import ChatFeedbackRequest
from SystemCode.src.backend.services.chat_feedback_service import (
    ChatAnswerNotFoundError,
    ChatFeedbackService,
)


class ChatFeedbackServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = ChatFeedbackService(Path(self.temporary.name) / "chat-feedback.sqlite3")
        self.session_id = uuid.uuid4()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _answer(*, intent: str = "ask_general_knowledge", category: str = "authoritative_fact") -> dict:
        return {
            "profile": {"intent": intent, "intent_method": "rules"},
            "evidence_category": category,
            "citations": [{"url": "https://example.test"}],
            "question": "This text must not be persisted",
        }

    def test_records_privacy_minimised_answer_and_feedback(self) -> None:
        answer_id = self.service.record_answer(self._answer())
        request = ChatFeedbackRequest(
            answer_id=answer_id, anonymous_session_id=self.session_id,
            helpful=True, consent=True,
        )
        self.service.record_feedback(request)

        summary = self.service.summary()

        self.assertEqual(summary["responses"], 1)
        self.assertEqual(summary["helpful_rate"], 1.0)
        self.assertEqual(summary["segments"][0]["intent"], "ask_general_knowledge")
        with self.service._connect() as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(chat_answer_snapshots)")}
        self.assertNotIn("question", columns)
        self.assertNotIn("answer", columns)

    def test_summary_segments_intent_and_evidence_category(self) -> None:
        first = self.service.record_answer(self._answer())
        second = self.service.record_answer(self._answer(intent="comparison", category="calculated_estimate"))
        for answer_id, helpful in ((first, True), (second, False)):
            self.service.record_feedback(ChatFeedbackRequest(
                answer_id=answer_id, anonymous_session_id=self.session_id,
                helpful=helpful, consent=True,
            ))
        summary = self.service.summary()
        self.assertEqual(summary["responses"], 2)
        self.assertEqual(summary["helpful_rate"], 0.5)
        self.assertEqual(len(summary["segments"]), 2)

    def test_rejects_unknown_answer_and_missing_consent(self) -> None:
        with self.assertRaises(ChatAnswerNotFoundError):
            self.service.record_feedback(ChatFeedbackRequest(
                answer_id=uuid.uuid4(), anonymous_session_id=self.session_id,
                helpful=False, consent=True,
            ))
        with self.assertRaises(ValidationError):
            ChatFeedbackRequest.model_validate({
                "answer_id": str(uuid.uuid4()),
                "anonymous_session_id": str(self.session_id),
                "helpful": True,
                "consent": False,
            })


if __name__ == "__main__":
    unittest.main()
