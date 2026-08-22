import unittest
import datetime as dt
from pathlib import Path
from unittest.mock import Mock

from SystemCode.src.backend.domain.catalogue import EvaluatedSchool
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.services.preference_service import PreferenceService
from stage1.conversation import update_conversation
from stage1.dialogue_manager import catalogue_facets, next_best_question
from stage1.dialogue_manager import propose_constraint_relaxation
from stage1.intent_router import classify_intent


class DecisionAwareDialogueTests(unittest.TestCase):
    def setUp(self):
        self.schools = [
            {"second_languages_offered": "Chinese", "pedagogy": "Montessori",
             "spark_certified": "Yes", "provision_of_transport": "Yes", "food_offered": "Halal"},
            {"second_languages_offered": "Malay", "pedagogy": "Play-based",
             "spark_certified": "No", "provision_of_transport": "No", "food_offered": "No pork"},
            {"second_languages_offered": "Tamil", "pedagogy": "Montessori",
             "spark_certified": "Yes", "provision_of_transport": "No", "food_offered": "Standard"},
            {"second_languages_offered": "Chinese", "pedagogy": "Reggio Emilia",
             "spark_certified": "No", "provision_of_transport": "Yes", "food_offered": "Standard"},
        ]
        self.facets = catalogue_facets(self.schools)

    def test_selects_high_information_unanswered_attribute(self):
        profile = {"hard_constraints": {}, "preferences": {"spark_certified": {"value": True}}}
        attribute, question = next_best_question(profile, self.facets)
        self.assertEqual(attribute, "transport")
        self.assertIn("transport", question)

    def test_does_not_repeat_an_answered_dimension(self):
        profile = {
            "hard_constraints": {"language": "Chinese"},
            "preferences": {"pedagogy": {"value": "Montessori"}},
        }
        attribute, _ = next_best_question(profile, self.facets)
        self.assertNotIn(attribute, {"language", "pedagogy"})

    def test_conversation_records_reason_for_next_question(self):
        turn = update_conversation(
            None, "SPARK is preferred", candidate_facets=self.facets
        )
        self.assertTrue(turn["ready_to_search"])
        self.assertEqual(turn["profile"]["next_question_attribute"], "transport")
        self.assertIn("Show recommendations", turn["question"])


class ContradictionDetectionTests(unittest.TestCase):
    def test_conflicting_required_languages_require_explicit_repair(self):
        first = update_conversation(None, "Chinese is required")
        conflict = update_conversation(first["profile"], "Malay is required")
        self.assertEqual(conflict["status"], "needs_clarification")
        self.assertFalse(conflict["ready_to_search"])
        self.assertIn("already require Chinese", conflict["question"])
        self.assertEqual(conflict["profile"]["hard_constraints"]["language"], "Chinese")

        resolved = update_conversation(conflict["profile"], "use Malay")
        self.assertTrue(resolved["ready_to_search"])
        self.assertEqual(resolved["profile"]["hard_constraints"]["language"], "Malay")
        self.assertNotIn("pending_contradiction", resolved["profile"])

    def test_unresolved_contradiction_cannot_be_silently_overwritten(self):
        first = update_conversation(None, "Chinese is required")
        conflict = update_conversation(first["profile"], "Malay is required")
        repeated = update_conversation(conflict["profile"], "show recommendations")
        self.assertFalse(repeated["ready_to_search"])
        self.assertEqual(repeated["profile"]["hard_constraints"]["language"], "Chinese")

    def test_conflicting_required_pedagogies_can_keep_existing(self):
        first = update_conversation(None, "Montessori is required")
        conflict = update_conversation(first["profile"], "Reggio is required")
        self.assertEqual(conflict["status"], "needs_clarification")
        resolved = update_conversation(conflict["profile"], "keep Montessori")
        self.assertEqual(resolved["profile"]["preferences"]["pedagogy"]["value"], "Montessori")


class ControlledRelaxationTests(unittest.TestCase):
    def test_proposes_smallest_distance_change_without_applying_it(self):
        profile = update_conversation(None, "within 1 km")["profile"]
        proposal = propose_constraint_relaxation(profile)
        self.assertEqual(profile["hard_constraints"]["max_distance_km"], 1)
        self.assertEqual(proposal["new_value"], 2)

    def test_relaxation_requires_explicit_approval(self):
        profile = update_conversation(None, "within 1 km")["profile"]
        profile["pending_relaxation"] = propose_constraint_relaxation(profile)
        pending = update_conversation(profile, "maybe")
        self.assertFalse(pending["ready_to_search"])
        self.assertEqual(pending["profile"]["hard_constraints"]["max_distance_km"], 1)

        approved = update_conversation(pending["profile"], "apply relaxation")
        self.assertEqual(approved["profile"]["hard_constraints"]["max_distance_km"], 2)
        self.assertNotIn("pending_relaxation", approved["profile"])

    def test_declining_preserves_constraints(self):
        profile = update_conversation(None, "Chinese is required")["profile"]
        profile["pending_relaxation"] = propose_constraint_relaxation(profile)
        declined = update_conversation(profile, "keep constraints")
        self.assertEqual(declined["profile"]["hard_constraints"]["language"], "Chinese")


class WhatIfAndExclusionTests(unittest.TestCase):
    @staticmethod
    def centre(fee=160, *, eligible=True, reason=None):
        return EvaluatedSchool.model_validate({
            "school_id": "CENTRE:A", "name": "Example Preschool",
            "status": "estimated" if eligible else "ineligible", "eligible": eligible,
            "net_monthly_fee": fee if eligible else None,
            "preferred_programme": "full_day",
            "preferred_programme_available": eligible,
            "programme_options": [], "reason": reason,
        })

    def setUp(self):
        self.evaluation = Mock()
        self.service = PreferenceService(Mock(), self.evaluation, Mock(), Path("."))
        self.family = FamilyDetails(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10),
            gross_household_income=4500, working_hours_per_month=56,
        )

    def test_what_if_is_routed_and_does_not_mutate_family(self):
        self.assertEqual(classify_intent("What if my working hours are 55?").intent, "run_what_if_scenario")
        self.evaluation.evaluate.side_effect = [[self.centre(160)], [self.centre(750)]]
        result = self.service._what_if(
            "What if my working hours are 55?", ["CENTRE:A"], {}, self.family
        )
        self.assertIn("$160", result["question"])
        self.assertIn("$750", result["question"])
        self.assertIn("were not changed", result["question"])
        self.assertEqual(self.family.working_hours_per_month, 56)

    def test_exclusion_uses_stage2_reason(self):
        self.evaluation.evaluate.return_value = [
            self.centre(eligible=False, reason="the required age level is not offered")
        ]
        result = self.service._explain_exclusion(
            "Why was Example Preschool excluded?", ["CENTRE:A"], {}, self.family
        )
        self.assertIn("required age level is not offered", result["question"])
        self.assertFalse(result["ranking_affected"])


if __name__ == "__main__":
    unittest.main()
