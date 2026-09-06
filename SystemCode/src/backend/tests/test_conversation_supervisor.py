import json
import unittest

from langchain_core.messages import AIMessage, ToolMessage

from SystemCode.src.backend.agents import (
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    UPDATE_PREFERENCES_TOOL_NAME,
    create_conversation_supervisor_graph,
    create_evidence_tools,
    create_preference_state_tools,
    create_structured_school_facts_tool,
)
from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    ConversationExecutionLimits,
    ConversationRequestContext,
    ConversationSupervisorResult,
    EvidenceIndexContext,
    GeneratedConversationAnswer,
)


SCHOOL_ID = "CENTRE:A"
SCHOOL_CHUNK = "CENTRE:A:page:0"
GENERAL_CHUNK = "GENERAL:play:0"


class SequencedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []
        self.bound_tools = []
        self.tool_binding_options = {}
        self.tool_bindings = []

    def bind_tools(self, tools, **options):
        self.bound_tools = list(tools)
        self.tool_binding_options = options
        self.tool_bindings.append((list(tools), options))
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


class StructuredRepository:
    def get_structured_facts(self, school_ids, operation):
        return [{
            "school_id": school_ids[0],
            "name": "Alpha Preschool",
            "operation": operation,
            "facts": {"food_offered": "Halal food"},
            "available": True,
            "freshness": "current",
            "last_updated": "2026-08-14",
        }]


def route(scope, intent):
    return AIMessage(content=json.dumps({
        "scope": scope,
        "intent": intent,
        "confidence": 0.95,
        "clarification": None,
    }))


def tool_calls(*calls):
    return AIMessage(content="", tool_calls=[
        {
            "name": name,
            "args": arguments,
            "id": f"call-{index}",
            "type": "tool_call",
        }
        for index, (name, arguments) in enumerate(calls, start=1)
    ])


def context(message="What curriculum does this school use, and what does play-based learning mean?"):
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
            scope="school",
            available=True,
            index={"pages": [{
                "school_id": SCHOOL_ID,
                "chunks": [{
                    "chunk_id": SCHOOL_CHUNK,
                    "school_id": SCHOOL_ID,
                    "text": "Our play-based curriculum supports exploration.",
                    "source_url": "https://school.example/programme",
                    "title": "Official programme page",
                    "retrieved_at": "2026-08-14T00:00:00+00:00",
                }],
            }]},
        ),
        general_knowledge_evidence=EvidenceIndexContext(
            scope="general",
            available=True,
            index={"chunks": [{
                "chunk_id": GENERAL_CHUNK,
                "topic": "play-based learning",
                "text": "Play-based learning uses active, hands-on experiences.",
                "source_url": "https://authority.example/play",
                "title": "Play guidance",
                "authority": "Education Authority",
                "retrieved_at": "2026-08-14",
            }]},
        ),
        catalogue_version="test-catalogue",
    )


