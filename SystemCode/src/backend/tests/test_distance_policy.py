import unittest

from stage1.distance_policy import (
    DEFAULT_HOME_RADIUS_KM,
    NEAR_HOME_RADIUS_KM,
    chat_search_radius_km,
    distance_opt_out,
    effective_search_radius_km,
    explicit_search_radius_km,
)
from stage1.nlp_mapper import map_text_to_filters, merge_preference_profile, summarize_profile


class DistancePolicyTests(unittest.TestCase):
    def test_near_home_phrases_set_one_kilometre(self):
        for message in (
            "Spark kindergarten near my place",
            "school close to home",
            "preschool near home",
        ):
            with self.subTest(message=message):
                profile = map_text_to_filters(message)
                self.assertEqual(profile["hard_constraints"]["max_distance_km"], NEAR_HOME_RADIUS_KM)

    def test_explicit_kilometres_override_near_home_default(self):
        profile = map_text_to_filters("SPARK preschool within 3 km near my place")
        self.assertEqual(profile["hard_constraints"]["max_distance_km"], 3.0)

    def test_default_radius_when_postal_present(self):
        profile = map_text_to_filters("SPARK is required")
        self.assertIsNone(profile["hard_constraints"].get("max_distance_km"))
        self.assertIsNone(explicit_search_radius_km(profile))
        self.assertEqual(effective_search_radius_km(profile, "570301"), DEFAULT_HOME_RADIUS_KM)
        self.assertEqual(chat_search_radius_km(profile, "570301"), NEAR_HOME_RADIUS_KM)

    def test_chat_search_uses_explicit_radius_and_respects_opt_out(self):
        profile = map_text_to_filters("SPARK within 3 km")
        self.assertEqual(chat_search_radius_km(profile, "570301"), 3.0)
        self.assertEqual(chat_search_radius_km(profile, None), 3.0)
        opted_out = merge_preference_profile(profile, "anywhere in Singapore")
        self.assertIsNone(chat_search_radius_km(opted_out, "570301"))
        no_distance = map_text_to_filters("SPARK is required")
        self.assertIsNone(chat_search_radius_km(no_distance, None))

    def test_opt_out_disables_default_radius(self):
        profile = merge_preference_profile(
            map_text_to_filters("SPARK is required"),
            "search anywhere in Singapore",
        )
        self.assertTrue(profile.get("skip_default_distance"))
        self.assertIsNone(effective_search_radius_km(profile, "570301"))

    def test_summarize_shows_default_distance_with_postal(self):
        profile = map_text_to_filters("SPARK is required")
        summary = summarize_profile(profile, home_postal_code="570301")
        self.assertIn("Distance (default): within 5 km from home", summary)


if __name__ == "__main__":
    unittest.main()
