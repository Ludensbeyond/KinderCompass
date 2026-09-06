import unittest
from copy import deepcopy

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from SystemCode.src.backend.agents import (
    CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
    PREFERENCE_STATE_TOOL_NAMES,
    RESET_PREFERENCES_TOOL_NAME,
    UPDATE_PREFERENCES_TOOL_NAME,
    PreferenceStateToolRequest,
    create_preference_state_tools,
)
from SystemCode.src.backend.agents.contracts import (
    CapabilityToolResult,
    ConversationRequestContext,
    EvidenceIndexContext,
)
from stage1.conversation import update_conversation
from stage1.dialogue_manager import propose_constraint_relaxation
from stage1.nlp_mapper import merge_preference_profile


def context(message, profile=None):
    return ConversationRequestContext(
        message=message,
        profile=profile or {},
        selected_school_evidence=EvidenceIndexContext(
            scope="school", available=False,
        ),
        general_knowledge_evidence=EvidenceIndexContext(
            scope="general", available=False,
        ),
        catalogue_version="test-catalogue",
    )


def by_name(tools):
    return {tool.name: tool for tool in tools}


class PreferenceStateToolTests(unittest.TestCase):
    def test_registers_three_strict_typed_mutating_tools(self):
        tools = create_preference_state_tools(
            context("Montessori is preferred"), candidate_facets={},
        )

        self.assertEqual({tool.name for tool in tools}, PREFERENCE_STATE_TOOL_NAMES)
        self.assertTrue(all(isinstance(tool, BaseTool) for tool in tools))
        self.assertTrue(all(tool.args_schema is PreferenceStateToolRequest for tool in tools))
        for tool in tools:
            if tool.name == CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME:
                continue
            result = tool.invoke({})
            self.assertIsInstance(result, CapabilityToolResult)
            self.assertTrue(result.mutates_profile)

        with self.assertRaises(ValidationError):
            by_name(tools)[UPDATE_PREFERENCES_TOOL_NAME].invoke(
                {"profile": {"hard_constraints": {}}}
            )

    def test_update_returns_complete_profile_without_mutating_context(self):
        original = merge_preference_profile(None, "SPARK is preferred")
        turn = context("Montessori is preferred", original)
        snapshot = deepcopy(turn.profile)

        result = by_name(create_preference_state_tools(turn, candidate_facets={}))[
            UPDATE_PREFERENCES_TOOL_NAME
        ].invoke({})

        self.assertEqual(turn.profile, snapshot)
        self.assertEqual(result.profile["preferences"]["pedagogy"]["value"], "Montessori")
        self.assertIn("spark_certified", result.profile["preferences"])
        self.assertEqual(result.understood, result.grounding_facts)
        self.assertEqual(result.citations, [])

    def test_reset_reuses_deterministic_reset_behavior_on_a_copy(self):
        original = merge_preference_profile(None, "Montessori with SPARK")
        snapshot = deepcopy(original)

        result = by_name(create_preference_state_tools(
            context("clear preferences", original), candidate_facets={},
        ))[RESET_PREFERENCES_TOOL_NAME].invoke({})

        self.assertEqual(original, snapshot)
        self.assertEqual(result.profile["hard_constraints"], {})
        self.assertEqual(result.profile["preferences"], {})
        self.assertFalse(result.ready_to_search)
        self.assertIn("Tell me a preference", result.answer_candidate)

    def test_continues_queued_importance_clarifications(self):
        first = update_conversation(None, "Montessori with Chinese")
        original = deepcopy(first["profile"])

        result = by_name(create_preference_state_tools(
            context("It is preferred", first["profile"]), candidate_facets={},
        ))[CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME].invoke({})

        self.assertEqual(first["profile"], original)
        self.assertFalse(result.ready_to_search)
        self.assertIn("pending", result.profile)
        self.assertNotEqual(
            result.profile["pending"]["value"], original["pending"]["value"],
        )

    def test_continues_contradiction_and_relaxation_flows(self):
        chinese = merge_preference_profile(None, "I need Chinese")
        contradiction = update_conversation(chinese, "I need Malay")["profile"]
        repaired = by_name(create_preference_state_tools(
            context("use Malay", contradiction), candidate_facets={},
        ))[CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME].invoke({})
        self.assertEqual(repaired.profile["hard_constraints"]["language"], "Malay")
        self.assertNotIn("pending_contradiction", repaired.profile)

        constrained = merge_preference_profile(None, "within 2 km")
        constrained["pending_relaxation"] = propose_constraint_relaxation(constrained)
        relaxed = by_name(create_preference_state_tools(
            context("apply relaxation", constrained), candidate_facets={},
        ))[CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME].invoke({})
        self.assertEqual(relaxed.profile["hard_constraints"]["max_distance_km"], 3)
        self.assertNotIn("pending_relaxation", relaxed.profile)

    def test_pending_flow_takes_precedence_over_reset_and_requires_pending_state(self):
        constrained = merge_preference_profile(None, "within 2 km")
        constrained["pending_relaxation"] = propose_constraint_relaxation(constrained)
        result = by_name(create_preference_state_tools(
            context("clear preferences", constrained), candidate_facets={},
        ))[RESET_PREFERENCES_TOOL_NAME].invoke({})
        self.assertIn("pending_relaxation", result.profile)
        self.assertFalse(result.ready_to_search)

        tool = by_name(create_preference_state_tools(
            context("It is preferred"), candidate_facets={},
        ))[CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME]
        with self.assertRaisesRegex(ValueError, "no pending preference flow"):
            tool.invoke({})


if __name__ == "__main__":
    unittest.main()
