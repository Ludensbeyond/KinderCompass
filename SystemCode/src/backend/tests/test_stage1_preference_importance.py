import unittest

from stage1.nlp_mapper import map_text_to_filters, merge_preference_profile


class Stage1PreferenceImportanceTests(unittest.TestCase):
    def test_each_explicit_importance_level_is_parsed(self):
        cases = (
            ("SPARK is required", "required"),
            ("SPARK is high priority", "high_priority"),
            ("SPARK is preferred", "preferred"),
            ("SPARK is nice to have", "nice_to_have"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                profile = map_text_to_filters(message)
                item = next(item for item in profile["preference_items"] if item["attribute"] == "spark_certified")
                self.assertEqual(item["importance"], expected)

    def test_importance_cues_attach_to_their_preference(self):
        profile = map_text_to_filters(
            "SPARK is required, transport is high priority, "
            "Montessori is preferred, and halal food is nice to have"
        )
        importance = {item["attribute"]: item["importance"] for item in profile["preference_items"]}
        self.assertEqual(importance["spark_certified"], "required")
        self.assertEqual(importance["transport"], "high_priority")
        self.assertEqual(importance["pedagogy"], "preferred")
        self.assertEqual(importance["food"], "nice_to_have")

    def test_language_importance_is_not_inferred_from_another_preference(self):
        profile = map_text_to_filters("Chinese is preferred, but SPARK is required")
        self.assertNotIn("language", profile["hard_constraints"])
        importance = {item["attribute"]: item["importance"] for item in profile["preference_items"]}
        self.assertEqual(importance["language"], "preferred")
        self.assertEqual(importance["spark_certified"], "required")

    def test_leading_requirement_cue_can_govern_a_following_preference_list(self):
        profile = map_text_to_filters("Need Montessori with Chinese and SPARK")
        self.assertEqual(profile["hard_constraints"]["language"], "Chinese")
        importance = {item["attribute"]: item["importance"] for item in profile["preference_items"]}
        self.assertEqual(importance["pedagogy"], "required")
        self.assertEqual(importance["language"], "required")
        self.assertEqual(importance["spark_certified"], "required")

    def test_bare_and_explicitly_preferred_montessori_are_not_required(self):
        for message in ("Montessori", "Montessori is preferred"):
            with self.subTest(message=message):
                profile = map_text_to_filters(message)
                item = next(item for item in profile["preference_items"] if item["attribute"] == "pedagogy")
                self.assertEqual(item["importance"], "preferred")
                self.assertEqual(profile["preferences"]["pedagogy"]["weight"], 4)

    def test_existing_importance_survives_a_later_turn_without_a_new_cue(self):
        profile = merge_preference_profile(None, "SPARK is high priority")
        profile = merge_preference_profile(profile, "I also want transport")
        importance = {item["attribute"]: item["importance"] for item in profile["preference_items"]}
        self.assertEqual(importance["spark_certified"], "high_priority")
        self.assertEqual(importance["transport"], "preferred")

    def test_explicit_preferred_language_downgrades_only_that_language(self):
        profile = merge_preference_profile(None, "Chinese is required")
        profile = merge_preference_profile(profile, "Chinese is preferred, SPARK is required")
        self.assertNotIn("language", profile["hard_constraints"])
        importance = {item["attribute"]: item["importance"] for item in profile["preference_items"]}
        self.assertEqual(importance["language"], "preferred")
        self.assertEqual(importance["spark_certified"], "required")


if __name__ == "__main__":
    unittest.main()
