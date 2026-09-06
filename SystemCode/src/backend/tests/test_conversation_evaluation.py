import json
import os
import unittest
from pathlib import Path
from typing import get_args
from unittest.mock import patch

from SystemCode.src.backend.agents.contracts import ConversationExecutionMetadata
from SystemCode.src.backend.agents.evaluation import (
    ConversationEvaluationRun,
    ConversationEvaluationSet,
    evaluate_conversation_cases,
)
from SystemCode.src.backend.agents.observability import build_conversation_observation
from SystemCode.src.backend.scripts import evaluate_conversation_supervisor
from stage1.intent_router import IntentName


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class ConversationEvaluationTests(unittest.TestCase):
    def test_staged_model_factory_opts_in_without_mutating_rollout_mode(self):
        sentinel = object()
        with patch.dict(os.environ, {"CONVERSATION_AGENT_MODE": "deterministic"}), patch.object(
            evaluate_conversation_supervisor,
            "create_conversation_agent_model",
            return_value=sentinel,
        ) as create_model:
            result = evaluate_conversation_supervisor.staged_model_factory()

            self.assertEqual(os.environ["CONVERSATION_AGENT_MODE"], "deterministic")

        self.assertIs(result, sentinel)
        self.assertEqual(
            create_model.call_args.args[0]["CONVERSATION_AGENT_MODE"], "agent",
        )

    def test_curated_set_is_ordered_and_covers_intents_transitions_and_sources(self):
        raw = json.loads(
            (BACKEND_ROOT / "resources" / "conversation_agent_evaluation.json").read_text()
        )
        evaluation_set = ConversationEvaluationSet.model_validate(raw)

        covered_intents = {case.expected_intent for case in evaluation_set.cases}
        self.assertEqual(covered_intents, set(get_args(IntentName)))
        self.assertEqual(
            [case.sequence for case in evaluation_set.cases],
            list(range(1, len(evaluation_set.cases) + 1)),
        )
        case_ids = {case.case_id for case in evaluation_set.cases}
        self.assertTrue({
            "pending_language_required", "pending_contradiction", "pending_relaxation",
            "structured_food", "structured_vacancy", "missing_structured_field",
            "general_subsidy_guidance", "combined_school_and_guidance",
            "missing_selection", "missing_family", "missing_postal_context",
            "ambiguous_request", "reset_preferences",
        }.issubset(case_ids))

    def test_evaluator_reports_only_safe_booleans_counts_and_metadata(self):
        evaluation_set = ConversationEvaluationSet.model_validate({
            "schema_version": 1,
            "cases": [{
                "case_id": "private_case", "sequence": 1,
                "message": "private family question sk-private",
                "expected_intent": "ask_general_knowledge",
                "expected_route_scope": "general_knowledge",
                "expected_tool_names": ["search_general_knowledge"],
                "expected_citation_scopes": ["general"],
                "expected_answer_terms": ["hands-on"],
            }],
        })
        response = {
            "profile": {"private": "family secret"},
            "understood": [], "ready_to_search": True,
            "question": "Play uses hands-on experiences.",
            "citations": [{
                "url": "https://authority.example/play", "title": "Private title",
                "retrieved_at": "2026-08-14", "chunk_id": "GENERAL:play:0",
                "evidence_scope": "general",
            }],
        }
        metadata = ConversationExecutionMetadata(
            mode="agent", route_scope="general_knowledge",
            tool_names=["search_general_knowledge"], tool_calls=1,
            graph_iterations=3, validation_succeeded=True,
            termination_reason="completed",
        )

        report = evaluate_conversation_cases(
            evaluation_set,
            lambda case: ConversationEvaluationRun(
                deterministic_intent="ask_general_knowledge",
                deterministic_response=response,
                agent_response=response,
                metadata=metadata,
            ),
        )

        self.assertTrue(report["passed"])
        serialized = json.dumps(report)
        for private_value in (
            "sk-private", "family secret", "hands-on", "Private title",
            "authority.example",
        ):
            self.assertNotIn(private_value, serialized)
        self.assertEqual(report["metrics"]["agent_tool_selection_accuracy"], 1.0)

    def test_observation_is_an_explicit_privacy_safe_allowlist(self):
        metadata = ConversationExecutionMetadata(
            mode="agent", route_scope="application_workflow",
            tool_names=["reset_preferences"], tool_calls=1,
            profile_mutations=1, graph_iterations=3, latency_ms=12,
            validation_succeeded=True, termination_reason="completed",
        )
        private = {
            "profile": {"income": 1234, "secret": "sk-private"},
            "citations": [], "ready_to_search": False,
            "question": "private conversation text",
        }
        observation = build_conversation_observation(
            metadata, mode="shadow",
            deterministic_response=private, agent_response=private,
        )

        self.assertEqual(set(observation.model_dump()), {
            "schema_version", "mode", "route_scope", "tool_names", "tool_calls",
            "profile_mutations", "graph_iterations", "latency_ms",
            "termination_reason", "validation_succeeded", "fallback_reason",
            "profile_state_matches", "citations_match", "readiness_matches",
        })
        serialized = observation.model_dump_json()
        for private_value in ("1234", "sk-private", "private conversation text"):
            self.assertNotIn(private_value, serialized)


if __name__ == "__main__":
    unittest.main()
