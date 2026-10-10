import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, ToolMessage

from SystemCode.src.backend.agents.contracts import InitialConversationContext
from SystemCode.src.backend.agents.conversation_loop import (
    ConversationLoopError, LoopLimits, run_conversation_loop,
)
from SystemCode.src.backend.services.conversation_context_service import CAPABILITIES
from SystemCode.src.backend.services.conversation_tool_service import ConversationToolService
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.repositories.school_repository import SchoolRepository


def call(name, args=None, id="call:1"):
    return {"name": name, "args": args or {}, "id": id, "type": "tool_call"}


class ScriptedModel:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.messages = []
        self.names = []

    def bind_tools(self, tools):
        self.names = [tool.name for tool in tools]
        return self

    def invoke(self, messages):
        self.messages.append(list(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response(messages) if callable(response) else response


class LlmFirstLoopTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        catalogue = Path(directory.name) / "schools.json"
        catalogue.write_text(json.dumps([
            {"school_id": "CENTRE:A", "name": "School A", "base_fee": 900,
             "care_levels": ["Nursery (4 yrs old)"], "second_languages_offered": "Chinese"},
            {"school_id": "CENTRE:B", "name": "School B", "base_fee": 800,
             "care_levels": ["Nursery (4 yrs old)"], "second_languages_offered": "Malay"},
        ]))
        self.schools = SchoolRepository(catalogue)
        self.locations = Mock()

    def service(self, message="Hi", **context):
        return ConversationToolService(InitialConversationContext(
            message=message, catalogue_version=self.schools.catalogue_version,
            capabilities=context.pop("capabilities", list(CAPABILITIES)), **context,
        ), self.schools, EvaluationService(self.schools), self.locations)

    async def run_loop(self, service, model, **kwargs):
        return await run_conversation_loop(service.initial_context, service, model=model, **kwargs)

    async def rejected(self, service, model, reason=None, **kwargs):
        before = service.staged_profile
        with self.assertRaises(ConversationLoopError) as error:
            await self.run_loop(service, model, **kwargs)
        if reason:
            self.assertEqual(error.exception.reason, reason)
        self.assertEqual(service.staged_profile, before)
        with self.assertRaises(ValueError):
            service.export_validated_state(response_validated=True)

    async def test_every_valid_turn_calls_model_first_with_full_permitted_registry(self):
        for message in ("Hi", "What can you help with?", "Make that required",
                        "Which is closest?", "Please reset and compare fees"):
            with self.subTest(message=message):
                service = self.service(message)
                before = service.staged_profile
                model = ScriptedModel(AIMessage(content="What would you like to explore?"))
                with patch.object(service, "invoke", side_effect=AssertionError("unexpected tool")), patch(
                    "SystemCode.src.backend.services.preference_service.classify_intent",
                    side_effect=AssertionError("unexpected routing"),
                ):
                    candidate = await self.run_loop(service, model)
                self.assertEqual(model.names, list(CAPABILITIES))
                self.assertEqual(len(model.messages), 1)
                self.assertEqual(candidate.tool_calls, 0)
                self.assertEqual(service.staged_profile, before)
                self.locations.attach_distances.assert_not_called()

    async def test_follow_up_context_and_ambiguous_reference_allow_clarification(self):
        service = self.service("Does it have transport?", selected_schools=[
            {"school_id": "CENTRE:A", "name": "School A"},
            {"school_id": "CENTRE:B", "name": "School B"},
        ], recent_exchanges=[{"user": "Compare these schools", "assistant": "School A and School B."}])
        def clarify(messages):
            context = json.loads(messages[1].content)
            self.assertEqual(len(context["selected_schools"]), 2)
            self.assertEqual(context["recent_exchanges"][0]["user"], "Compare these schools")
            return AIMessage(content="Do you mean School A or School B?")
        candidate = await self.run_loop(service, ScriptedModel(clarify))
        self.assertEqual(candidate.answer, "Do you mean School A or School B?")
        self.assertFalse(candidate.results)

    async def test_mixed_paraphrases_and_dependent_calls_read_updated_state(self):
        for message in ("Chinese is essential; find matching schools and their fees",
                        "Show fees for centres after making Chinese a must"):
            service = self.service(message)
            def select_fee(messages):
                ranked = json.loads(messages[-1].content)
                self.assertEqual(ranked["data"]["profile_used"]["hard_constraints"]["language"], "Chinese")
                ids = [r["school_id"] for r in ranked["data"]["records"]]
                self.assertEqual(ids, ["CENTRE:A"])
                return AIMessage(content="", tool_calls=[call("read_school_facts", {
                    "school_ids": ids, "operation": "fees"}, "call:3")])
            model = ScriptedModel(
                AIMessage(content="", tool_calls=[
                    call("update_preferences", {"set": [{"attribute": "language", "value": "Chinese", "importance": "required"}]}),
                    call("search_rank_compare_schools", id="call:2"),
                ]), select_fee, AIMessage(content="Chinese is required; School A matches. Its listed fee is 900."),
            )
            candidate = await self.run_loop(service, model)
            self.assertEqual((candidate.model_calls, candidate.tool_calls), (3, 3))
            self.assertTrue(all(r.state_revision == 1 for r in candidate.results))
            self.assertEqual([m.tool_call_id for m in model.messages[-1] if isinstance(m, ToolMessage)],
                             ["call:1", "call:2", "call:3"])
            self.assertEqual(service.initial_context.profile, {})
            # Loop success is not an export or persistence commit.
            self.assertEqual(service.export_validated_state(response_validated=True)["hard_constraints"]["language"], "Chinese")

    async def test_missing_input_reaches_model_and_can_recover_from_user_context(self):
        service = self.service("Which is nearest to postal code 123456?")
        self.locations.attach_distances.side_effect = lambda records, postal: [{**r, "distance_km": 1.0} for r in records]
        def recover(messages):
            result = json.loads(messages[-1].content)
            self.assertEqual(result["status"], "needs_input")
            self.assertIn("home_postal_code", result["missing_inputs"])
            return AIMessage(content="", tool_calls=[call("find_nearby_schools", {"postal_code": "123456"}, "call:2")])
        candidate = await self.run_loop(service, ScriptedModel(
            AIMessage(content="", tool_calls=[call("find_nearby_schools")]),
            recover, AIMessage(content="Both schools are 1 km away."),
        ))
        self.assertEqual([r.status for r in candidate.results], ["needs_input", "ok"])
        self.locations.attach_distances.assert_called_once()

    async def test_missing_input_can_end_with_model_clarification(self):
        service = self.service("Which is closest?")
        candidate = await self.run_loop(service, ScriptedModel(
            AIMessage(content="", tool_calls=[call("find_nearby_schools")]),
            AIMessage(content="What is your six-digit home postal code?"),
        ))
        self.assertEqual(candidate.results[0].status, "needs_input")
        self.assertIn("postal code", candidate.answer)

    async def test_access_scope_invalid_arguments_and_duplicate_call_ids_fail_closed(self):
        invalid = [
            [call("unknown")],
            [call("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "secret"})],
            [call("read_school_facts", {"school_ids": ["UNKNOWN"], "operation": "fees"})],
            [call("find_nearby_schools"), call("find_nearby_schools")],
            [call("find_nearby_schools", id="")],
        ]
        for calls in invalid:
            await self.rejected(self.service(), ScriptedModel(AIMessage(content="", tool_calls=calls)))
        service = self.service(capabilities=["find_nearby_schools"])
        model = ScriptedModel(AIMessage(content="", tool_calls=[call("reset_continue_preferences", {"operation": "reset"})]))
        await self.rejected(service, model, "invalid_tool_call")
        self.assertEqual(model.names, ["find_nearby_schools"])
        await self.rejected(self.service(), ScriptedModel(
            AIMessage(content="", tool_calls=[call("find_nearby_schools")]),
            AIMessage(content="", tool_calls=[call("find_nearby_schools")]),
        ), "invalid_tool_call")

    async def test_malformed_calls_and_model_responses_are_rejected(self):
        responses = ["invalid", AIMessage(content=""), AIMessage(content="x" * 801),
                     AIMessage(content=[{"type": "text", "text": "Hi"}]),
                     AIMessage(content="", invalid_tool_calls=[{"name": "find_nearby_schools", "args": "{", "id": "bad", "error": "bad"}])]
        for response in responses:
            await self.rejected(self.service(), ScriptedModel(response))

    async def test_model_tool_context_and_output_bounds(self):
        await self.rejected(self.service(), ScriptedModel(AIMessage(content="", tool_calls=[call("find_nearby_schools")])),
                            "model_limit", limits=LoopLimits(model_calls=1))
        await self.rejected(self.service(), ScriptedModel(AIMessage(content="", tool_calls=[call("find_nearby_schools")])),
                            "tool_limit", limits=LoopLimits(tool_calls=0))
        model = ScriptedModel(AIMessage(content="Hi"))
        await self.rejected(self.service(), model, "context_limit", limits=LoopLimits(context_bytes=1))
        self.assertFalse(model.messages)
        await self.rejected(self.service(), ScriptedModel(AIMessage(content="Hi")),
                            "output_limit", limits=LoopLimits(model_output_bytes=1))
        service = self.service()
        model = ScriptedModel(AIMessage(content="", tool_calls=[call("find_nearby_schools")]), AIMessage(content="Hi"))
        # Tool result plus call history pushes cumulative context past its bound.
        candidate = await self.run_loop(service, model)
        from SystemCode.src.backend.agents.conversation_loop import _json_bytes
        registry = service.registered_tools()
        schemas = [{"name": t.name, "description": t.description, "parameters": t.args_schema.model_json_schema()} for t in registry]
        size = _json_bytes({"tools": schemas, "messages": [m.model_dump(mode="json") for m in model.messages[0]]})
        await self.rejected(self.service(), ScriptedModel(AIMessage(content="", tool_calls=[call("find_nearby_schools")])),
                            "context_limit", limits=LoopLimits(context_bytes=size))
        self.assertEqual(candidate.tool_calls, 1)

    async def test_failure_after_staged_mutation_rolls_back_and_hides_provider_error(self):
        for response in (RuntimeError("private provider details"), AIMessage(content="x" * 801)):
            service = self.service()
            await self.rejected(service, ScriptedModel(
                AIMessage(content="", tool_calls=[call("update_preferences", {"set": [
                    {"attribute": "language", "value": "Chinese", "importance": "required"}]} )]), response,
            ))

    async def test_elapsed_limit_closes_transaction_before_late_mutation(self):
        service = self.service()
        before = service.staged_profile
        release, finished = threading.Event(), threading.Event()
        original = service._stage
        def delayed(candidate, changed):
            release.wait(2)
            try:
                return original(candidate, changed)
            finally:
                finished.set()
        with patch.object(service, "_stage", side_effect=delayed):
            try:
                await self.rejected(service, ScriptedModel(AIMessage(content="", tool_calls=[call("update_preferences", {"set": [
                    {"attribute": "language", "value": "Chinese", "importance": "required"}]} )])),
                    "elapsed_limit", limits=LoopLimits(elapsed_seconds=0.05))
            finally:
                release.set()
                await asyncio.to_thread(finished.wait, 2)
        self.assertTrue(finished.is_set())
        self.assertEqual(service.staged_profile, before)

    async def test_timeout_and_cancellation_abort_without_retry(self):
        service = self.service()
        model = ScriptedModel(TimeoutError("private details"))
        await self.rejected(service, model, "elapsed_limit")
        self.assertEqual(len(model.messages), 1)
        started, release = threading.Event(), threading.Event()
        def block(messages):
            started.set()
            release.wait(2)
            return AIMessage(content="Hi")
        service = self.service()
        task = asyncio.create_task(self.run_loop(service, ScriptedModel(block)))
        try:
            await asyncio.to_thread(started.wait, 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaises(ValueError):
                service.export_validated_state(response_validated=True)
        finally:
            release.set()

    async def test_mismatched_context_cannot_broaden_access_or_change_turn(self):
        service = self.service(capabilities=["find_nearby_schools"])
        with self.assertRaisesRegex(ConversationLoopError, "context_mismatch"):
            await run_conversation_loop(service.initial_context.model_copy(update={"capabilities": list(CAPABILITIES)}),
                                        service, model=ScriptedModel(AIMessage(content="Hi")))

    async def test_mutation_limit_and_tool_provider_failure_rollback(self):
        await self.rejected(self.service(), ScriptedModel(AIMessage(content="", tool_calls=[
            call("reset_continue_preferences", {"operation": "reset"}, f"call:{i}") for i in range(5)
        ])))
        service = self.service()
        with patch.object(service, "_general_retriever_loader", side_effect=RuntimeError("private provider error")):
            await self.rejected(service, ScriptedModel(AIMessage(content="", tool_calls=[
                call("update_preferences", {"set": [{"attribute": "language", "value": "Chinese", "importance": "required"}]}),
                call("search_general_guidance", {"query": "What is Montessori?"}, "call:2"),
            ])))

    async def test_binding_failure_aborts_and_overall_deadline_includes_model_call(self):
        model = ScriptedModel()
        with patch.object(model, "bind_tools", side_effect=RuntimeError("private configuration")):
            await self.rejected(self.service(), model, "execution_error")
        ticks = [0.0]
        def slow_model(messages):
            ticks[0] = 31.0
            return AIMessage(content="Hi")
        await self.rejected(self.service(), ScriptedModel(slow_model), "elapsed_limit", clock=lambda: ticks[0])

    async def test_unavailable_evidence_is_structured_and_model_can_explain_gap(self):
        service = self.service("What is Montessori?")
        def explain(messages):
            self.assertEqual(json.loads(messages[-1].content)["status"], "unavailable")
            return AIMessage(content="The guidance source is unavailable. Please try again later.")
        candidate = await self.run_loop(service, ScriptedModel(
            AIMessage(content="", tool_calls=[call("search_general_guidance", {"query": "Montessori"})]), explain,
        ))
        self.assertEqual(candidate.results[0].status, "unavailable")
