import os
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from stage1.intent_router import IntentResult

from SystemCode.src.backend import main
from SystemCode.src.backend.agents.config import (
    WebRagAnswerMode,
    get_web_rag_answer_mode,
)
from SystemCode.src.backend.agents.contracts import (
    ConversationExecutionMetadata,
    ConversationRequestContext,
    EvidenceIndexContext,
)
from SystemCode.src.backend.domain.models import PreferenceRequest, PreferenceResponse
from SystemCode.src.backend.services.preference_service import PreferenceService


def turn_context() -> ConversationRequestContext:
    return ConversationRequestContext(
        message="Reset my preferences",
        profile={"preferences": {"spark_certified": {"value": True}}},
        selected_school_evidence=EvidenceIndexContext(
            scope="school", available=False,
        ),
        general_knowledge_evidence=EvidenceIndexContext(
            scope="general", available=False,
        ),
        catalogue_version="test-catalogue",
    )


def deterministic_response() -> dict:
    return {
        "profile": {"decision_state": {"current_goal": "reset_preferences"}},
        "understood": [],
        "ready_to_search": False,
        "question": "Tell me a preference to start again.",
        "citations": [],
        "answer_method": None,
        "fallback_reason": None,
        "evidence_category": "unknown",
    }


def agent_response() -> dict:
    return {
        "profile": {},
        "understood": [],
        "ready_to_search": False,
        "question": "Tell me a preference to start again.",
        "citations": [],
        "answer_method": "agent_grounded",
        "fallback_reason": None,
        "evidence_category": "unknown",
    }


class ConversationModeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.service = PreferenceService(Mock(), Mock(), Mock(), Path("."))
        self.context = turn_context()
        self.service.build_conversation_context = Mock(return_value=self.context)
        self.service._conversation_tools = Mock(return_value=[Mock(name="tool")])

    def handle(self, mode: str) -> dict:
        with (
            patch.dict(os.environ, {
                "CONVERSATION_AGENT_MODE": mode,
                "WEB_RAG_ANSWER_MODE": "agent",
            }),
            patch(
                "SystemCode.src.backend.services.preference_service.classify_intent",
                return_value=IntentResult(intent="reset_preferences", confidence=1),
            ),
        ):
            return self.service.handle(
                message=self.context.message,
                profile=deepcopy(self.context.profile),
                selected_school_ids=[], eligible_school_ids=[], excluded_school_ids=[],
                family=None, home_postal_code=None,
            )

    def test_deterministic_mode_never_constructs_or_runs_the_supervisor(self):
        expected = deterministic_response()
        self.service._handle_deterministic = Mock(return_value=expected)
        self.service._run_conversation_agent = Mock()

        result = self.handle("deterministic")

        self.assertEqual(result, expected)
        self.service._conversation_tools.assert_not_called()
        self.service._run_conversation_agent.assert_not_called()

    def test_shadow_serves_exact_deterministic_result_without_duplicate_graph_entry(self):
        expected = deterministic_response()
        deterministic_calls = []
        shadow_fallbacks = []

        def deterministic(**kwargs):
            deterministic_calls.append(True)
            self.assertIs(get_web_rag_answer_mode(), WebRagAnswerMode.DETERMINISTIC)
            return deepcopy(expected)

        def run_shadow(context, tools, fallback):
            shadow_fallbacks.append(fallback())
            return SimpleNamespace(
                response=agent_response(),
                metadata=SimpleNamespace(validation_succeeded=True),
            )

        self.service._handle_deterministic = Mock(side_effect=deterministic)
        self.service._run_conversation_agent = Mock(side_effect=run_shadow)

        result = self.handle("shadow")

        self.assertEqual(result, expected)
        self.assertEqual(deterministic_calls, [True])
        self.assertEqual(shadow_fallbacks, [expected])
        self.service._run_conversation_agent.assert_called_once()

    def test_agent_mode_serves_validated_result_without_legacy_execution(self):
        self.service._handle_deterministic = Mock(return_value=deterministic_response())
        self.service._run_conversation_agent = Mock(return_value=SimpleNamespace(
            response=agent_response(),
            metadata=SimpleNamespace(validation_succeeded=True),
        ))

        result = self.handle("agent")

        self.service._handle_deterministic.assert_not_called()
        self.assertEqual(result["answer_method"], "agent_grounded")
        self.assertEqual(
            result["profile"]["decision_state"]["current_goal"],
            "reset_preferences",
        )

    def test_agent_setup_failure_falls_back_once_with_fixed_safe_metadata(self):
        expected = deterministic_response()
        fallback_modes = []

        def deterministic(**kwargs):
            fallback_modes.append(get_web_rag_answer_mode())
            return deepcopy(expected)

        self.service._handle_deterministic = Mock(side_effect=deterministic)
        self.service._conversation_tools = Mock(side_effect=RuntimeError("private"))

        result = self.handle("agent")

        self.assertEqual(fallback_modes, [WebRagAnswerMode.DETERMINISTIC])
        self.assertEqual(result["question"], expected["question"])
        self.assertEqual(result["answer_method"], "deterministic_fallback")
        self.assertEqual(result["fallback_reason"], "validation_error")

    def test_shadow_emits_only_the_safe_comparison_observation(self):
        expected = deterministic_response()
        metadata = ConversationExecutionMetadata(
            mode="agent", route_scope="application_workflow",
            tool_names=["reset_preferences"], tool_calls=1,
            profile_mutations=1, graph_iterations=3,
            validation_succeeded=True, termination_reason="completed",
        )
        self.service._handle_deterministic = Mock(return_value=deepcopy(expected))
        self.service._run_conversation_agent = Mock(return_value=SimpleNamespace(
            response=deepcopy(expected), metadata=metadata,
        ))

        with patch(
            "SystemCode.src.backend.services.preference_service.emit_conversation_observation",
        ) as emit:
            result = self.handle("shadow")

        self.assertEqual(result, expected)
        observation = emit.call_args.args[0]
        self.assertEqual(observation.mode, "shadow")
        self.assertTrue(observation.profile_state_matches)
        self.assertTrue(observation.citations_match)
        self.assertTrue(observation.readiness_matches)


