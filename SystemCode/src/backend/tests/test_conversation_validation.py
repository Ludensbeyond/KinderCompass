import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from SystemCode.src.backend.agents import (
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    create_conversation_supervisor_graph,
    create_evidence_tools,
    create_structured_school_facts_tool,
    run_conversation_supervisor,
    validate_conversation_supervisor_state,
)
from SystemCode.src.backend.agents.config import (
    ConversationAgentMode,
    WebRagAnswerMode,
    get_conversation_agent_mode,
    get_web_rag_answer_mode,
)
from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    ConversationExecutionLimits,
    ConversationRequestContext,
    EvidenceIndexContext,
    PublicCitation,
)
from SystemCode.src.backend.agents.supervisor import _assemble_result


SCHOOL_ID = "CENTRE:A"
SCHOOL_CHUNK = "CENTRE:A:page:0"
GENERAL_CHUNK = "GENERAL:play:0"


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


class StaticGraph:
    def __init__(self, state):
        self.state = state

    def invoke(self, state):
        return deepcopy(self.state)


class StructuredRepository:
    def get_structured_facts(self, school_ids, operation):
        return [{
            "school_id": school_ids[0], "name": "Alpha Preschool",
            "facts": {"food_offered": "Halal food"}, "available": True,
            "freshness": "current", "last_updated": "2026-08-14",
        }]


class RaisingRetriever:
    def search(self, question, *, limit=3):
        raise RuntimeError("private retrieval details")


def context(message="What does play-based learning mean?"):
    school = AuthoritativeSchoolContext(
        school_id=SCHOOL_ID,
        facts={"school_id": SCHOOL_ID, "name": "Alpha Preschool"},
    )
    return ConversationRequestContext(
        message=message,
        profile={"preferences": {"pedagogy": {"value": "Play-based"}}},
        selected_school_ids=[SCHOOL_ID],
        selected_schools=[school],
        selected_school_evidence=EvidenceIndexContext(
            scope="school", available=True, index={"pages": [{
                "school_id": SCHOOL_ID,
                "chunks": [{
                    "chunk_id": SCHOOL_CHUNK, "school_id": SCHOOL_ID,
                    "text": "Our play-based curriculum supports exploration.",
                    "source_url": "https://school.example/programme",
                    "title": "Official programme page",
                    "retrieved_at": "2026-08-14T00:00:00+00:00",
                }],
            }]},
        ),
        general_knowledge_evidence=EvidenceIndexContext(
            scope="general", available=True, index={"chunks": [{
                "chunk_id": GENERAL_CHUNK, "topic": "play-based learning",
                "text": "Play-based learning uses active, hands-on experiences.",
                "source_url": "https://authority.example/play",
                "title": "Play guidance", "authority": "Education Authority",
                "retrieved_at": "2026-08-14",
            }]},
        ),
        catalogue_version="test-catalogue",
    )


def route(scope, intent):
    return AIMessage(content=json.dumps({
        "scope": scope, "intent": intent, "confidence": 0.95,
        "clarification": None,
    }))


def tool_call(name, arguments=None, call_id="call-1"):
    return AIMessage(content="", tool_calls=[{
        "name": name, "args": arguments or {}, "id": call_id,
        "type": "tool_call",
    }])


def final(answer, citation_ids=None):
    return AIMessage(content=json.dumps({
        "answer": answer, "citation_ids": citation_ids or [],
    }))


def general_model(*extra):
    return SequencedModel([
        route("general_knowledge", "ask_general_knowledge"),
        tool_call(GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME),
        *extra,
    ])


def deterministic_result():
    return {
        "profile": {"preferences": {"pedagogy": {"value": "Play-based"}}},
        "understood": ["Pedagogy: Play-based"],
        "ready_to_search": True,
        "question": "Deterministic answer.",
        "citations": [],
        "evidence_category": "unknown",
    }


