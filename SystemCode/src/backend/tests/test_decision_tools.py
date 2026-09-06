import datetime as dt
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from SystemCode.src.backend.agents import (
    DECISION_AND_CALCULATION_TOOL_NAMES,
    QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
    DecisionToolRequest,
    StructuredSchoolFactsToolRequest,
    create_decision_and_calculation_tools,
    create_structured_school_facts_tool,
)
from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    CapabilityToolResult,
    ConversationRequestContext,
    EvidenceIndexContext,
)
from SystemCode.src.backend.repositories.school_repository import SchoolRepository


def school(school_id: str, name: str, **facts):
    return AuthoritativeSchoolContext(
        school_id=school_id,
        facts={"school_id": school_id, "name": name, **facts},
    )


def context(
    message: str,
    *, selected=None,
    eligible=None,
    excluded=None,
    family=None,
    profile=None,
    postal_code="123456",
):
    selected = selected or []
    eligible = eligible or []
    excluded = excluded or []
    return ConversationRequestContext(
        message=message,
        profile=profile or {},
        family=family,
        home_postal_code=postal_code,
        selected_school_ids=[item.school_id for item in selected],
        eligible_school_ids=[item.school_id for item in eligible],
        excluded_school_ids=[item.school_id for item in excluded],
        selected_schools=selected,
        eligible_schools=eligible,
        excluded_schools=excluded,
        selected_school_evidence=EvidenceIndexContext(scope="school", available=False),
        general_knowledge_evidence=EvidenceIndexContext(scope="general", available=False),
        catalogue_version="test-catalogue",
    )


def by_name(tools):
    return {tool.name: tool for tool in tools}


class DecisionAndCalculationToolTests(unittest.TestCase):
    def test_registers_nine_strict_read_only_tools(self):
        evaluator = Mock()
        tools = create_decision_and_calculation_tools(context("compare these"), evaluator)

        self.assertEqual({tool.name for tool in tools}, DECISION_AND_CALCULATION_TOOL_NAMES)
        self.assertTrue(all(isinstance(tool, BaseTool) for tool in tools))
        self.assertTrue(all(tool.args_schema is DecisionToolRequest for tool in tools))
        with self.assertRaises(ValidationError):
            tools[0].invoke({"school_ids": ["CENTRE:FORGED"]})

    def test_decisions_reuse_authoritative_context_without_mutating_it(self):
        selected = [
            school("CENTRE:A", "Alpha", match_score=85, net_monthly_fee=700, distance_km=2),
            school("CENTRE:B", "Beta", match_score=75, net_monthly_fee=600, distance_km=1),
        ]
        turn = context("Which selected preschool do you recommend?", selected=selected)
        snapshot = deepcopy(turn)
        tools = by_name(create_decision_and_calculation_tools(turn, Mock()))

        recommendation = tools["recommend_selected_school"].invoke({})
        comparison = tools["compare_selected_schools"].invoke({})

        self.assertIn("recommend Alpha", recommendation.answer_candidate)
        self.assertIn("Alpha", comparison.answer_candidate)
        self.assertIn("Beta", comparison.answer_candidate)
        self.assertFalse(recommendation.mutates_profile)
        self.assertEqual(turn, snapshot)
        self.assertTrue(recommendation.grounding_facts)

    def test_closest_and_missing_context_answers_are_deterministic(self):
        eligible = [
            school("CENTRE:A", "Alpha", distance_km=1.5),
            school("CENTRE:B", "Beta", distance_km=0.4),
        ]
        closest = by_name(create_decision_and_calculation_tools(
            context("Which is closest?", eligible=eligible), Mock(),
        ))["find_closest_school"].invoke({})
        self.assertIn("Beta", closest.answer_candidate)
        self.assertIn("0.40 km", closest.answer_candidate)

        missing = by_name(create_decision_and_calculation_tools(
            context("Explain the first result", eligible=[]), Mock(),
        ))["explain_top_ranked_school"].invoke({})
        self.assertIn("show recommendations first", missing.answer_candidate.lower())

    def test_what_if_uses_authoritative_family_and_evaluator(self):
        baseline = school(
            "CENTRE:A", "Alpha", net_monthly_fee=700, status="estimated",
        )
        turn = context(
            "What if my income is 6000?",
            selected=[baseline],
            family={
                "dob": dt.date(2023, 1, 1),
                "admission_date": dt.date(2026, 1, 1),
                "gross_household_income": 4500,
            },
        )
        evaluator = Mock()
        evaluator.evaluate.return_value = [{
            "school_id": "CENTRE:A", "name": "Alpha",
            "net_monthly_fee": 850, "status": "estimated",
        }]

        result = by_name(create_decision_and_calculation_tools(
            turn, evaluator,
        ))["run_what_if_scenario"].invoke({})

        self.assertIn("$700", result.answer_candidate)
        self.assertIn("$850", result.answer_candidate)
        self.assertEqual(
            evaluator.evaluate.call_args.args[2].gross_household_income, 6000,
        )
        self.assertEqual(turn.family.gross_household_income, 4500)
        self.assertEqual(result.evidence_category, "calculated_estimate")

    def test_exclusion_uses_precomputed_authoritative_result(self):
        excluded = [school(
            "CENTRE:A", "Alpha", status="ineligible_age",
            reason="the child is outside the supported age range",
        )]
        turn = context(
            "Why was Alpha excluded?",
            excluded=excluded,
            family={
                "dob": dt.date(2023, 1, 1),
                "admission_date": dt.date(2026, 1, 1),
                "gross_household_income": 4500,
            },
        )
        evaluator = Mock()
        result = by_name(create_decision_and_calculation_tools(
            turn, evaluator,
        ))["explain_school_exclusion"].invoke({})

        self.assertIn("outside the supported age range", result.answer_candidate)
        evaluator.evaluate.assert_not_called()
        self.assertFalse(result.mutates_profile)


class StructuredSchoolFactsToolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "catalogue.json"
        path.write_text(json.dumps([
            {
                "school_id": "CENTRE:A", "centre_name_x": "Alpha",
                "food_offered": "Halal food", "has_vacancy_data": True,
                "n1_vacancy_current_month": "Available",
                "n1_vacancy_next_month": "Limited",
                "last_updated": "2025-01-01",
            },
            {
                "school_id": "CENTRE:B", "centre_name_x": "Beta",
                "has_vacancy_data": False,
            },
        ]), encoding="utf-8")
        self.repository = SchoolRepository(path)

    def tearDown(self):
        self.directory.cleanup()

    def test_repository_projects_only_allowlisted_food_and_vacancy_fields(self):
        food = self.repository.get_structured_facts(
            ["CENTRE:A"], "food", as_of=dt.date(2026, 9, 6),
        )[0]
        vacancy = self.repository.get_structured_facts(
            ["CENTRE:A"], "vacancy", as_of=dt.date(2026, 9, 6),
        )[0]

        self.assertEqual(food["facts"], {"food_offered": "Halal food"})
        self.assertEqual(food["freshness"], "stale")
        self.assertEqual(vacancy["facts"]["n1_vacancy_current_month"], "Available")
        self.assertNotIn("food_offered", vacancy["facts"])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.repository.get_structured_facts(["CENTRE:A"], "cypher")

    def test_tool_rejects_unknown_ids_and_reports_unavailable_data(self):
        selected = [school("CENTRE:A", "Alpha"), school("CENTRE:B", "Beta")]
        tool = create_structured_school_facts_tool(
            context("Does it have vacancies?", selected=selected), self.repository,
        )
        self.assertEqual(tool.name, QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME)
        self.assertIs(tool.args_schema, StructuredSchoolFactsToolRequest)

        available = tool.invoke({"operation": "vacancy", "school_ids": ["CENTRE:A"]})
        unavailable = tool.invoke({"operation": "vacancy", "school_ids": ["CENTRE:B"]})
        self.assertIn("N1=Available", available.answer_candidate)
        self.assertIn("may be stale", available.answer_candidate)
        self.assertIn("unavailable", unavailable.answer_candidate)
        self.assertEqual(available.evidence_category, "authoritative_fact")
        with self.assertRaisesRegex(ValueError, "server-resolved"):
            tool.invoke({"operation": "food", "school_ids": ["CENTRE:FORGED"]})
        with self.assertRaises(ValidationError):
            tool.invoke({"operation": "cypher", "school_ids": ["CENTRE:A"]})


if __name__ == "__main__":
    unittest.main()