class PreferenceEndpointModeTests(unittest.TestCase):
    def test_every_mode_has_the_same_public_shape_and_writes_after_selection(self):
        service = PreferenceService(Mock(), Mock(), Mock(), Path("."))
        context = turn_context()
        service.build_conversation_context = Mock(return_value=context)
        service._conversation_tools = Mock(return_value=[Mock(name="tool")])
        service._handle_deterministic = Mock(
            side_effect=lambda **kwargs: deterministic_response(),
        )
        service._run_conversation_agent = Mock(return_value=SimpleNamespace(
            response=agent_response(),
            metadata=SimpleNamespace(validation_succeeded=True),
        ))
        answer_id = uuid.UUID("00000000-0000-0000-0000-000000000123")
        session_id = uuid.UUID("00000000-0000-0000-0000-000000000456")
        public_results = []

        with (
            patch.object(main, "PREFERENCE_SERVICE", service),
            patch.object(
                main.CHAT_FEEDBACK_SERVICE, "record_answer", return_value=answer_id,
            ) as record_answer,
            patch.object(main.CONVERSATION_MEMORY_SERVICE, "save") as save,
            patch(
                "SystemCode.src.backend.services.preference_service.classify_intent",
                return_value=IntentResult(intent="reset_preferences", confidence=1),
            ),
        ):
            for mode in ("deterministic", "shadow", "agent"):
                with patch.dict(os.environ, {
                    "CONVERSATION_AGENT_MODE": mode,
                    "WEB_RAG_ANSWER_MODE": "agent",
                }):
                    raw = main.preferences(PreferenceRequest(
                        message=context.message,
                        profile=deepcopy(context.profile),
                        anonymous_session_id=session_id,
                        remember_preferences=True,
                    ))
                    public_results.append(
                        PreferenceResponse.model_validate(raw).model_dump(mode="json")
                    )

        expected_keys = set(public_results[0])
        self.assertTrue(all(set(item) == expected_keys for item in public_results))
        self.assertTrue(all(item["answer_id"] == str(answer_id) for item in public_results))
        self.assertEqual(record_answer.call_count, 3)
        self.assertEqual(save.call_count, 3)
        for call in save.call_args_list:
            self.assertIn("decision_state", call.args[1])


if __name__ == "__main__":
    unittest.main()
