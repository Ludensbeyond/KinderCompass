import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from SystemCode.src.backend.agents.config import ConversationFlowMode, get_conversation_flow_mode
from SystemCode.src.backend.agents.conversation_telemetry import TurnTelemetry
from SystemCode.src.backend.domain.models import PreferenceRequest
from SystemCode.src.backend.services.preference_service import PreferenceService
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.conversation_history_service import ConversationHistoryService
from SystemCode.src.backend.tests import test_llm_first_loop as fixtures
from SystemCode.src.backend.tests.test_llm_first_response import final, claim
from SystemCode.src.backend.tests.asgi_test_client import ASGITestClient


class RolloutTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixtures.LlmFirstLoopTests.setUp(self)
        self.service = PreferenceService(self.schools, EvaluationService(self.schools), self.locations, Path('.'))
        self.history = ConversationHistoryService()
        self.memory = Mock()
        self.feedback = Mock()
        self.feedback.record_answer.return_value = str(uuid.uuid4())

    async def request(self, model, mode=None, **body):
        from SystemCode.src.backend import main
        env = {"CONVERSATION_FLOW_MODE": mode or "", "OPENAI_WEB_RAG_MODEL": "gpt-4o-mini"}
        with (patch.dict(os.environ, env),
              patch.object(main, 'PREFERENCE_SERVICE', self.service),
              patch.object(main, 'CONVERSATION_HISTORY_SERVICE', self.history),
              patch.object(main, 'CONVERSATION_MEMORY_SERVICE', self.memory),
              patch.object(main, 'CHAT_FEEDBACK_SERVICE', self.feedback),
              patch('SystemCode.src.backend.agents.model_factory.create_conversation_agent_model', return_value=model)):
            async with ASGITestClient(main.app, timeout_seconds=4) as client:
                return await client.post('/api/preferences', json={"message": "Hi", **body})

    async def test_default_reaches_model_before_legacy_closest_gate(self):
        model = fixtures.ScriptedModel(final("What is your home postal code?", kind="clarification"))
        with patch.object(self.service, 'handle', side_effect=AssertionError('legacy routing')):
            response = await self.request(model, message="Which is closest?")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['answer_method'], 'llm_first')
        self.assertEqual(len(model.messages), 1)
        self.locations.assert_not_called()
        self.feedback.record_answer.assert_called_once()

    async def test_default_trace_executes_model_selected_tool(self):
        sentence = "Chinese is now required."
        model = fixtures.ScriptedModel(AIMessage(content='', tool_calls=[fixtures.call('update_preferences', {
            'set': [{'attribute': 'language', 'value': 'Chinese', 'importance': 'required'}]})]),
            final(sentence, [claim(sentence, 'Chinese', path='/data/staged_profile/hard_constraints/language', school=None)]))
        with self.assertLogs('kindercompass.llm_first', level='INFO') as logs:
            response = await self.request(model, message='Chinese is required')
        self.assertEqual(response.json()['profile']['hard_constraints']['language'], 'Chinese')
        event = json.loads(logs.output[-1].split('llm_first_observation ')[1])
        self.assertEqual(event['tool_names'], ['update_preferences'])
        self.assertEqual(event['executed_tool_calls'], 1)
        self.assertTrue(event['validation_succeeded'])
        self.assertEqual(event['model_calls'], 2)

    async def test_legacy_rollback_serves_original_contract_without_new_model(self):
        model = Mock()
        response = await self.request(model, 'legacy')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Hi!', response.json()['question'])
        model.bind_tools.assert_not_called()
        model.invoke.assert_not_called()
        self.feedback.record_answer.assert_called_once()

    async def test_shadow_discards_mutation_and_has_no_shared_writes(self):
        sentence = "Chinese is now required."
        model = fixtures.ScriptedModel(AIMessage(content='', tool_calls=[fixtures.call('update_preferences', {
            'set': [{'attribute': 'language', 'value': 'Chinese', 'importance': 'required'}]})]),
            final(sentence, [claim(sentence, 'Chinese', path='/data/staged_profile/hard_constraints/language', school=None)]))
        original = {'hard_constraints': {'language': 'Malay'}}
        # Separate direct shadow proves even explicit consent cannot write.
        request = PreferenceRequest(message='Chinese is required', anonymous_session_id=uuid.uuid4(),
                                    remember_conversation=True, remember_preferences=True)
        with (patch.object(self.history, 'begin_turn', side_effect=AssertionError('shared history')),
              patch.object(self.history, 'commit', side_effect=AssertionError('shadow commit')),
              self.assertLogs('kindercompass.llm_first', level='INFO') as logs):
            result = await self.service.handle_llm_first(request, history=self.history,
                memory=self.memory, feedback=self.feedback, model_factory=lambda: model,
                shadow=True, legacy_result={'profile': original})
        self.assertFalse(result['profile'].get('hard_constraints'))
        self.assertFalse(result['profile'].get('preference_items'))
        self.memory.save.assert_not_called()
        self.feedback.record_answer.assert_not_called()
        event = json.loads(logs.output[-1].split('llm_first_observation ')[1])
        self.assertFalse(event['comparison']['profile_matches'])
        self.assertTrue(event['validation_succeeded'])

    async def test_successful_shadow_serves_legacy_and_compares_without_writes(self):
        model = fixtures.ScriptedModel(final("Hello from the model!"))
        with self.assertLogs('kindercompass.llm_first', level='INFO') as logs:
            response = await self.request(model, 'shadow')
        self.assertIn('Hi!', response.json()['question'])
        self.feedback.record_answer.assert_called_once()
        self.memory.save.assert_not_called()
        self.assertFalse(self.history._sessions)
        event = json.loads(logs.output[-1].split('llm_first_observation ')[1])
        self.assertEqual(event['mode'], 'shadow')
        self.assertTrue(event['validation_succeeded'])
        self.assertIsNotNone(event['comparison'])

    async def test_shadow_serves_one_legacy_answer_even_on_model_failure(self):
        model = fixtures.ScriptedModel(RuntimeError('SECRET TRANSCRIPT'))
        session = str(uuid.uuid4())
        response = await self.request(model, 'shadow', anonymous_session_id=session,
                                      remember_preferences=True, remember_conversation=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Hi!', response.json()['question'])
        self.feedback.record_answer.assert_called_once()
        self.memory.save.assert_called_once()
        self.assertFalse(self.history._sessions)

    async def test_invalid_mode_is_visible_and_explicit_staged_route_remains_available(self):
        response = await self.request(Mock(), 'misspelled')
        self.assertEqual(response.status_code, 503)
        self.feedback.record_answer.assert_not_called()
        self.assertEqual(get_conversation_flow_mode({}), ConversationFlowMode.LLM_FIRST)
        self.assertEqual(get_conversation_flow_mode({'CONVERSATION_FLOW_MODE': 'legacy'}), ConversationFlowMode.LEGACY)

    async def test_default_failure_does_not_use_rollback(self):
        with patch.object(self.service, 'handle', side_effect=AssertionError('fallback')):
            response = await self.request(fixtures.ScriptedModel(RuntimeError('SECRET')))
        self.assertEqual(response.json()['answer_method'], 'service_error')
        self.assertEqual(response.json()['profile'], {})
        self.assertNotIn('SECRET', response.text)
        self.memory.save.assert_not_called()


class TelemetryTests(unittest.TestCase):
    def test_cost_and_logging_exclude_model_content_arguments_and_errors(self):
        with patch.dict(os.environ, {'OPENAI_WEB_RAG_MODEL': 'gpt-4o-mini'}):
            telemetry = TurnTelemetry('llm-first')
        response = AIMessage(content='SECRET FAMILY', usage_metadata={
            'input_tokens': 1000, 'output_tokens': 100, 'total_tokens': 1100,
            'input_token_details': {'cache_read': 200}}, tool_calls=[
                {'name': 'update_preferences', 'args': {'SECRET': '123456'}, 'id': 'SECRET-ID'}])
        model = telemetry.wrap(fixtures.ScriptedModel(response))
        model.bind_tools([]).invoke([])
        with self.assertLogs('kindercompass.llm_first', level='INFO') as logs:
            telemetry.emit(Mock(status='ok', failure_reason=None, tool_calls=1))
        event = json.loads(logs.output[-1].split('llm_first_observation ')[1])
        self.assertAlmostEqual(event['estimated_cost_usd'], 0.000195)
        self.assertNotIn('SECRET', str(logs.output))
        self.assertNotIn('123456', str(logs.output))
        self.assertTrue(event['usage_complete'])

    def test_configured_model_cost(self):
        with patch.dict(os.environ, {'OPENAI_WEB_RAG_MODEL': 'gpt-5.4-mini'}):
            telemetry = TurnTelemetry('llm-first')
        telemetry.model_calls = telemetry.usage_calls = 1
        telemetry.input_tokens, telemetry.cached_tokens, telemetry.output_tokens = 1000, 200, 100
        with self.assertLogs('kindercompass.llm_first', level='INFO') as logs:
            telemetry.emit(Mock(status='ok', failure_reason=None, tool_calls=0))
        event = json.loads(logs.output[-1].split('llm_first_observation ')[1])
        self.assertAlmostEqual(event['estimated_cost_usd'], 0.001065)

    def test_missing_usage_unknown_price_and_logger_failure(self):
        with patch.dict(os.environ, {'OPENAI_WEB_RAG_MODEL': 'unknown'}):
            telemetry = TurnTelemetry('shadow')
        telemetry.wrap(fixtures.ScriptedModel(AIMessage(content='hello'))).invoke([])
        with self.assertLogs('kindercompass.llm_first', level='INFO') as logs:
            telemetry.emit(Mock(status='unavailable', failure_reason='SECRET', tool_calls=0))
        event = json.loads(logs.output[-1].split('llm_first_observation ')[1])
        self.assertIsNone(event['estimated_cost_usd'])
        self.assertFalse(event['usage_complete'])
        self.assertNotIn('SECRET', str(logs.output))
        with patch('SystemCode.src.backend.agents.conversation_telemetry.LOGGER.info', side_effect=RuntimeError):
            telemetry.emit(None)
