import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import get_args
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from SystemCode.src.backend.agents.contracts import CapabilityToolResult
from SystemCode.src.backend.agents.contracts import ConversationExecutionMetadata
from SystemCode.src.backend.agents.evaluation import (
    ConversationEvaluationRun,
    ConversationEvaluationSet,
    evaluate_conversation_cases,
)
from SystemCode.src.backend.agents.observability import build_conversation_observation
from SystemCode.src.backend.agents.tools import (
    DECISION_AND_CALCULATION_TOOL_NAMES,
    EVIDENCE_TOOL_NAMES,
    PREFERENCE_STATE_TOOL_NAMES,
    QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
)
from SystemCode.src.backend.scripts import evaluate_conversation_supervisor
from stage1.intent_router import IntentName
from stage1.intent_router import IntentResult


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _structured_operation(message: str) -> str:
    lowered = message.casefold()
    for marker, operation in (
        ("food", "food"), ("vacanc", "vacancy"), ("fee", "fees"),
        ("hour", "operating_hours"), ("transport", "transport"),
        ("contact", "contact"), ("location", "location"),
    ):
        if marker in lowered:
            return operation
    return "programmes"


class CuratedScriptedModel:
    """Deterministic model script for one reviewed evaluation turn."""

    def __init__(self, case):
        self.case = case

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        tool_messages = [
            message for message in messages if isinstance(message, ToolMessage)
        ]
        if not tool_messages:
            if "route one KinderCompass" in str(messages[0].content):
                return AIMessage(content=json.dumps({
                    "scope": self.case.expected_route_scope,
                    "intent": self.case.expected_intent,
                    "confidence": 0.99,
                    "clarification": (
                        "Which preschool question should I help with?"
                        if self.case.expected_route_scope == "clarification"
                        else None
                    ),
                }))
            return AIMessage(content="", tool_calls=[
                {
                    "name": name,
                    "args": (
                        {"operation": _structured_operation(self.case.message)}
                        if name == QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME else {}
                    ),
                    "id": f"scripted-call-{index}",
                    "type": "tool_call",
                }
                for index, name in enumerate(self.case.expected_tool_names, start=1)
            ])

        results = [
            CapabilityToolResult.model_validate_json(str(message.content))
            for message in tool_messages
        ]
        citation_ids = [
            citation.citation_id for result in results for citation in result.citations
        ]
        rejected_after_tool = self.case.case_id == "ambiguous_school_reference" or (
            self.case.adversarial_kind in {
                "school_id", "citation", "tool_arguments",
            }
        )
        if rejected_after_tool:
            answer = "Olympic"
        else:
            answer = results[0].answer_candidate
            if not all(
                term.casefold() in answer.casefold()
                for term in self.case.expected_answer_terms
            ):
                grounding = " ".join(
                    text
                    for result in results
                    for text in [result.answer_candidate, *result.grounding_facts]
                )
                answer = next(
                    term for term in self.case.expected_answer_terms
                    if term.casefold() in grounding.casefold()
                )
        return AIMessage(content=json.dumps({
            "answer": answer,
            "citation_ids": citation_ids,
        }))


