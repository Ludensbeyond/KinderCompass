import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from langchain_core.messages import AIMessage

from SystemCode.src.backend.agents.conversation_loop import LoopLimits
from SystemCode.src.backend.agents.conversation_response import (
    SERVICE_ERROR, ResponseValidationError, run_validated_conversation, validate_response,
)
from SystemCode.src.backend.agents.structured_contracts import StructuredToolResult
from SystemCode.src.backend.tests import test_llm_first_loop as fixtures

ScriptedModel = fixtures.ScriptedModel
call = fixtures.call


def final(answer, claims=None, kind=None):
    return AIMessage(content=json.dumps({"answer": answer, "kind": kind or (
        "grounded" if claims else "conversation"), "claims": claims or []}))


def claim(span, value, path="/data/records/0/facts/base_fee", result="result:1", school="CENTRE:A", citations=None):
    return {"span": span, "value": value, "path": path, "result_id": result,
            "school_id": school, "citation_ids": citations or []}


# Reuse only the synthetic catalogue/transaction setup, not inherited test cases.
class LlmFirstResponseTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixtures.LlmFirstLoopTests.setUp
    service = fixtures.LlmFirstLoopTests.service

    async def run_response(self, service, model, **kwargs):
        return await run_validated_conversation(service.initial_context, service, model=model, **kwargs)

    def facts(self, service):
        return service.invoke("read_school_facts", {"school_ids": ["CENTRE:A", "CENTRE:B"], "operation": "fees"})

    def check_invalid(self, service, result, message, category):
        with self.assertRaisesRegex(ResponseValidationError, category):
            validate_response(message.content, (result,), service.initial_context)

    async def test_zero_tool_greetings_capabilities_and_clarifications_are_model_authored(self):
        for answer, kind in (("Hello! Tell me what matters to your family.", "conversation"),
                             ("I can compare schools and estimate fees.", "conversation"),
                             ("Which school do you mean?", "clarification")):
            service = self.service()
            with patch.object(service, "invoke", side_effect=AssertionError("unnecessary tool")):
                response = await self.run_response(service, ScriptedModel(final(answer, kind=kind)))
            self.assertEqual(response.answer, answer)
            self.assertEqual(response.status, "ok")
            self.assertEqual((response.model_calls, response.tool_calls), (1, 0))
            self.assertIsNotNone(response.profile)
            with self.assertRaises(ValueError):
                service.export_validated_state(response_validated=True)

    def test_pending_acknowledgement_is_supported_but_missing_input_data_is_not(self):
        service = self.service()
        result = service.invoke("update_preferences", {"set": [
            {"attribute": "language", "value": "Chinese"}]})
        answer = "Chinese is pending. Should it be required or preferred?"
        supported = claim("Chinese is pending.", "Chinese",
                          path="/data/staged_profile/pending/value", school=None)
        self.assertEqual(validate_response(final(answer, [supported]).content,
                         (result,), service.initial_context).answer, answer)
        result = result.model_copy(update={"tool_name": "find_nearby_schools"})
        self.check_invalid(service, result, final(answer, [supported]), "unsupported_result_status")

    async def test_missing_pending_question_repairs_without_replaying_mutation(self):
        service = self.service("I want Chinese")
        answer = "Chinese is pending."
        supported = claim(answer, "Chinese", path="/data/staged_profile/pending/value", school=None)
        repaired = answer + " Should it be required or preferred?"
        response = await self.run_response(service, ScriptedModel(
            AIMessage(content="", tool_calls=[call("update_preferences", {
                "set": [{"attribute": "language", "value": "Chinese"}]})]),
            final(answer, [supported]), final(repaired, [supported])))
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.answer, repaired)
        self.assertEqual(response.tool_calls, 1)

    async def test_numeric_value_and_school_attribution_checks_allow_paraphrases(self):
        service = self.service()
        result = self.facts(service)
        answer = "The catalogue lists School A at $900."
        self.assertEqual(validate_response(final(answer, [claim(answer, 900)]).content,
                         (result,), service.initial_context).answer, answer)
        cases = [
            (final("School A costs $800.", [claim("School A costs $800.", 900)]), "wrong_reported_number"),
            (final("School A costs $800.", [claim("School A costs $800.", 800)]), "wrong_claim_value"),
            (final("School B costs $900.", [claim("School B costs $900.", 900, school="CENTRE:B")]), "cross_school_attribution"),
            (final("School B costs $900.", [claim("School B costs $900.", 900)]), "missing_school_attribution"),
            (final("School A costs $900; subsidy is $300.", [claim("School A costs $900", 900)]), "unsupported_reported_number"),
            (final("Fee is $900.", [claim("Fee is $900.", 900)]), "missing_school_attribution"),
            (final("It costs $900."), "unsupported_reported_number"),
            (final("School A costs $900.", [claim("School A costs $900.", 900, result="invented")]), "unknown_claim_support"),
            (final("School A costs $900.", kind="grounded"), "missing_claim_support"),
            (final("School A costs $900.", [claim("School A costs $900.", 900, path="/data/records/99")]), "invalid_support_path"),
            (final("Hello! [invented]"), "unsupported_citation_marker"),
        ]
        for message, category in cases:
            with self.subTest(category=category):
                self.check_invalid(service, result, message, category)

    def test_shared_sentence_requires_support_for_each_reported_number(self):
        service = self.service()
        result = self.facts(service)
        result = result.model_copy(update={"data": {"records": [{"school_id": "CENTRE:A",
            "name": "School A", "facts": {"base_fee": 900, "net_fee": 160}}]}})
        answer = "School A has a base fee of $900 and an estimated net fee of $160."
        claims = [claim(answer, 900), claim(answer, 160, path="/data/records/0/facts/net_fee")]
        self.assertEqual(validate_response(final(answer, claims).content,
                         (result,), service.initial_context).answer, answer)
        self.check_invalid(service, result, final(answer, claims[:1]), "wrong_reported_number")

    def test_current_state_support_cannot_forge_school_facts_or_unblock_a_decision(self):
        service = self.service(profile={"hard_constraints": {"max_distance_km": 1}})
        answer = "I’ll keep the 1 km limit."
        supported = claim(answer, 1, path="/data/profile/hard_constraints/max_distance_km",
                          result="context:current", school=None)
        self.assertEqual(validate_response(final(answer, [supported]).content, (),
                         service.initial_context).answer, answer)
        supported["path"] = "/data/records/0/facts/base_fee"
        with self.assertRaisesRegex(ResponseValidationError, "invalid_support_path"):
            validate_response(final(answer, [supported]).content, (), service.initial_context)
        forged_context = service.initial_context.model_copy(update={"profile": {
            "hard_constraints": {"max_distance_km": 1}, "school_fee": 999}})
        supported.update(path="/data/profile/school_fee", value=999, span="Fee is $999.")
        with self.assertRaisesRegex(ResponseValidationError, "invalid_support_path"):
            validate_response(final("Fee is $999.", [supported]).content, (), forged_context)
        service = self.service(profile={"pending_contradiction": {"existing": "Chinese", "incoming": "Malay"}})
        with self.assertRaisesRegex(ResponseValidationError, "missing_pending_question"):
            validate_response(final("Chinese remains required.").content, (), service.initial_context)

    def evidence(self):
        return StructuredToolResult(
            result_id="result:1", tool_name="search_school_evidence", status="ok",
            data={"passages": [{"school_id": "CENTRE:A", "school_name": "School A",
                  "chunk_id": "source:A", "text": "Children explore the outdoor garden."}]},
            citations=[{"citation_id": "source:A", "evidence_scope": "school", "school_id": "CENTRE:A",
                        "url": "https://example.org/a", "title": "School A", "retrieved_at": "2026-10-10T00:00:00Z"}],
            catalogue_version="synthetic", state_revision=0,
        )

    async def test_passages_require_resolvable_citations_and_matching_school(self):
        service = self.service()
        result = self.evidence()
        answer = "School A describes outdoor garden exploration [source:A]."
        supported = claim(answer, result.data["passages"][0]["text"],
                          path="/data/passages/0/text", citations=["source:A"])
        response = validate_response(final(answer, [supported]).content, (result,), service.initial_context)
        self.assertEqual(response.answer, answer)
        for edits, category in (({"citation_ids": ["invented"]}, "invented_citation"),
                                ({"school_id": "CENTRE:B"}, "cross_school_attribution"),
                                ({"citation_ids": []}, "missing_passage_citation")):
            wrong = {**supported, **edits}
            self.check_invalid(service, result, final(answer, [wrong]), category)
        with patch.object(service, "invoke", return_value=result):
            output = await self.run_response(service, ScriptedModel(
                AIMessage(content="", tool_calls=[call("search_school_evidence", {"school_ids": ["CENTRE:A"], "query": "outdoors"})]),
                final(answer, [supported]),
            ))
        self.assertEqual(output.status, "ok")
        self.assertEqual([c.citation_id for c in output.citations], ["source:A"])
        self.assertEqual(output.claims[0].result_id, "result:1")

    async def test_wrong_numeric_reply_repaired_with_same_evidence_no_tool_replay(self):
        service = self.service()
        bad = "School A costs $999."
        good = "School A has a listed fee of $900."
        def repair(messages):
            self.assertIn("wrong_reported_number", messages[-1].content)
            self.assertIn("existing results only", messages[-1].content)
            return final(good, [claim(good, 900)])
        model = ScriptedModel(
            AIMessage(content="", tool_calls=[call("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees"})]),
            final(bad, [claim(bad, 900)]), repair,
        )
        with patch.object(service, "export_validated_state", wraps=service.export_validated_state) as export:
            response = await self.run_response(service, model)
        self.assertEqual((response.status, response.answer), ("ok", good))
        self.assertEqual((response.model_calls, response.tool_calls), (3, 1))
        export.assert_called_once()

    async def test_model_authored_preference_acknowledgement_uses_latest_staged_state(self):
        service = self.service()
        answer = "Chinese is now required."
        model = ScriptedModel(
            AIMessage(content="", tool_calls=[call("update_preferences", {"set": [
                {"attribute": "language", "value": "Chinese", "importance": "required"}]})]),
            final(answer, [claim(answer, "Chinese", path="/data/staged_profile/hard_constraints/language", school=None)]),
        )
        response = await self.run_response(service, model)
        self.assertEqual(response.answer, answer)
        self.assertEqual(response.profile["hard_constraints"]["language"], "Chinese")
        self.assertEqual(service.initial_context.profile, {})

    async def test_wrong_eligibility_boolean_stale_calculations_and_cross_school_citations_fail(self):
        service = self.service()
        result = StructuredToolResult(result_id="result:1", tool_name="calculate_fees_scenario",
            status="ok", data={"records": [{"school_id": "CENTRE:A", "name": "School A",
            "eligible": True, "fee": 900}]}, catalogue_version="synthetic", state_revision=0)
        wrong = final("School A is ineligible.", [claim("School A is ineligible.", False,
                      path="/data/records/0/eligible")])
        self.check_invalid(service, result, wrong, "wrong_claim_value")
        valid = final("School A costs $900.", [claim("School A costs $900.", 900,
                      path="/data/records/0/fee")])
        later = StructuredToolResult(result_id="result:2", tool_name="update_preferences", status="ok",
                catalogue_version="synthetic", state_revision=1)
        with self.assertRaisesRegex(ResponseValidationError, "stale_state_claim"):
            validate_response(valid.content, (result, later), service.initial_context)
        evidence = self.evidence()
        evidence.citations[0] = evidence.citations[0].model_copy(update={"school_id": "CENTRE:B"})
        answer = "School A describes a garden [source:A]."
        supported = claim(answer, evidence.data["passages"][0]["text"],
                          path="/data/passages/0/text", citations=["source:A"])
        self.check_invalid(service, evidence, final(answer, [supported]), "cross_school_citation")

    async def test_failed_tool_after_mutation_returns_fixed_error_and_no_export(self):
        service = self.service()
        before = deepcopy(service.staged_profile)
        with patch.object(service, "_general_retriever_loader", side_effect=RuntimeError("secret detail")):
            response = await self.run_response(service, ScriptedModel(AIMessage(content="", tool_calls=[
                call("update_preferences", {"set": [{"attribute": "language", "value": "Chinese", "importance": "required"}]}),
                call("search_general_guidance", {"query": "Montessori"}, "call:2"),
            ])))
        self.assertEqual(response.answer, SERVICE_ERROR)
        self.assertIsNone(response.profile)
        self.assertEqual(service.staged_profile, before)

    async def test_failure_and_exhausted_repairs_discard_staged_changes_no_fallback(self):
        for limits, tail in (
            (LoopLimits(), [RuntimeError("private provider detail")]),
            (LoopLimits(), [final("Wrong $999.")] * 3),
            (LoopLimits(repair_calls=0), [final("Wrong $999.")]),
            (LoopLimits(model_calls=2), [final("Wrong $999.")]),
            (LoopLimits(), [final("Wrong $999."), AIMessage(content="", tool_calls=[call("reset_continue_preferences", {"operation": "reset"}, "call:2")])]),
        ):
            service = self.service(profile={"hard_constraints": {"language": "Malay"}})
            before = deepcopy(service.staged_profile)
            model = ScriptedModel(AIMessage(content="", tool_calls=[
                call("reset_continue_preferences", {"operation": "reset"})]), *tail)
            with patch("SystemCode.src.backend.services.preference_service.classify_intent",
                       side_effect=AssertionError("legacy fallback")):
                response = await self.run_response(service, model, limits=limits)
            self.assertEqual((response.status, response.answer), ("unavailable", SERVICE_ERROR))
            self.assertIsNone(response.profile)
            self.assertNotIn("private", response.answer)
            self.assertEqual(service.staged_profile, before)
            self.assertLessEqual(len(model.messages), limits.model_calls)
            with self.assertRaises(ValueError):
                service.export_validated_state(response_validated=True)

    async def test_model_authored_missing_evidence_explanation_supported_by_status(self):
        service = self.service()
        answer = "I cannot check the guidance source right now. Please try later."
        response = await self.run_response(service, ScriptedModel(
            AIMessage(content="", tool_calls=[call("search_general_guidance", {"query": "Montessori"})]),
            final(answer, [claim(answer, "unavailable", path="/status", school=None)], kind="evidence_gap"),
        ))
        self.assertEqual((response.status, response.answer), ("ok", answer))
        self.assertFalse(response.citations)

    async def test_shadow_export_keeps_original_and_repair_context_and_deadline_are_bounded(self):
        service = self.service()
        response = await self.run_response(service, ScriptedModel(
            AIMessage(content="", tool_calls=[call("reset_continue_preferences", {"operation": "reset"})]),
            final("Let's start again.", [claim("Let's start again.", "reset", path="/data/changed_fields/0", school=None)]),
        ), shadow=True)
        self.assertEqual(response.status, "ok")
        self.assertFalse(response.profile.get("hard_constraints"))
        ticks = [0.0]
        def invalid(messages):
            ticks[0] = 29.0
            return final("Unsupported $123.")
        def late(messages):
            ticks[0] = 31.0
            return final("Hello!")
        response = await self.run_response(self.service(), ScriptedModel(invalid, late), clock=lambda: ticks[0])
        self.assertEqual(response.failure_reason, "elapsed_limit")
        model = ScriptedModel(final("Unsupported $123."), final("Hello!"))
        # Size of the initial request is accepted; repair messages exceed the same bound.
        await self.run_response(self.service(), model)
        from SystemCode.src.backend.agents.conversation_loop import _json_bytes
        service = self.service()
        schemas = [{"name": t.name, "description": t.description, "parameters": t.args_schema.model_json_schema()}
                   for t in service.registered_tools()]
        size = _json_bytes({"tools": schemas, "messages": [m.model_dump(mode="json") for m in model.messages[0]]})
        response = await self.run_response(service, ScriptedModel(final("Unsupported $123.")), limits=LoopLimits(context_bytes=size))
        self.assertEqual(response.failure_reason, "context_limit")

    async def test_malformed_output_gets_bounded_repair_and_success_never_substitutes_wording(self):
        for bad in (AIMessage(content="not JSON"), AIMessage(content=json.dumps({"answer": "hi", "extra": "bad"})),
                    final("x" * 801)):
            response = await self.run_response(self.service(), ScriptedModel(bad, final("Hello, how can I help?")))
            self.assertEqual(response.status, "ok")
            self.assertEqual(response.answer, "Hello, how can I help?")