class ConversationSupervisorTests(unittest.TestCase):
    def test_typed_answer_tool_output_is_normalized_before_validation(self):
        turn = context("What does play-based learning mean?")
        model = SequencedModel([
            route("general_knowledge", "ask_general_knowledge"),
            tool_calls((GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME, {})),
            tool_calls((GeneratedConversationAnswer.__name__, {
                "answer": "Play-based learning uses active, hands-on experiences.",
                "citation_ids": [GENERAL_CHUNK],
            })),
        ])

        result = create_conversation_supervisor_graph(
            turn, create_evidence_tools(turn), model=model,
        ).invoke({})

        self.assertEqual(result["termination_reason"], "completed")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["answer"].citation_ids, [GENERAL_CHUNK])

    def test_ungrounded_typed_wording_uses_the_authoritative_tool_candidate(self):
        turn = context("What does play-based learning mean?")
        model = SequencedModel([
            route("general_knowledge", "ask_general_knowledge"),
            tool_calls((GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME, {})),
            tool_calls(("generated_conversation_answer", {
                "answer": "It includes an Olympic swimming pool.",
                "citation_ids": ["CENTRE:FORGED"],
            })),
        ])

        result = create_conversation_supervisor_graph(
            turn, create_evidence_tools(turn), model=model,
        ).invoke({})

        self.assertNotIn("Olympic", result["answer"].answer)
        self.assertEqual(result["answer"].citation_ids, [GENERAL_CHUNK])

    def test_structured_school_route_executes_the_allowlisted_fact_operation(self):
        turn = context("What food does this preschool offer?")
        tool = create_structured_school_facts_tool(turn, StructuredRepository())
        model = SequencedModel([
            route("structured_kindercompass", "ask_school_food"),
            tool_calls((tool.name, {"operation": "food"})),
            AIMessage(content="```json\n" + json.dumps({
                "answer": "Alpha Preschool offers Halal food.",
                "citation_ids": [],
            }) + "\n```"),
        ])

        result = create_conversation_supervisor_graph(
            turn, [tool], model=model,
        ).invoke({})

        self.assertEqual(result["termination_reason"], "completed")
        self.assertIn("Halal food", result["tool_results"][0].answer_candidate)
        self.assertEqual(result["result"].evidence_category, "authoritative_fact")
        self.assertIn('"confidence":0.95', model.invocations[0][0].content)
        self.assertEqual(model.tool_bindings[0][1], {"tool_choice": "required"})

    def test_combined_route_calls_two_tools_and_assembles_authoritative_result(self):
        turn = context()
        tools = create_evidence_tools(turn)
        model = SequencedModel([
            route("combined", "ask_combined_evidence"),
            tool_calls(
                (SELECTED_SCHOOL_EVIDENCE_TOOL_NAME, {"question": "forged school query"}),
                (GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME, {"question": "forged general query"}),
            ),
            AIMessage(content=json.dumps({
                "answer": "Alpha describes play-based learning, which uses active experiences.",
                "citation_ids": [SCHOOL_CHUNK, GENERAL_CHUNK],
            })),
        ])

        result = create_conversation_supervisor_graph(turn, tools, model=model).invoke({})

        self.assertEqual(result["termination_reason"], "completed")
        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["profile_mutations"], 0)
        self.assertEqual(result["graph_iterations"], 3)
        self.assertIsInstance(result["result"], ConversationSupervisorResult)
        self.assertEqual(
            {item.evidence_scope for item in result["result"].citations},
            {"school", "general"},
        )
        tool_messages = [
            message for message in model.invocations[-1]
            if isinstance(message, ToolMessage)
        ]
        self.assertEqual(len(tool_messages), 2)
        self.assertIn("hands-on experiences", tool_messages[1].content)

    def test_general_route_rejects_an_inapplicable_registered_tool(self):
        turn = context("What does play-based learning mean?")
        tools = create_evidence_tools(turn) + create_preference_state_tools(turn)
        model = SequencedModel([
            route("general_knowledge", "ask_general_knowledge"),
            tool_calls((UPDATE_PREFERENCES_TOOL_NAME, {})),
        ])

        graph = create_conversation_supervisor_graph(turn, tools, model=model)
        with self.assertRaisesRegex(ValueError, "outside the typed route"):
            graph.invoke({})

    def test_model_cannot_replace_the_authoritative_evidence_question(self):
        turn = context("What does play-based learning mean?")
        model = SequencedModel([
            route("general_knowledge", "ask_general_knowledge"),
            tool_calls((GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME, {
                "question": "an unrelated forged query",
                "school_id": "CENTRE:FORGED",
            })),
            AIMessage(content=json.dumps({
                "answer": "It uses active, hands-on experiences.",
                "citation_ids": [GENERAL_CHUNK],
            })),
        ])

        result = create_conversation_supervisor_graph(
            turn, create_evidence_tools(turn), model=model,
        ).invoke({})

        self.assertEqual(result["termination_reason"], "completed")
        self.assertEqual(result["result"].citations[0].citation_id, GENERAL_CHUNK)

    def test_answer_is_not_accepted_until_a_tool_has_run(self):
        turn = context("What does play-based learning mean?")
        premature = AIMessage(content=json.dumps({
            "answer": "Unsupported answer.", "citation_ids": [],
        }))
        model = SequencedModel([
            route("general_knowledge", "ask_general_knowledge"),
            premature,
            premature,
        ])
        graph = create_conversation_supervisor_graph(
            turn,
            create_evidence_tools(turn),
            model=model,
            limits=ConversationExecutionLimits(max_graph_iterations=3),
        )

        result = graph.invoke({})

        self.assertEqual(result["termination_reason"], "iteration_limit")
        self.assertEqual(result.get("tool_calls", 0), 0)
        self.assertNotIn("answer", result)

    def test_tool_call_and_mutation_limits_stop_before_execution(self):
        turn = context("Reset my preferences")
        preference_tools = create_preference_state_tools(turn)
        too_many_calls = tool_calls(*[
            (UPDATE_PREFERENCES_TOOL_NAME, {}) for _ in range(4)
        ])
        call_limited = create_conversation_supervisor_graph(
            turn,
            preference_tools,
            model=SequencedModel([
                route("application_workflow", "update_preferences"),
                too_many_calls,
            ]),
        ).invoke({})
        self.assertEqual(call_limited["termination_reason"], "tool_call_limit")
        self.assertEqual(call_limited.get("tool_calls", 0), 0)

        mutation_limited = create_conversation_supervisor_graph(
            turn,
            preference_tools,
            model=SequencedModel([
                route("application_workflow", "update_preferences"),
                tool_calls(
                    (UPDATE_PREFERENCES_TOOL_NAME, {}),
                    (UPDATE_PREFERENCES_TOOL_NAME, {}),
                ),
            ]),
        ).invoke({})
        self.assertEqual(mutation_limited["termination_reason"], "mutation_limit")
        self.assertEqual(mutation_limited.get("tool_calls", 0), 0)

    def test_clarification_route_terminates_without_an_agent_answer(self):
        turn = context("Can you help with that?")
        clarification = AIMessage(content=json.dumps({
            "scope": "clarification",
            "intent": "needs_clarification",
            "confidence": 0.4,
            "clarification": "Which preschool question should I help with?",
        }))
        model = SequencedModel([clarification])

        result = create_conversation_supervisor_graph(
            turn, create_evidence_tools(turn), model=model,
        ).invoke({})

        self.assertEqual(result["termination_reason"], "clarification")
        self.assertEqual(result["route"].scope, "clarification")
        self.assertNotIn("answer", result)


if __name__ == "__main__":
    unittest.main()
