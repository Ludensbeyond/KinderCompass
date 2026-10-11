import os
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

    def test_help_and_introductions_reply_in_every_conversation_mode(self):
        messages = (
            "what can you do", " WHAT CAN YOU DO? ", "Hi, what can you do?",
            "What do you do?", "What can you help me with?", "How can you help me?",
            "Can you help me?", "Could you tell me what you can do?",
            "What are your capabilities?", "Tell me about your features",
            "Who are you?", "What is KinderCompass?", "What's KinderCompass?",
            "How do I use this app?", "How does KinderCompass work?", "Help",
            "Help me please!",
        )
        for mode in ("deterministic", "shadow", "agent"):
            for message in messages:
                with self.subTest(mode=mode, message=message), patch.dict(
                    os.environ, {"CONVERSATION_AGENT_MODE": mode},
                ):
                    result = self.handle(message)
                    PreferenceResponse.model_validate(result)
                    self.assertIn("I'm KinderCompass", result["question"])
                    self.assertIn("compare selected schools", result["question"])
                    self.assertIn("estimate fees and subsidies", result["question"])
                    self.assertIn("What is Montessori?", result["question"])
                    self.assertFalse(result["ready_to_search"])
        self.service.schools.assert_not_called()
        self.service.evaluation.assert_not_called()
        self.service.locations.assert_not_called()

    def test_help_preserves_saved_state_and_pending_flows(self):
        for pending in (
            {},
            {"pending": {"kind": "language", "value": "Chinese"}},
            {"pending_contradiction": {"question": "Keep Chinese or use Malay?"}},
            {"pending_relaxation": {"question": "Increase the distance limit?"}},
        ):
            with self.subTest(pending=pending):
                profile = {
                    "hard_constraints": {"language": "Chinese"},
                    "active_school": {"school_id": "CENTRE:A", "name": "School A"},
                    "decision_state": {"current_goal": "update_preferences"},
                    **pending,
                }
                before = deepcopy(profile)
                result = self.handle("What can you do?", profile)
                self.assertEqual(result["profile"], before)
                self.assertEqual(profile, before)
                self.assertEqual(result["ready_to_search"], not bool(pending))
                self.assertIn("I'm KinderCompass", result["question"])
                if "pending" in pending:
                    self.assertIn("required or preferred", result["question"])
                elif pending:
                    self.assertIn(next(iter(pending.values()))["question"], result["question"])
                else:
                    self.assertIn("Show recommendations", result["question"])

    def test_help_with_specific_requests_continues_normal_chat(self):
        for message in (
            "Can you help me find a preschool?",
            "What can you do about preschool subsidies?",
            "Help me compare selected schools",
            "What can you do? I want Chinese to be required.",
            "What can you do? Reset preferences.",
        ):
            with self.subTest(message=message), patch(
                "SystemCode.src.backend.services.preference_service.classify_intent",
            ) as classify:
                with self.assertRaisesRegex(AssertionError, "unexpected school"):
                    self.service.handle(
                        message=message, profile=None,
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

    async def test_capabilities_return_through_http_and_record_one_answer(self):
        from SystemCode.src.backend import main

        with (
            patch("SystemCode.src.backend.services.preference_service.classify_intent", side_effect=AssertionError("unexpected model call")),
            patch.object(main.PREFERENCE_SERVICE, "build_conversation_context", side_effect=AssertionError("unexpected lookup")),
            patch.object(main.CHAT_FEEDBACK_SERVICE, "record_answer", return_value="00000000-0000-0000-0000-000000000123") as record,
        ):
            async with ASGITestClient(main.app, timeout_seconds=2) as client:
                response = await client.post("/api/preferences", json={"message": "what can you do"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("I'm KinderCompass", response.json()["question"])
            self.assertFalse(response.json()["ready_to_search"])
            self.assertIsNotNone(response.json()["answer_id"])
            record.assert_called_once()

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
