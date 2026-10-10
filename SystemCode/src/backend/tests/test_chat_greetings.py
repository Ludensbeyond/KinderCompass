import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from SystemCode.src.backend.domain.models import PreferenceResponse
from SystemCode.src.backend.services.preference_service import PreferenceService
from SystemCode.src.backend.tests.asgi_test_client import ASGITestClient


class ChatGreetingTests(unittest.TestCase):
    def setUp(self):
        self.service = PreferenceService(Mock(), Mock(), Mock(), Path("."))
        self.service.build_conversation_context = Mock(side_effect=AssertionError("unexpected school or location lookup"))

    def handle(self, message, profile=None):
        with patch("SystemCode.src.backend.services.preference_service.classify_intent", side_effect=AssertionError("unexpected model call")):
            return self.service.handle(
                message=message, profile=profile,
                selected_school_ids=["CENTRE:A"], eligible_school_ids=["CENTRE:A"],
                excluded_school_ids=[], family=None, home_postal_code="123456",
            )

    def test_greetings_reply_without_external_dependencies(self):
        for message in ("Hi", " HELLO! ", "hey", "Good morning."):
            with self.subTest(message=message):
                result = self.handle(message)
                PreferenceResponse.model_validate(result)
                self.assertTrue(result["question"].startswith("Hi!"))
                self.assertFalse(result["ready_to_search"])

    def test_greeting_preserves_preferences_and_pending_decision(self):
        profile = {
            "hard_constraints": {"language": "Chinese"},
            "pending_contradiction": {"attribute": "language", "question": "Keep Chinese or use Malay?"},
            "decision_state": {"current_goal": "contradiction"},
        }
        before = deepcopy(profile)
        result = self.handle("Hi", profile)
        self.assertEqual(result["profile"], before)
        self.assertEqual(profile, before)
        self.assertIn("Keep Chinese or use Malay?", result["question"])
        self.assertFalse(result["ready_to_search"])

    def test_greeting_keeps_saved_preferences_ready_to_search(self):
        result = self.handle("Hi", {"hard_constraints": {"language": "Chinese"}})
        self.assertTrue(result["ready_to_search"])
        self.assertIn("Show recommendations", result["question"])

    def test_greeting_with_a_request_continues_normal_chat(self):
        with patch("SystemCode.src.backend.services.preference_service.classify_intent") as classify:
            with self.assertRaisesRegex(AssertionError, "unexpected school"):
                self.service.handle(
                    message="Hi, I want Chinese", profile=None,
                    selected_school_ids=[], eligible_school_ids=[], excluded_school_ids=[],
                    family=None, home_postal_code=None,
                )
            classify.assert_called_once()


class ChatGreetingApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import os
        rollout = patch.dict(os.environ, {"CONVERSATION_FLOW_MODE": "legacy"})
        rollout.start()
        self.addCleanup(rollout.stop)

    async def test_hi_returns_through_http_and_records_one_answer(self):
        from SystemCode.src.backend import main

        with (
            patch("SystemCode.src.backend.services.preference_service.classify_intent", side_effect=AssertionError("unexpected model call")),
            patch.object(main.CHAT_FEEDBACK_SERVICE, "record_answer", return_value="00000000-0000-0000-0000-000000000123") as record,
        ):
            async with ASGITestClient(main.app, timeout_seconds=2) as client:
                response = await client.post("/api/preferences", json={"message": "Hi"})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["question"].startswith("Hi!"))
            record.assert_called_once()
