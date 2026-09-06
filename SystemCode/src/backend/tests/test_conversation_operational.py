import asyncio
import json
import logging
import os
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from stage1.intent_router import IntentResult

from SystemCode.src.backend import main
from SystemCode.src.backend.agents.contracts import (
    ConversationExecutionMetadata,
    ConversationRequestContext,
    EvidenceIndexContext,
)
from SystemCode.src.backend.agents.model_factory import (
    ModelFactoryError,
    ModelFactoryErrorCode,
)
from SystemCode.src.backend.agents.supervisor import ConversationSupervisorError
from SystemCode.src.backend.agents.validation import run_conversation_supervisor
from SystemCode.src.backend.services.preference_service import PreferenceService
from SystemCode.src.backend.tests.asgi_test_client import ASGITestClient


ANSWER_ID = "00000000-0000-0000-0000-000000000123"


def _context(message: str = "Reset my preferences") -> ConversationRequestContext:
    return ConversationRequestContext(
        message=message,
        profile={"preferences": {"spark_certified": {"value": True}}},
        deterministic_intent="reset_preferences",
        selected_school_evidence=EvidenceIndexContext(
            scope="school", available=False,
        ),
        general_knowledge_evidence=EvidenceIndexContext(
            scope="general", available=False,
        ),
        catalogue_version="test-catalogue",
    )


def _response(question: str, *, method: str | None = None) -> dict:
    return {
        "profile": {"decision_state": {"current_goal": "reset_preferences"}},
        "understood": [],
        "ready_to_search": False,
        "question": question,
        "citations": [],
        "answer_method": method,
        "fallback_reason": None,
        "evidence_category": "unknown",
    }


def _metadata(
    *, succeeded: bool = True, fallback_reason: str | None = None,
    termination_reason: str = "completed",
) -> ConversationExecutionMetadata:
    return ConversationExecutionMetadata(
        mode="agent",
        route_scope="application_workflow",
        tool_names=["reset_preferences"] if succeeded else [],
        tool_calls=1 if succeeded else 0,
        profile_mutations=1 if succeeded else 0,
        graph_iterations=3 if succeeded else 0,
        latency_ms=4,
        validation_succeeded=succeeded,
        termination_reason=termination_reason,
        fallback_reason=fallback_reason,
    )


class _RaisingGraphFactory:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def __call__(self, *args, **kwargs):
        raise self.error


class ConversationOperationalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = PreferenceService(Mock(), Mock(), Mock(), Path("."))
        self.service.build_conversation_context = Mock(
            side_effect=lambda **kwargs: _context(kwargs["message"]),
        )
        self.service._conversation_tools = Mock(return_value=[Mock(name="tool")])

    async def _post_concurrently(self, mode: str, count: int = 4):
        answer_snapshot = Mock(return_value=ANSWER_ID)
        memory_save = Mock()
        observations = Mock()

        with (
            patch.object(main, "PREFERENCE_SERVICE", self.service),
            patch.object(main.CHAT_FEEDBACK_SERVICE, "record_answer", answer_snapshot),
            patch.object(main.CONVERSATION_MEMORY_SERVICE, "save", memory_save),
            patch(
                "SystemCode.src.backend.services.preference_service.emit_conversation_observation",
                observations,
            ),
            patch(
                "SystemCode.src.backend.services.preference_service.classify_intent",
                return_value=IntentResult(
                    intent="reset_preferences", confidence=1, method="rules",
                ),
            ),
            patch.dict(os.environ, {
                "CONVERSATION_AGENT_MODE": mode,
                "WEB_RAG_ANSWER_MODE": "agent",
            }),
        ):
            async with ASGITestClient(main.app, timeout_seconds=2) as client:
                responses = await asyncio.gather(*(
                    client.post("/api/preferences", json={
                        "message": f"Reset preference {number}",
                        "anonymous_session_id": str(uuid.UUID(int=number + 1)),
                        "remember_preferences": True,
                    })
                    for number in range(count)
                ))

        return responses, answer_snapshot, memory_save, observations

    async def test_modes_complete_under_bounded_concurrency_with_exactly_once_writes(self):
        for mode in ("deterministic", "shadow", "agent"):
            with self.subTest(mode=mode):
                self.service._handle_deterministic = Mock(
                    side_effect=lambda **kwargs: _response(
                        f"served:{kwargs['message']}"
                    ),
                )
                self.service._run_conversation_agent = Mock(
                    side_effect=lambda context, tools, fallback: SimpleNamespace(
                        response=_response(
                            f"candidate:{context.message}", method="agent_grounded",
                        ),
                        metadata=_metadata(),
                    ),
                )

                responses, snapshots, memory, observations = (
                    await self._post_concurrently(mode)
                )

                self.assertTrue(all(response.status_code == 200 for response in responses))
                self.assertEqual(snapshots.call_count, 4)
                self.assertEqual(memory.call_count, 4)
                self.assertTrue(all(response.json()["answer_id"] == ANSWER_ID for response in responses))
                if mode == "shadow":
                    self.assertTrue(all(
                        response.json()["question"].startswith("served:")
                        for response in responses
                    ))
                    self.assertEqual(observations.call_count, 4)
                    self.assertTrue(all(
                        call.args[0].mode == "shadow"
                        for call in observations.call_args_list
                    ))
                elif mode == "agent":
                    self.assertTrue(all(
                        response.json()["question"].startswith("candidate:")
                        for response in responses
                    ))
                    self.assertEqual(observations.call_count, 4)
                else:
                    self.service._run_conversation_agent.assert_not_called()
                    observations.assert_not_called()

    async def test_agent_failures_serve_one_fallback_and_emit_distinct_safe_outcomes(self):
        failures = (
            (
                "timeout",
                TimeoutError("provider timeout includes private request text"),
                "timeout",
            ),
            (
                "tool_error",
                ConversationSupervisorError(
                    "tool_error", "tool failure includes https://private.example",
                ),
                "error",
            ),
            (
                "model_unavailable",
                ModelFactoryError(ModelFactoryErrorCode.DEPENDENCY_UNAVAILABLE),
                "error",
            ),
            (
                "validation_error",
                ValueError("invalid private agent state"),
                "validation_failed",
            ),
        )

        for expected_reason, error, expected_termination in failures:
            with self.subTest(reason=expected_reason):
                fallback = _response("Safe deterministic response.")
                self.service._handle_deterministic = Mock(
                    side_effect=lambda **kwargs: deepcopy(fallback),
                )

                def run(context, tools, deterministic_fallback, error=error):
                    return run_conversation_supervisor(
                        context,
                        tools,
                        deterministic_fallback,
                        graph_factory=_RaisingGraphFactory(error),
                    )

                self.service._run_conversation_agent = Mock(side_effect=run)
                observations = Mock()
                snapshots = Mock(return_value=ANSWER_ID)
                memory = Mock()
                with (
                    patch.object(main, "PREFERENCE_SERVICE", self.service),
                    patch.object(main.CHAT_FEEDBACK_SERVICE, "record_answer", snapshots),
                    patch.object(main.CONVERSATION_MEMORY_SERVICE, "save", memory),
                    patch(
                        "SystemCode.src.backend.services.preference_service.emit_conversation_observation",
                        observations,
                    ),
                    patch(
                        "SystemCode.src.backend.services.preference_service.classify_intent",
                        return_value=IntentResult(
                            intent="reset_preferences", confidence=1,
                            method="rules",
                        ),
                    ),
                    patch.dict(os.environ, {
                        "CONVERSATION_AGENT_MODE": "agent",
                        "WEB_RAG_ANSWER_MODE": "agent",
                    }),
                ):
                    async with ASGITestClient(main.app, timeout_seconds=2) as client:
                        response = await client.post("/api/preferences", json={
                            "message": "Reset my preferences",
                        })

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["question"], fallback["question"])
                self.assertEqual(response.json()["fallback_reason"], expected_reason)
                self.service._handle_deterministic.assert_called_once()
                snapshots.assert_called_once()
                memory.assert_not_called()
                observations.assert_called_once()
                observation = observations.call_args.args[0]
                self.assertEqual(observation.fallback_reason, expected_reason)
                self.assertEqual(observation.termination_reason, expected_termination)
                self.assertFalse(observation.validation_succeeded)

    def test_emitted_telemetry_excludes_all_sensitive_runtime_content(self):
        private_values = (
            "private family profile",
            "private conversation message",
            "private system prompt",
            "private evidence passage",
            "sk-private-credential",
            "https://private.example/source",
            "private provider failure",
        )
        metadata = _metadata(
            succeeded=False,
            fallback_reason="tool_error",
            termination_reason="error",
        )
        deterministic = {
            "profile": {"family": private_values[0]},
            "question": private_values[1],
            "prompt": private_values[2],
            "evidence": private_values[3],
            "credential": private_values[4],
            "citations": [{"url": private_values[5]}],
            "provider_error": private_values[6],
            "ready_to_search": False,
        }

        with self.assertLogs(
            "kindercompass.conversation_agent", level=logging.INFO,
        ) as captured:
            self.service._observe_conversation_agent(
                metadata,
                mode="shadow",
                deterministic_response=deterministic,
                agent_response=deepcopy(deterministic),
            )

        serialized = "\n".join(captured.output)
        payload = json.loads(serialized.split("conversation_agent_observation ", 1)[1])
        self.assertEqual(payload["fallback_reason"], "tool_error")
        self.assertEqual(payload["termination_reason"], "error")
        self.assertTrue(payload["profile_state_matches"])
        for private_value in private_values:
            self.assertNotIn(private_value, serialized)


if __name__ == "__main__":
    unittest.main()