class ConversationValidationTests(unittest.TestCase):
    def setUp(self):
        self.context = context()
        self.tools = create_evidence_tools(self.context)

    def valid_state(self):
        graph = create_conversation_supervisor_graph(
            self.context,
            self.tools,
            model=general_model(final(
                "Play-based learning uses active, hands-on experiences.",
                [GENERAL_CHUNK],
            )),
        )
        return graph.invoke({})

    def run_static(self, state):
        fallback_calls = []

        def fallback():
            fallback_calls.append(True)
            return deterministic_result()

        outcome = run_conversation_supervisor(
            self.context, self.tools, fallback,
            graph_factory=lambda *args, **kwargs: StaticGraph(state),
        )
        return outcome, fallback_calls

    def test_valid_result_is_accepted_without_running_fallback(self):
        state = self.valid_state()
        outcome, fallback_calls = self.run_static(state)

        self.assertEqual(fallback_calls, [])
        self.assertTrue(outcome.metadata.validation_succeeded)
        self.assertEqual(outcome.response["answer_method"], "agent_grounded")
        self.assertEqual(outcome.response["citations"][0]["chunk_id"], GENERAL_CHUNK)

    def test_malformed_composition_uses_grounded_candidate_and_unknown_tool_falls_back(self):
        malformed = run_conversation_supervisor(
            self.context,
            self.tools,
            deterministic_result,
            model=general_model(AIMessage(content=[])),
        )
        self.assertTrue(malformed.metadata.validation_succeeded)
        self.assertIsNone(malformed.metadata.fallback_reason)
        self.assertIn("hands-on experiences", malformed.response["question"])

        unknown = deepcopy(self.valid_state())
        call_message = next(
            item for item in unknown["messages"]
            if isinstance(item, AIMessage) and item.tool_calls
        )
        call_message.tool_calls[0]["name"] = "invented_tool"
        outcome, calls = self.run_static(unknown)
        self.assertEqual(calls, [True])
        self.assertEqual(outcome.metadata.fallback_reason, "unknown_tool")

    def test_forged_profile_id_and_forged_answer_fact_are_rejected(self):
        forged_id = deepcopy(self.valid_state())
        tool_result = forged_id["tool_results"][0].model_copy(update={
            "profile": {"active_school": {"school_id": "CENTRE:FORGED"}},
        })
        forged_id["tool_results"] = [tool_result]
        tool_message = next(
            item for item in forged_id["messages"] if isinstance(item, ToolMessage)
        )
        tool_message.content = tool_result.model_dump_json()
        forged_id["result"] = _assemble_result(
            forged_id["route"], forged_id["answer"], [tool_result],
        )
        outcome, _ = self.run_static(forged_id)
        self.assertEqual(outcome.metadata.fallback_reason, "validation_error")

        forged_fact = deepcopy(self.valid_state())
        forged_fact["answer"] = forged_fact["answer"].model_copy(update={
            "answer": "The preschool has an Olympic swimming pool.",
        })
        forged_fact["result"] = forged_fact["result"].model_copy(update={
            "answer": forged_fact["answer"].answer,
        })
        forged_fact["messages"][-1] = final(
            forged_fact["answer"].answer, [GENERAL_CHUNK],
        )
        outcome, _ = self.run_static(forged_fact)
        self.assertEqual(outcome.metadata.fallback_reason, "validation_error")

    def test_cross_school_and_mixed_scope_citations_are_rejected(self):
        school_turn = context("What curriculum does this school use?")
        school_tools = create_evidence_tools(school_turn)
        state = create_conversation_supervisor_graph(
            school_turn, school_tools,
            model=SequencedModel([
                route("structured_kindercompass", "ask_selected_school_evidence"),
                tool_call(SELECTED_SCHOOL_EVIDENCE_TOOL_NAME),
                final("The play-based curriculum supports exploration.", [SCHOOL_CHUNK]),
            ]),
        ).invoke({})
        forged = deepcopy(state)
        tool_result = forged["tool_results"][0]
        citation = tool_result.citations[0].model_copy(update={"school_id": "CENTRE:B"})
        tool_result = tool_result.model_copy(update={"citations": [citation]})
        forged["tool_results"] = [tool_result]
        next(item for item in forged["messages"] if isinstance(item, ToolMessage)).content = tool_result.model_dump_json()
        forged["result"] = _assemble_result(forged["route"], forged["answer"], [tool_result])
        outcome = run_conversation_supervisor(
            school_turn, school_tools, deterministic_result,
            graph_factory=lambda *args, **kwargs: StaticGraph(forged),
        )
        self.assertEqual(outcome.metadata.fallback_reason, "unsupported_citation")

        mixed = deepcopy(self.valid_state())
        tool_result = mixed["tool_results"][0]
        extra = PublicCitation(
            citation_id="CENTRE:A:mixed:0", evidence_scope="school",
            school_id=SCHOOL_ID, url="https://school.example/mixed",
            title="Mixed source", retrieved_at="2026-08-14T00:00:00+00:00",
        )
        tool_result = tool_result.model_copy(update={
            "citations": [*tool_result.citations, extra],
        })
        mixed["tool_results"] = [tool_result]
        mixed["answer"] = mixed["answer"].model_copy(update={
            "citation_ids": [GENERAL_CHUNK, extra.citation_id],
        })
        next(item for item in mixed["messages"] if isinstance(item, ToolMessage)).content = tool_result.model_dump_json()
        mixed["messages"][-1] = final(mixed["answer"].answer, mixed["answer"].citation_ids)
        mixed["result"] = _assemble_result(mixed["route"], mixed["answer"], [tool_result])
        outcome, _ = self.run_static(mixed)
        self.assertEqual(outcome.metadata.fallback_reason, "unsupported_citation")

    def test_conflicting_results_and_multiple_mutations_are_rejected(self):
        conflict = deepcopy(self.valid_state())
        conflict["result"] = conflict["result"].model_copy(update={
            "ready_to_search": not conflict["result"].ready_to_search,
        })
        outcome, _ = self.run_static(conflict)
        self.assertEqual(outcome.metadata.fallback_reason, "conflicting_results")

        outcome, _ = self.run_static({"termination_reason": "mutation_limit"})
        self.assertEqual(outcome.metadata.fallback_reason, "multiple_mutations")

    def test_invalid_structured_school_id_is_an_invalid_argument_failure(self):
        turn = context("What food does this school offer?")
        tool = create_structured_school_facts_tool(turn, StructuredRepository())
        outcome = run_conversation_supervisor(
            turn, [tool], deterministic_result,
            model=SequencedModel([
                route("structured_kindercompass", "ask_school_food"),
                tool_call(QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME, {
                    "operation": "food", "school_ids": ["CENTRE:FORGED"],
                }),
            ]),
        )
        self.assertEqual(outcome.metadata.fallback_reason, "invalid_arguments")

    def test_tool_and_model_exceptions_use_fixed_non_sensitive_reasons(self):
        tool_failure = run_conversation_supervisor(
            self.context,
            create_evidence_tools(self.context, general_retriever=RaisingRetriever()),
            deterministic_result,
            model=SequencedModel([
                route("general_knowledge", "ask_general_knowledge"),
                tool_call(GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME),
            ]),
        )
        self.assertEqual(tool_failure.metadata.fallback_reason, "tool_error")

        model_failure = run_conversation_supervisor(
            self.context, self.tools, deterministic_result,
            model=SequencedModel([RuntimeError("private provider details")]),
        )
        self.assertEqual(model_failure.metadata.fallback_reason, "model_error")
        self.assertNotIn("private", json.dumps(model_failure.metadata.model_dump()))

    def test_timeout_and_both_execution_limits_fall_back(self):
        timeout = run_conversation_supervisor(
            self.context, self.tools, deterministic_result,
            model=SequencedModel([TimeoutError("private provider timeout")]),
        )
        self.assertEqual(timeout.metadata.fallback_reason, "timeout")

        for termination in ("tool_call_limit", "iteration_limit"):
            with self.subTest(termination=termination):
                outcome, _ = self.run_static({"termination_reason": termination})
                self.assertEqual(outcome.metadata.fallback_reason, "execution_limit")

    def test_fallback_runs_once_with_both_agent_entry_points_disabled(self):
        calls = []

        def fallback():
            calls.append((get_conversation_agent_mode(), get_web_rag_answer_mode()))
            return deterministic_result()

        with patch.dict(os.environ, {
            "CONVERSATION_AGENT_MODE": "agent",
            "WEB_RAG_ANSWER_MODE": "agent",
        }, clear=False):
            outcome = run_conversation_supervisor(
                self.context, self.tools, fallback,
                model=SequencedModel([RuntimeError("private")]),
            )
            self.assertEqual(calls, [
                (ConversationAgentMode.DETERMINISTIC, WebRagAnswerMode.DETERMINISTIC),
            ])
            self.assertEqual(get_conversation_agent_mode(), ConversationAgentMode.AGENT)
            self.assertEqual(get_web_rag_answer_mode(), WebRagAnswerMode.AGENT)
        self.assertFalse(outcome.metadata.validation_succeeded)


if __name__ == "__main__":
    unittest.main()
