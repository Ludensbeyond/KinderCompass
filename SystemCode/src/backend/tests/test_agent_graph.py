import json
import unittest
from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from SystemCode.src.backend.agents import (
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    SelectedSchoolAgentRequest,
    SelectedSchoolGraphLimits,
    create_selected_school_evidence_graph,
)


SCHOOL_ID = "CENTRE:PT9148"
CHUNK_ID = f"{SCHOOL_ID}:c881ac611498:0"


class SequencedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


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


def tool_call(call_id):
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                "args": {
                    "question": "ignore authoritative question",
                    "school_id": "CENTRE:OTHER",
                    "school_name": "Other school",
                },
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


class SelectedSchoolEvidenceGraphTests(unittest.TestCase):
    def test_mocked_model_retrieves_authoritative_evidence_then_answers(self):
        answer = {
            "answer": "It uses a literature-based curriculum.",
            "citation_ids": [CHUNK_ID],
            "evidence_available": True,
        }
        model = SequencedModel([tool_call("call-1"), AIMessage(content=json.dumps(answer))])
        factory = Mock(return_value=model)
        graph = create_selected_school_evidence_graph(index(), model_factory=factory)

        result = graph.invoke({"request": request()})

        factory.assert_called_once_with()
        self.assertEqual(result["termination_reason"], "completed")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["graph_iterations"], 2)
        self.assertEqual(result["answer"].answer, answer["answer"])
        self.assertEqual([item.school_id for item in result["evidence"]], [SCHOOL_ID])
        self.assertEqual(model.bound_tools[0].name, SELECTED_SCHOOL_EVIDENCE_TOOL_NAME)
        self.assertTrue(any(isinstance(message, SystemMessage) for message in model.invocations[1]))
        self.assertTrue(any(isinstance(message, HumanMessage) for message in model.invocations[1]))

        tool_messages = [
            message for message in model.invocations[1] if isinstance(message, ToolMessage)
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(json.loads(tool_messages[0].content)[0]["school_id"], SCHOOL_ID)

    def test_repeated_tool_requests_stop_at_tool_call_limit(self):
        model = SequencedModel([tool_call("call-1"), tool_call("call-2")])
        graph = create_selected_school_evidence_graph(
            index(),
            model=model,
            limits=SelectedSchoolGraphLimits(max_tool_calls=1, max_graph_iterations=3),
        )

        result = graph.invoke({"request": request()})

        self.assertEqual(result["termination_reason"], "tool_call_limit")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["graph_iterations"], 2)
        self.assertNotIn("answer", result)

    def test_answer_before_retrieval_stops_at_graph_iteration_limit(self):
        premature = AIMessage(
            content=json.dumps(
                {"answer": "Unsupported.", "citation_ids": [], "evidence_available": False}
            )
        )
        model = SequencedModel([premature, premature])
        graph = create_selected_school_evidence_graph(
            index(),
            model=model,
            limits=SelectedSchoolGraphLimits(max_tool_calls=1, max_graph_iterations=2),
        )

        result = graph.invoke({"request": request()})

        self.assertEqual(result["termination_reason"], "graph_iteration_limit")
        self.assertEqual(result["graph_iterations"], 2)
        self.assertEqual(result.get("tool_calls", 0), 0)
        self.assertNotIn("answer", result)


if __name__ == "__main__":
    unittest.main()