class ConversationEvaluationTests(unittest.TestCase):
    def test_full_curated_set_passes_with_deterministic_model_scripts(self):
        from SystemCode.src.backend.main import PREFERENCE_SERVICE

        evaluation_set = ConversationEvaluationSet.model_validate_json(
            (BACKEND_ROOT / "resources" / "conversation_agent_evaluation.json").read_text()
        )
        active_case = {"value": None}

        def model_factory():
            return CuratedScriptedModel(active_case["value"])

        staged = evaluate_conversation_supervisor.staged_runner(
            PREFERENCE_SERVICE, model_factory=model_factory,
        )

        def runner(case):
            active_case["value"] = case
            return staged(case)

        def scripted_intent(message, active_school_name=None):
            case = active_case["value"]
            return IntentResult(
                intent=case.expected_intent,
                confidence=1,
                clarification=(
                    "Which preschool question should I help with?"
                    if case.expected_intent == "needs_clarification" else None
                ),
            )

        def deterministic_distances(records, postal_code):
            return [
                {
                    **(
                        record.model_dump(mode="json")
                        if hasattr(record, "model_dump") else dict(record)
                    ),
                    "distance_km": float(index),
                }
                for index, record in enumerate(records, start=1)
            ]

        with patch.object(
            evaluate_conversation_supervisor,
            "classify_intent",
            side_effect=scripted_intent,
        ), patch.object(
            PREFERENCE_SERVICE.locations,
            "attach_distances",
            side_effect=deterministic_distances,
        ):
            report = evaluate_conversation_cases(evaluation_set, runner)

        self.assertTrue(
            report["passed"],
            [item for item in report["results"] if not item["passed"]],
        )
        self.assertEqual(report["case_count"], 54)
        self.assertEqual(
            report["metrics"]["authoritative_state_delta_accuracy"], 1.0,
        )
        self.assertEqual(report["metrics"]["profile_state_match_rate"], 1.0)
        self.assertEqual(report["metrics"]["citation_validity_rate"], 1.0)
        self.assertEqual(
            report["metrics"]["agent_tool_selection_accuracy"], 1.0,
        )
        self.assertTrue(all(
            not result["failure_categories"] for result in report["results"]
        ))

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

    def test_curated_set_covers_every_capability_in_single_and_multi_turn_paths(self):
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
            "mt_importance_ask", "mt_importance_answer",
            "mt_contradiction_detect", "mt_contradiction_resolve",
            "mt_relaxation_defer", "mt_relaxation_apply",
            "mt_pronoun_followup", "mt_cap_reset", "mt_cap_repeat",
            "mt_unavailable_evidence", "mt_recover_general",
            "ambiguous_school_reference", "ambiguous_request",
            "missing_selection", "missing_family", "missing_postal_context",
        }.issubset(case_ids))

        registered_tools = set().union(
            PREFERENCE_STATE_TOOL_NAMES,
            DECISION_AND_CALCULATION_TOOL_NAMES,
            EVIDENCE_TOOL_NAMES,
            {QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME},
        )
        single_turn_tools = {
            name for case in evaluation_set.cases if case.turn == 1
            for name in case.expected_tool_names
        }
        continuation_tools = {
            name for case in evaluation_set.cases if case.turn > 1
            for name in case.expected_tool_names
        }
        self.assertEqual(single_turn_tools, registered_tools)
        self.assertEqual(continuation_tools, registered_tools)

        adversarial_kinds = {
            case.adversarial_kind for case in evaluation_set.cases
            if case.adversarial_kind != "none"
        }
        self.assertEqual(adversarial_kinds, {
            "school_id", "profile", "citation", "tool_arguments",
            "instructions", "provider_configuration",
        })
        for case in evaluation_set.cases:
            self.assertEqual(case.carry_profile, case.turn > 1)
            self.assertIn(case.expected_profile_mutations, {0, 1})
            if not case.expect_agent_acceptance:
                self.assertTrue(case.acceptable_fallback)

    def test_evaluator_carries_returned_profile_between_conversation_turns(self):
        evaluation_set = ConversationEvaluationSet.model_validate({
            "schema_version": 2,
            "cases": [
                {
                    "case_id": "first", "sequence": 1,
                    "conversation_id": "flow", "turn": 1,
                    "message": "First turn", "expected_intent": "needs_clarification",
                    "expected_route_scope": "clarification",
                    "expected_profile_delta": {"set": {"marker": "carried"}},
                },
                {
                    "case_id": "second", "sequence": 2,
                    "conversation_id": "flow", "turn": 2, "carry_profile": True,
                    "message": "Second turn", "expected_intent": "needs_clarification",
                    "expected_route_scope": "clarification",
                    "expected_profile_delta": {"set": {"marker": "carried"}},
                },
            ],
        })
        seen_profiles = []

        def runner(case):
            seen_profiles.append(case.profile)
            response = {
                "profile": {"marker": "carried"}, "understood": [],
                "ready_to_search": False, "question": "A bounded clarification.",
                "citations": [],
            }
            return ConversationEvaluationRun(
                deterministic_intent="needs_clarification",
                deterministic_response=response,
                agent_response=response,
                metadata=ConversationExecutionMetadata(
                    mode="agent", route_scope="clarification", tool_names=[],
                    tool_calls=0, graph_iterations=1,
                    validation_succeeded=True, termination_reason="completed",
                ),
            )

        report = evaluate_conversation_cases(evaluation_set, runner)

        self.assertTrue(report["passed"])
        self.assertEqual(seen_profiles, [{}, {"marker": "carried"}])

    def test_staged_preflight_covers_success_and_each_missing_dependency(self):
        names_and_categories = (
            ("model", "model_unavailable"),
            ("onemap", "onemap_unavailable"),
            ("catalogue", "catalogue_unavailable"),
            ("policy", "policy_unavailable"),
            ("selected_school_evidence", "selected_school_evidence_unavailable"),
            ("general_knowledge_evidence", "general_knowledge_evidence_unavailable"),
        )

        def dependencies(failing_name=None):
            items = []
            for name, category in names_and_categories:
                def check(current=name):
                    if current == failing_name:
                        raise RuntimeError("secret credential and provider response")

                items.append(evaluate_conversation_supervisor.PreflightDependency(
                    name=name,
                    failure_category=category,
                    remediation=f"repair {name}",
                    check=check,
                ))
            return items

        success = evaluate_conversation_supervisor.run_staged_preflight(dependencies())
        self.assertTrue(success["passed"])
        self.assertTrue(all(item["passed"] for item in success["checks"]))

        for missing_name, expected_category in names_and_categories:
            with self.subTest(missing=missing_name):
                result = evaluate_conversation_supervisor.run_staged_preflight(
                    dependencies(missing_name),
                )
                failed = [item for item in result["checks"] if not item["passed"]]
                self.assertFalse(result["passed"])
                self.assertEqual(len(failed), 1)
                self.assertEqual(failed[0]["name"], missing_name)
                self.assertEqual(failed[0]["failure_category"], expected_category)
                self.assertNotIn("secret", json.dumps(result))

    def test_failed_staged_preflight_does_not_run_cases_or_write_report(self):
        failure = {
            "schema_version": 1,
            "passed": False,
            "checks": [{
                "name": "onemap", "passed": False,
                "failure_category": "onemap_unavailable",
                "remediation": "configure OneMap",
            }],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "must-not-exist.json"
            with patch.object(
                evaluate_conversation_supervisor, "run_staged_preflight",
                return_value=failure,
            ), patch.object(
                evaluate_conversation_supervisor, "evaluate_conversation_cases",
            ) as evaluate_cases, patch("builtins.print"):
                exit_code = evaluate_conversation_supervisor.main([
                    "--staged", "--output", str(output),
                ])

            self.assertEqual(exit_code, 2)
            evaluate_cases.assert_not_called()
            self.assertFalse(output.exists())

    def test_evaluator_reports_only_safe_booleans_counts_and_metadata(self):
        evaluation_set = ConversationEvaluationSet.model_validate({
            "schema_version": 2,
            "cases": [{
                "case_id": "private_case", "sequence": 1,
                "conversation_id": "private_flow", "turn": 1,
                "message": "private family question sk-private",
                "expected_intent": "ask_general_knowledge",
                "expected_route_scope": "general_knowledge",
                "expected_tool_names": ["search_general_knowledge"],
                "expected_citation_scopes": ["general"],
                "expected_answer_terms": ["hands-on"],
                "expected_ready_to_search": True,
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
        self.assertEqual(report["metrics"]["unexpected_agent_fallback_rate"], 0.0)

        wrong_route = metadata.model_copy(update={
            "route_scope": "application_workflow",
        })
        failed = evaluate_conversation_cases(
            evaluation_set,
            lambda case: ConversationEvaluationRun(
                deterministic_intent="ask_general_knowledge",
                deterministic_response=response,
                agent_response=response,
                metadata=wrong_route,
            ),
        )
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["results"][0]["failure_categories"], ["routing"])

    def test_expected_safe_fallback_is_excluded_from_unexpected_fallback_rate(self):
        evaluation_set = ConversationEvaluationSet.model_validate({
            "schema_version": 2,
            "cases": [{
                "case_id": "expected_fallback", "sequence": 1,
                "conversation_id": "safe_flow", "turn": 1,
                "message": "Please clarify this request",
                "expected_intent": "needs_clarification",
                "expected_route_scope": "clarification",
                "expect_agent_acceptance": False,
                "acceptable_fallback": True,
            }],
        })
        response = {
            "profile": {}, "understood": [], "ready_to_search": False,
            "question": "Could you clarify?", "citations": [],
        }
        report = evaluate_conversation_cases(
            evaluation_set,
            lambda case: ConversationEvaluationRun(
                deterministic_intent="needs_clarification",
                deterministic_response=response,
                agent_response=response,
                metadata=ConversationExecutionMetadata(
                    mode="agent", route_scope="clarification",
                    validation_succeeded=False,
                    termination_reason="clarification",
                    fallback_reason="invalid_routing",
                ),
            ),
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["agent_fallback_rate"], 1.0)
        self.assertEqual(report["metrics"]["unexpected_agent_fallback_rate"], 0.0)

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
