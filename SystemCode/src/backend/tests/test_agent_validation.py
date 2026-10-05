import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from langchain_core.messages import AIMessage

from SystemCode.src.backend.agents import (
    EvidenceCitation,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    SelectedSchoolAgentRequest,
    run_selected_school_evidence_graph,
)


SCHOOL_ID = "CENTRE:PT9148"
CHUNK_ID = f"{SCHOOL_ID}:c881ac611498:0"


class SequencedModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def request():
    return SelectedSchoolAgentRequest(
        question="What curriculum does it use?",
        school_id=SCHOOL_ID,
        school_name="School A",
    )


def index():
    return {
        "pages": [
            {
                "school_id": SCHOOL_ID,
                "chunks": [
                    {
                        "chunk_id": CHUNK_ID,
                        "school_id": SCHOOL_ID,
                        "text": "Our literature-based curriculum supports learning.",
                        "source_url": "https://school.example/curriculum",
                        "title": "School A curriculum",
                        "retrieved_at": "2026-08-23T12:00:00+00:00",
                    }
                ],
            }
        ]
    }


def fallback_citation():
    return EvidenceCitation(
        citation_id=CHUNK_ID,
        school_id=SCHOOL_ID,
        chunk_id=CHUNK_ID,
        url="https://school.example/curriculum",
        title="School A curriculum",
        retrieved_at=datetime(2026, 8, 23, 12, tzinfo=timezone.utc),
    )


def tool_call():
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                "args": {},
                "id": "call-1",
                "type": "tool_call",
            }
        ],
    )


def run(model):
    return run_selected_school_evidence_graph(
        index(),
        request(),
        deterministic_answer="Deterministic curriculum answer.",
        deterministic_citations=[fallback_citation()],
        model=model,
    )


class SelectedSchoolGraphValidationTests(unittest.TestCase):
    def assert_fallback(self, result, reason):
        self.assertEqual(result.answer, "Deterministic curriculum answer.")
        self.assertEqual(result.citations, (fallback_citation(),))
        self.assertEqual(result.answer_method, "deterministic_fallback")
        self.assertEqual(result.fallback_reason, reason)

    def test_malformed_model_output_uses_deterministic_fallback(self):
        result = run(SequencedModel([tool_call(), AIMessage(content="not json")]))

        self.assert_fallback(result, "ValidationError")

    def test_model_timeout_uses_deterministic_fallback(self):
        result = run(SequencedModel([TimeoutError("provider details must stay private")]))

        self.assert_fallback(result, "TimeoutError")

    def test_tool_failure_uses_deterministic_fallback(self):
        with patch(
            "SystemCode.src.backend.agents.tools.retrieve",
            side_effect=RuntimeError("retrieval details must stay private"),
        ):
            result = run(SequencedModel([tool_call()]))

        self.assert_fallback(result, "RuntimeError")

    def test_invalid_citation_uses_deterministic_fallback(self):
        invalid_answer = {
            "answer": "Unsupported curriculum answer.",
            "citation_ids": [f"{SCHOOL_ID}:invented:0"],
            "evidence_available": True,
        }
        result = run(
            SequencedModel([tool_call(), AIMessage(content=json.dumps(invalid_answer))])
        )

        self.assert_fallback(result, "ValueError")

    def test_valid_citation_returns_grounded_agent_answer(self):
        answer = {
            "answer": "It uses a literature-based curriculum.",
            "citation_ids": [CHUNK_ID],
            "evidence_available": True,
        }
        result = run(SequencedModel([tool_call(), AIMessage(content=json.dumps(answer))]))

        self.assertEqual(result.answer, answer["answer"])
        self.assertEqual(result.citations, (fallback_citation(),))
        self.assertEqual(result.answer_method, "agent_grounded")
        self.assertIsNone(result.fallback_reason)


if __name__ == "__main__":
    unittest.main()
