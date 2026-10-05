import os
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from SystemCode.src.backend import main
from SystemCode.src.backend.agents.contracts import EvidenceCitation
from SystemCode.src.backend.domain.models import PreferenceRequest, PreferenceResponse
from stage1.intent_router import IntentResult


SCHOOL_ID = "CENTRE:PT9148"
CHUNK_ID = f"{SCHOOL_ID}:c881ac611498:0"
SCHOOL = {"school_id": SCHOOL_ID, "centre_code": "PT9148", "name": "School A"}
INDEX = {
    "pages": [
        {
            "school_id": SCHOOL_ID,
            "chunks": [
                {
                    "chunk_id": CHUNK_ID,
                    "school_id": SCHOOL_ID,
                    "text": "Our literature-based curriculum supports learning through stories.",
                    "source_url": "https://school.example/curriculum",
                    "title": "School A curriculum",
                    "retrieved_at": "2026-08-23T12:00:00+00:00",
                }
            ],
        }
    ]
}


def citation():
    return EvidenceCitation(
        citation_id=CHUNK_ID,
        school_id=SCHOOL_ID,
        chunk_id=CHUNK_ID,
        url="https://school.example/curriculum",
        title="School A curriculum",
        retrieved_at=datetime(2026, 8, 23, 12, tzinfo=timezone.utc),
    )


class SelectedSchoolAgentEndpointTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "message": "What curriculum does this preschool use?",
            "selected_school_ids": [SCHOOL_ID],
        }

    def _endpoint_patches(self):
        return (
            patch.object(
                main.PREFERENCE_SERVICE,
                "_rebuild",
                side_effect=lambda school_ids, profile, family: [SCHOOL] if school_ids else [],
            ),
            patch.object(main.PREFERENCE_SERVICE, "_resources", return_value=(INDEX, None)),
            patch.object(main.SCHOOL_REPOSITORY, "facet_summary", return_value={}),
            patch.object(main.CHAT_FEEDBACK_SERVICE, "record_answer", return_value=uuid.uuid4()),
            patch(
                "SystemCode.src.backend.services.preference_service.classify_intent",
                return_value=IntentResult(
                    intent="ask_selected_school_evidence", confidence=0.99, method="rules"
                ),
            ),
        )

    def _post(self):
        patches = self._endpoint_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            request = PreferenceRequest.model_validate(self.request)
            result = main.preferences(request)
            return PreferenceResponse.model_validate(result).model_dump(mode="json")

    def test_deterministic_mode_preserves_endpoint_contract_without_graph(self):
        with patch.dict(os.environ, {
            "WEB_RAG_ANSWER_MODE": "deterministic",
            "OPENAI_WEB_RAG_ANSWERS_ENABLED": "false",
        }), patch.object(
            main.PREFERENCE_SERVICE, "_run_selected_school_agent"
        ) as graph:
            body = self._post()

        self.assertIn("literature-based curriculum", body["question"])
        self.assertEqual(body["answer_method"], "deterministic")
        self.assertIsNone(body["fallback_reason"])
        self.assertEqual(body["citations"][0]["chunk_id"], CHUNK_ID)
        graph.assert_not_called()

    def test_agent_mode_returns_validated_grounded_answer(self):
        agent_result = SimpleNamespace(
            answer="School A uses a literature-based curriculum.",
            citations=(citation(),),
            answer_method="agent_grounded",
            fallback_reason=None,
        )
        with patch.dict(os.environ, {
            "WEB_RAG_ANSWER_MODE": "agent",
            "OPENAI_WEB_RAG_ANSWERS_ENABLED": "true",
        }), patch.object(
            main.PREFERENCE_SERVICE,
            "_run_selected_school_agent",
            return_value=agent_result,
        ) as graph, patch(
            "stage1.grounded_explainer._answer_web_evidence_with_openai"
        ) as legacy_model:
            body = self._post()

        self.assertEqual(body["question"], agent_result.answer)
        self.assertEqual(body["answer_method"], "agent_grounded")
        self.assertIsNone(body["fallback_reason"])
        self.assertEqual(
            set(body["citations"][0]),
            {"url", "title", "retrieved_at", "chunk_id", "evidence_scope"},
        )
        self.assertEqual(body["citations"][0]["chunk_id"], CHUNK_ID)
        request = graph.call_args.args[1]
        self.assertEqual(request.school_id, SCHOOL_ID)
        self.assertEqual(request.school_name, SCHOOL["name"])
        legacy_model.assert_not_called()

    def test_agent_failure_returns_the_deterministic_endpoint_answer(self):
        def fallback(_index, _request, deterministic_answer, deterministic_citations):
            return SimpleNamespace(
                answer=deterministic_answer,
                citations=tuple(deterministic_citations),
                answer_method="deterministic_fallback",
                fallback_reason="TimeoutError",
            )

        with patch.dict(os.environ, {
            "WEB_RAG_ANSWER_MODE": "agent",
            "OPENAI_WEB_RAG_ANSWERS_ENABLED": "false",
        }), patch.object(
            main.PREFERENCE_SERVICE,
            "_run_selected_school_agent",
            side_effect=fallback,
        ):
            body = self._post()

        self.assertIn("literature-based curriculum", body["question"])
        self.assertEqual(body["answer_method"], "deterministic_fallback")
        self.assertEqual(body["fallback_reason"], "TimeoutError")
        self.assertEqual(body["citations"][0]["chunk_id"], CHUNK_ID)


if __name__ == "__main__":
    unittest.main()
