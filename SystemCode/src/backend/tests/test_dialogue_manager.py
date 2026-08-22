import unittest

from stage1.conversation import update_conversation
from stage1.dialogue_manager import catalogue_facets, next_best_question


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


if __name__ == "__main__":
    unittest.main()
