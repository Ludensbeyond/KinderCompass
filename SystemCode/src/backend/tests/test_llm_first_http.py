import asyncio
import json
import os
import threading
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from SystemCode.src.backend.domain.models import PreferenceRequest, PreferenceResponse
from SystemCode.src.backend.services.conversation_history_service import ConversationHistoryConflict, ConversationHistoryService
from SystemCode.src.backend.services.preference_service import PreferenceService
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.tests.asgi_test_client import ASGITestClient
from SystemCode.src.backend.tests import test_llm_first_loop as fixtures
from SystemCode.src.backend.tests.test_llm_first_response import final, claim

ScriptedModel, call = fixtures.ScriptedModel, fixtures.call


class LlmFirstHttpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixtures.LlmFirstLoopTests.setUp(self)
        self.service = PreferenceService(self.schools, EvaluationService(self.schools), self.locations, Path("."))
        self.history = ConversationHistoryService()
        self.memory = Mock()
        self.feedback = Mock()
        self.feedback.record_answer.return_value = str(uuid.uuid4())
        self.session = str(uuid.uuid4())

    async def turn(self, model, **kwargs):
        request = PreferenceRequest(message=kwargs.pop("message", "Hi"), **kwargs)
        return await self.service.handle_llm_first(request, history=self.history,
            memory=self.memory, feedback=self.feedback, model_factory=lambda: model)

    async def test_http_uses_model_first_and_preserves_response_fields(self):
        from SystemCode.src.backend import main
        for message in ("Hi", "What can you do?", "Which is closest?", "Make that required"):
            model = ScriptedModel(final("Which details would you like to discuss?", kind="clarification"))
            with (patch.object(main, "PREFERENCE_SERVICE", self.service),
                  patch.object(main, "CONVERSATION_HISTORY_SERVICE", self.history),
                  patch.object(main, "CONVERSATION_MEMORY_SERVICE", self.memory),
                  patch.object(main, "CHAT_FEEDBACK_SERVICE", self.feedback),
                  patch("SystemCode.src.backend.agents.model_factory.create_conversation_agent_model", return_value=model),
                  patch("SystemCode.src.backend.services.preference_service.classify_intent", side_effect=AssertionError("semantic routing")),
                  patch.object(self.service, "build_conversation_context", side_effect=AssertionError("eager evaluation"))):
                async with ASGITestClient(main.app, timeout_seconds=3) as client:
                    response = await client.post("/api/preferences/llm-first", json={"message": message})
                self.assertEqual(response.status_code, 200)
                public = PreferenceResponse.model_validate(response.json())
                self.assertEqual(public.question, "Which details would you like to discuss?")
                self.assertEqual(public.answer_method, "llm_first")
                self.assertIsNotNone(public.answer_id)
                self.assertEqual(len(model.messages), 1)
        self.locations.assert_not_called()
        self.memory.save.assert_not_called()
        self.assertEqual(self.feedback.record_answer.call_count, 4)

    async def test_state_history_and_memory_commit_once_after_validated_response(self):
        answer = "Chinese is now required."
        model = ScriptedModel(AIMessage(content="", tool_calls=[call("update_preferences", {"set": [
            {"attribute": "language", "value": "Chinese", "importance": "required"}]})]),
            final(answer, [claim(answer, "Chinese", path="/data/staged_profile/hard_constraints/language", school=None)]))
        with patch.object(self.history, "commit", wraps=self.history.commit) as commit:
            first = await self.turn(model, message="Chinese is required", anonymous_session_id=self.session,
                                    remember_conversation=True, remember_preferences=True)
        commit.assert_called_once()
        self.memory.save.assert_called_once_with(uuid.UUID(self.session), first["profile"])
        self.assertTrue(first["ready_to_search"])
        second_model = ScriptedModel(final("What else matters to your family?"))
        await self.turn(second_model, profile=first["profile"], anonymous_session_id=self.session, remember_conversation=True)
        context = json.loads(second_model.messages[0][1].content)
        self.assertEqual(context["recent_exchanges"][0]["assistant"], answer)
        self.assertEqual(context["profile"]["hard_constraints"]["language"], "Chinese")
        with self.assertRaises(ConversationHistoryConflict):
            await self.turn(ScriptedModel(final("Hi!")), anonymous_session_id=self.session)
        self.assertEqual(self.memory.save.call_count, 1)

    async def test_failure_after_staged_mutation_discards_state_history_and_memory(self):
        original = {"hard_constraints": {"language": "Chinese"}}
        for fault in (RuntimeError("SECRET"), final("Unsupported $999.")):
            model = ScriptedModel(AIMessage(content="", tool_calls=[call("reset_continue_preferences", {"operation": "reset"})]), fault, fault, fault)
            result = await self.turn(model, profile=original, anonymous_session_id=self.session,
                                     remember_preferences=True, remember_conversation=True)
            self.assertEqual(result["profile"], original)
            self.assertEqual(result["answer_method"], "service_error")
            self.assertNotIn("SECRET", result["question"])
            lease = self.history.begin(self.session, retain=True)
            self.assertFalse(lease.exchanges)
            self.history.abort(lease)
        self.memory.save.assert_not_called()

    async def test_unspecified_strength_stages_choice_and_followup_resolves_it(self):
        model = ScriptedModel(AIMessage(content="", tool_calls=[call("update_preferences", {
            "set": [{"attribute": "language", "value": "Chinese"}]})]),
            final("Should Chinese be required or preferred?", kind="clarification"))
        first = await self.turn(model, message="I want Chinese", anonymous_session_id=self.session,
                                remember_conversation=True)
        self.assertEqual(first["answer_method"], "llm_first")
        self.assertEqual(first["profile"]["pending"]["value"], "Chinese")
        self.assertFalse(first["profile"].get("hard_constraints", {}).get("language"))
        self.assertFalse(first["ready_to_search"])
        answer = "Chinese is now required."
        model = ScriptedModel(AIMessage(content="", tool_calls=[call("reset_continue_preferences", {
            "operation": "resolve_strength", "choice": "required"})]),
            final(answer, [claim(answer, "Chinese",
                path="/data/staged_profile/hard_constraints/language", school=None)]))
        second = await self.turn(model, message="Make that required", profile=first["profile"],
                                 anonymous_session_id=self.session, remember_conversation=True)
        self.assertEqual(second["profile"]["hard_constraints"]["language"], "Chinese")
        self.assertNotIn("pending", second["profile"])
        self.assertTrue(second["ready_to_search"])
        self.memory.save.assert_not_called()

    async def test_failure_discards_new_pending_strength(self):
        model = ScriptedModel(AIMessage(content="", tool_calls=[call("update_preferences", {
            "set": [{"attribute": "language", "value": "Chinese"}]})]), RuntimeError("provider"))
        result = await self.turn(model, message="I want Chinese", anonymous_session_id=self.session,
                                 remember_conversation=True, remember_preferences=True)
        self.assertEqual(result["profile"], {})
        self.assertEqual(result["answer_method"], "service_error")
        self.assertFalse(self.history._sessions[self.session].exchanges)
        self.memory.save.assert_not_called()

    async def test_no_history_without_consent_and_session_isolation(self):
        for consent in (True, False):
            session = str(uuid.uuid4())
            await self.turn(ScriptedModel(final("Let's discuss School A.")), anonymous_session_id=session, remember_conversation=consent)
            for selected_session, retain in ((session, consent), (str(uuid.uuid4()), True), (None, False), (session, False)):
                model = ScriptedModel(final("Which school?", kind="clarification"))
                profile = {} if selected_session != session else self.history._sessions[session].profile
                await self.turn(model, message="Does it provide transport?", profile=profile,
                                anonymous_session_id=selected_session, remember_conversation=retain)
                context = json.loads(model.messages[0][1].content)
                if selected_session != session or not retain:
                    self.assertFalse(context["recent_exchanges"])
        self.memory.save.assert_not_called()

    async def test_overlap_and_forget_during_turn_cannot_commit(self):
        from SystemCode.src.backend import main
        started, release = threading.Event(), threading.Event()
        def wait(messages):
            started.set()
            release.wait(3)
            return final("Hello!")
        pending = asyncio.create_task(self.turn(ScriptedModel(wait), anonymous_session_id=self.session,
            remember_preferences=True, remember_conversation=True))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            with self.assertRaises(ConversationHistoryConflict):
                await self.turn(ScriptedModel(final("Hi!")), anonymous_session_id=self.session)
            with (patch.object(main, "CONVERSATION_HISTORY_SERVICE", self.history),
                  patch.object(main, "CONVERSATION_MEMORY_SERVICE", self.memory)):
                async with ASGITestClient(main.app, timeout_seconds=3) as client:
                    response = await client.post("/api/memory/forget", json={"anonymous_session_id": self.session})
                self.assertEqual(response.status_code, 200)
        finally:
            release.set()
        with self.assertRaises(ConversationHistoryConflict):
            await pending
        self.memory.save.assert_not_called()
        self.feedback.record_answer.assert_not_called()

    async def test_consent_validation_and_legacy_endpoint_compatibility(self):
        rollout = patch.dict(os.environ, {"CONVERSATION_FLOW_MODE": "legacy"})
        rollout.start()
        self.addCleanup(rollout.stop)
        from SystemCode.src.backend import main
        with (patch.object(main, "PREFERENCE_SERVICE", self.service),
              patch.object(main, "CHAT_FEEDBACK_SERVICE", self.feedback)):
            async with ASGITestClient(main.app, timeout_seconds=3) as client:
                for field in ("remember_conversation", "remember_preferences"):
                    response = await client.post("/api/preferences/llm-first", json={"message": "Hi", field: True})
                    self.assertEqual(response.status_code, 422)
                response = await client.post("/api/preferences", json={"message": "Hi"})
                self.assertEqual(response.status_code, 200)
                PreferenceResponse.model_validate(response.json())
        schema = main.app.openapi()
        properties = schema["components"]["schemas"]["PreferenceRequest"]["properties"]
        self.assertFalse(properties["remember_conversation"]["default"])
        self.assertIn("/api/preferences/llm-first", schema["paths"])

    async def test_storage_failure_aborts_lease_and_does_not_save(self):
        self.feedback.record_answer.side_effect = RuntimeError("storage down")
        with self.assertRaises(RuntimeError):
            await self.turn(ScriptedModel(final("Hello!")), anonymous_session_id=self.session,
                            remember_preferences=True, remember_conversation=True)
        self.memory.save.assert_not_called()
        lease = self.history.begin(self.session, retain=True)
        self.assertFalse(lease.exchanges)
        self.history.abort(lease)

    async def test_cancellation_releases_session(self):
        started, release = threading.Event(), threading.Event()
        def wait(messages):
            started.set()
            release.wait(3)
            return final("Hello!")
        pending = asyncio.create_task(self.turn(ScriptedModel(wait), anonymous_session_id=self.session))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
        finally:
            release.set()
        lease = self.history.begin(self.session, retain=True)
        self.history.abort(lease)
        self.memory.save.assert_not_called()
