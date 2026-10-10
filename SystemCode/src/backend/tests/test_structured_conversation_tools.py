import datetime as dt
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import ValidationError

from SystemCode.src.backend.agents.contracts import InitialConversationContext
from SystemCode.src.backend.agents.structured_contracts import StructuredToolResult
from SystemCode.src.backend.repositories.school_repository import SchoolRepository, SchoolNotFoundError
from SystemCode.src.backend.services.conversation_context_service import CAPABILITIES
from SystemCode.src.backend.services.conversation_tool_service import ConversationToolService
from SystemCode.src.backend.services.evaluation_service import EvaluationService


class StructuredConversationToolsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        catalogue = Path(directory.name) / "schools.json"
        catalogue.write_text(json.dumps([
            {"school_id": "CENTRE:A", "name": "School A", "base_fee": 900,
             "care_levels": ["Nursery (4 yrs old)"], "second_languages_offered": "Chinese",
             "pedagogy": "Montessori", "provision_of_transport": "Yes"},
            {"school_id": "CENTRE:B", "name": "School B", "base_fee": 800,
             "care_levels": ["Nursery (4 yrs old)"], "second_languages_offered": "Malay"},
        ]))
        self.schools = SchoolRepository(catalogue)
        self.context = InitialConversationContext(
            message="I want Chinese and compare fees", catalogue_version=self.schools.catalogue_version,
            capabilities=list(CAPABILITIES), family={
                "dob": dt.date(2022, 1, 1), "admission_date": dt.date(2026, 1, 1),
                "gross_household_income": 4500,
            },
        )
        self.locations = Mock()
        self.locations.attach_distances.side_effect = lambda records, postal: [
            {**r, "distance_km": 0.5 if r["school_id"] == "CENTRE:A" else None} for r in records
        ]

    def service(self, **kwargs):
        return ConversationToolService(self.context, self.schools, EvaluationService(self.schools),
                                       self.locations, **kwargs)

    def update(self, service, attribute="language", value="Chinese", importance="required"):
        return service.invoke("update_preferences", {"set": [
            {"attribute": attribute, "value": value, "importance": importance},
        ]})

    def test_update_then_search_reads_staged_state_and_detached_results(self):
        service = self.service()
        before = self.context.model_dump()
        updated = self.update(service)
        self.assertEqual(updated.status, "ok")
        updated.data["staged_profile"]["hard_constraints"].clear()
        result = service.invoke("search_rank_compare_schools", {})
        self.assertEqual([r["school_id"] for r in result.data["records"]], ["CENTRE:A"])
        self.assertEqual(result.state_revision, 1)
        self.assertEqual(result.data["profile_used"]["hard_constraints"]["language"], "Chinese")
        self.assertEqual(self.context.model_dump(), before)
        exported = service.export_validated_state(response_validated=True)
        self.assertEqual(exported["hard_constraints"]["language"], "Chinese")
        with self.assertRaisesRegex(ValueError, "closed"):
            service.invoke("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees"})

    def test_scenario_uses_deterministic_evaluator_without_mutating_family(self):
        service = self.service()
        self.update(service, "pedagogy", "Montessori", "preferred")
        before = deepcopy(self.context.family.model_dump())
        result = service.invoke("calculate_fees_scenario", {
            "school_ids": ["CENTRE:A"], "overrides": {"gross_household_income": 1000.0},
        })
        expected = EvaluationService(self.schools).evaluate(
            ["CENTRE:A"], service.staged_profile,
            self.context.family.model_copy(update={"gross_household_income": 1000.0}),
            include_ineligible=True,
        )
        self.assertEqual(result.data["records"], [r.model_dump(mode="json") for r in expected])
        self.assertEqual(result.data["profile_used"], service.staged_profile)
        self.assertTrue(result.data["hypothetical"])
        self.assertEqual(self.context.family.model_dump(), before)
        normal = service.invoke("calculate_fees_scenario", {"school_ids": ["CENTRE:A"]})
        self.assertEqual(normal.data["inputs_used"]["gross_household_income"], 4500)

    def test_contract_rejections_discard_prior_changes(self):
        invalid = [
            ("read_school_facts", {"school_ids": ["CENTRE:UNKNOWN"], "operation": "fees"}, SchoolNotFoundError),
            ("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "secret"}, ValidationError),
            ("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees", "base_fee": 1}, ValidationError),
            ("update_preferences", {"profile": {"hard_constraints": {}}}, ValidationError),
            ("update_preferences", {"set": [{"attribute": "language", "value": "French", "importance": "required"}]}, ValidationError),
            ("update_preferences", {"set": [{"attribute": "max_distance_km", "value": -1, "importance": "required"}]}, ValidationError),
            ("update_preferences", {"remove": ["base_fee"]}, ValidationError),
            ("update_preferences", {"set": [{"attribute": "spark_certified", "value": 1, "importance": "required"}]}, ValidationError),
            ("calculate_fees_scenario", {"school_ids": ["CENTRE:A"], "overrides": {"gross_household_income": float("nan")}}, ValidationError),
            ("calculate_fees_scenario", {"school_ids": ["CENTRE:A"], "overrides": {"base_fee": 1}}, ValidationError),
            ("calculate_fees_scenario", {"school_ids": ["CENTRE:A"], "overrides": {"citizenship": None}}, ValidationError),
            ("search_rank_compare_schools", {"limit": True}, ValidationError),
        ]
        for name, arguments, error in invalid:
            with self.subTest(name=name, arguments=arguments):
                service = self.service()
                original = service.staged_profile
                self.update(service)
                with self.assertRaises(error):
                    service.invoke(name, arguments)
                self.assertEqual(service.staged_profile, original)
                with self.assertRaises(ValueError):
                    service.export_validated_state(response_validated=True)

    def test_tool_failure_and_invalid_final_response_discard_changes(self):
        for failure in ("tool", "response", "abort", "shadow"):
            with self.subTest(failure=failure):
                service = self.service()
                original = service.staged_profile
                self.update(service)
                if failure == "tool":
                    with patch.object(self.schools, "get_structured_facts", side_effect=RuntimeError("provider unavailable")):
                        with self.assertRaises(RuntimeError):
                            service.invoke("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees"})
                elif failure == "response":
                    with self.assertRaises(ValueError):
                        service.export_validated_state(response_validated=False)
                elif failure == "abort":
                    service.abort()
                else:
                    self.assertEqual(service.export_validated_state(response_validated=True, shadow=True), original)
                    continue
                self.assertEqual(service.staged_profile, original)

    def test_conflict_requires_typed_resolution(self):
        service = self.service()
        self.update(service)
        conflict = self.update(service, value="Malay")
        self.assertEqual(conflict.status, "needs_input")
        self.assertEqual(service.staged_profile["hard_constraints"]["language"], "Chinese")
        blocked = self.update(service, "pedagogy", "Montessori", "preferred")
        self.assertEqual(blocked.missing_inputs, ["pending_decision_resolution"])
        service.invoke("reset_continue_preferences", {"operation": "resolve_contradiction", "choice": "use_incoming"})
        self.assertEqual(service.staged_profile["hard_constraints"]["language"], "Malay")
        self.assertFalse(service.staged_profile.get("pending_contradiction"))

    def test_pending_strength_relaxation_and_reset(self):
        for pending, request, expected in (
            ({"pending": {"kind": "language", "value": "Chinese"}},
             {"operation": "resolve_strength", "choice": "required"}, {"language": "Chinese"}),
            ({"hard_constraints": {"max_distance_km": 1}, "pending_relaxation": {
                "kind": "distance", "attribute": "max_distance_km", "old_value": 1, "new_value": 2}},
             {"operation": "resolve_relaxation", "choice": "approve"}, {"max_distance_km": 2}),
            ({"hard_constraints": {"language": "Chinese"}}, {"operation": "reset"}, {}),
        ):
            with self.subTest(request=request):
                self.context.profile = pending
                service = self.service()
                result = service.invoke("reset_continue_preferences", request)
                self.assertEqual(result.status, "ok")
                self.assertEqual(service.staged_profile.get("hard_constraints", {}), expected)

    def test_registered_tools_and_validation_failure_abort(self):
        service = self.service()
        tools = {t.name: t for t in service.registered_tools()}
        self.assertEqual(set(tools), set(CAPABILITIES))
        self.assertIsInstance(tools["read_school_facts"].invoke({
            "school_ids": ["CENTRE:A"], "operation": "transport",
        }), StructuredToolResult)
        original = service.staged_profile
        self.update(service)
        with self.assertRaises(ValidationError):
            tools["read_school_facts"].invoke({"school_ids": ["CENTRE:A"], "operation": "invented"})
        self.assertEqual(service.staged_profile, original)

    def test_lazy_reads_missing_inputs_access_and_bounds(self):
        loader = Mock(return_value=None)
        service = self.service(school_index_loader=loader, general_retriever_loader=loader)
        loader.assert_not_called()
        self.locations.attach_distances.assert_not_called()
        missing = service.invoke("find_nearby_schools", {})
        self.assertEqual(missing.missing_inputs, ["home_postal_code"])
        nearby = service.invoke("find_nearby_schools", {"postal_code": "123456"})
        self.assertEqual(nearby.data["missing_location_count"], 1)
        self.assertEqual(nearby.data["records"][0]["distance_km"], 0.5)
        unavailable = service.invoke("search_school_evidence", {"school_ids": ["CENTRE:A"], "query": "Outdoor learning"})
        self.assertEqual(unavailable.status, "unavailable")
        self.assertNotIn("answer_candidate", unavailable.model_dump())
        self.assertEqual(service.invoke("search_general_guidance", {"query": "Montessori"}).status, "unavailable")
        self.context.capabilities = ["read_school_facts"]
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.service().invoke("update_preferences", {"remove": ["language"]})
        service = self.service()
        for _ in range(12):
            service.invoke("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees"})
        with self.assertRaisesRegex(ValueError, "limit"):
            service.invoke("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees"})

    def test_evidence_attribution_and_no_evidence_are_structured(self):
        index = {"pages": [{"school_id": "CENTRE:A", "chunks": [{
            "school_id": "CENTRE:A", "chunk_id": "chunk:A", "text": "Outdoor learning every day.",
            "source_url": "https://example.com/a", "title": "School A",
            "retrieved_at": "2026-10-10T00:00:00Z",
        }]}]}
        service = self.service(school_index_loader=lambda: index)
        result = service.invoke("search_school_evidence", {"school_ids": ["CENTRE:A", "CENTRE:B"], "query": "Outdoor learning"})
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.citations[0].school_id, "CENTRE:A")
        self.assertEqual(result.data["passages"][0]["school_id"], "CENTRE:A")
        result = service.invoke("search_school_evidence", {"school_ids": ["CENTRE:B"], "query": "Outdoor learning"})
        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(result.data["passages"], [])

    def test_mutation_and_output_limits_discard_staged_state(self):
        service = self.service()
        original = service.staged_profile
        for _ in range(4):
            self.update(service)
        with self.assertRaisesRegex(ValueError, "mutation limit"):
            self.update(service)
        self.assertEqual(service.staged_profile, original)
        service = self.service()
        self.update(service)
        with patch.object(self.schools, "get_structured_facts", return_value=[{
            "available": True, "facts": {"oversized": "x" * 5001},
        }]):
            with self.assertRaises(ValidationError):
                service.invoke("read_school_facts", {"school_ids": ["CENTRE:A"], "operation": "fees"})
        self.assertEqual(service.staged_profile, original)

    def test_general_retrieval_returns_typed_provenance_without_generation(self):
        from SystemCode.src.backend.agents.tools import CuratedGeneralKnowledgeRetriever
        retriever = CuratedGeneralKnowledgeRetriever({"chunks": [{
            "chunk_id": "general:1", "text": "Montessori uses child-led learning.",
            "source_url": "https://example.com/guide", "title": "Guide",
            "retrieved_at": "2026-10-10T00:00:00Z", "authority": "Reviewed guide",
        }]})
        service = self.service(general_retriever_loader=lambda: retriever)
        result = service.invoke("search_general_guidance", {"query": "Montessori"})
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.citations[0].evidence_scope, "general")
        self.assertIsNone(result.citations[0].school_id)
        self.assertEqual(result.data["passages"][0]["text"], "Montessori uses child-led learning.")


if __name__ == "__main__":
    unittest.main()
