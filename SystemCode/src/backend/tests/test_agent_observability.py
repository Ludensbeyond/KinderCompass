import json
import unittest

from langchain_core.messages import AIMessage

from SystemCode.src.backend.agents import (
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    SelectedSchoolAgentRequest,
    run_selected_school_evidence_graph,
)
from scripts.evaluate_selected_school_agent import evaluate


SCHOOL_ID = "CENTRE:PT9148"
CHUNK_ID = f"{SCHOOL_ID}:chunk:0"
INDEX = {"pages": [{"school_id": SCHOOL_ID, "school_name": "School A", "chunks": [{
    "chunk_id": CHUNK_ID,
    "school_id": SCHOOL_ID,
    "text": "The school uses a literature-based curriculum.",
    "source_url": "https://school.example/curriculum",
    "title": "Curriculum",
    "retrieved_at": "2026-08-23T12:00:00+00:00",
}]}]}
LABELS = {"cases": [{
    "case_id": "curriculum",
    "school_id": SCHOOL_ID,
    "school_name": "School A",
    "question": "What curriculum does this school use?",
    "evidence_expected": True,
    "expected_terms": ["literature-based"],
    "forbidden_terms": ["montessori"],
}]}


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


def grounded_model():
    return SequencedModel([
        AIMessage(content="", tool_calls=[{
            "name": SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            "args": {},
            "id": "call-1",
            "type": "tool_call",
        }]),
        AIMessage(content=json.dumps({
            "answer": "It uses a literature-based curriculum.",
            "citation_ids": [CHUNK_ID],
            "evidence_available": True,
        })),
    ])


class AgentEvaluationAndObservabilityTests(unittest.TestCase):
    def test_evaluation_compares_both_paths_reproducibly(self):
        def runner(index, request, **kwargs):
            return run_selected_school_evidence_graph(
                index, request, model=grounded_model(), **kwargs
            )

        first = evaluate(INDEX, LABELS, agent_runner=runner)
        second = evaluate(INDEX, LABELS, agent_runner=runner)

        self.assertEqual(first, second)
        self.assertEqual(first["case_count"], 1)
        self.assertEqual(first["deterministic_pass_rate"], 1.0)
        self.assertEqual(first["agent_pass_rate"], 1.0)
        self.assertEqual(first["agent_fallback_rate"], 0.0)
        self.assertEqual(first["comparison"], {"improved": 0, "regressed": 0, "tied": 1})
        self.assertNotIn("answer", first["results"][0])
        self.assertNotIn("question", first["results"][0])

    def test_execution_metadata_is_an_explicit_safe_allowlist(self):
        request = SelectedSchoolAgentRequest(
            question="Private family question with API key sk-private",
            school_id=SCHOOL_ID,
            school_name="School A",
        )
        result = run_selected_school_evidence_graph(
            INDEX,
            request,
            deterministic_answer="Private deterministic answer.",
            deterministic_citations=[],
            model=grounded_model(),
        )

        self.assertEqual(set(result.execution_metadata), {
            "answer_method", "fallback_reason", "tool_calls",
            "graph_iterations", "termination_reason",
        })
        serialized = json.dumps(result.execution_metadata)
        for private_value in ("sk-private", request.question, "literature-based", "School A"):
            self.assertNotIn(private_value, serialized)

    def test_unknown_exception_names_are_not_exposed(self):
        PrivateProviderSecret = type("PrivateProviderSecret", (Exception,), {})
        result = run_selected_school_evidence_graph(
            INDEX,
            SelectedSchoolAgentRequest(
                question="What curriculum does it use?",
                school_id=SCHOOL_ID,
                school_name="School A",
            ),
            deterministic_answer="Fallback.",
            deterministic_citations=[],
            model=SequencedModel([PrivateProviderSecret("secret provider message")]),
        )

        self.assertEqual(result.fallback_reason, "AgentExecutionError")
        self.assertNotIn("PrivateProviderSecret", json.dumps(result.execution_metadata))


if __name__ == "__main__":
    unittest.main()
