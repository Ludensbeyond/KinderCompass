import unittest

from stage1.scorer import individually_relaxable_required_preferences, rank_schools, score_school


def make_profile(*, spark_importance="preferred", transport_importance="preferred"):
    return {
        "preferences": {
            "spark_certified": {"value": True, "weight": 4, "desired": True},
            "transport": {"value": True, "weight": 3, "desired": True},
        },
        "preference_items": [
            {"attribute": "spark_certified", "value": True, "importance": spark_importance},
            {"attribute": "transport", "value": True, "importance": transport_importance},
        ],
    }


def school(school_id, *, spark="Yes", transport="Yes", name=None):
    return {
        "school_id": school_id,
        "name": name or school_id,
        "spark_certified": spark,
        "provision_of_transport": transport,
    }


class Stage1ScorerRankingTests(unittest.TestCase):
    def test_known_match_and_mismatch_are_verifiable(self):
        profile = make_profile()
        matched = score_school(profile, school("MATCH"))
        mismatched = score_school(profile, school("MISMATCH", spark="No"))
        self.assertEqual(matched["match_score"], 100.0)
        self.assertEqual(matched["profile_confidence"], 1.0)
        self.assertEqual(mismatched["match_score"], 42.9)
        self.assertEqual(mismatched["profile_confidence"], 1.0)
        self.assertEqual(mismatched["match_breakdown"][0]["status"], "not_matched")

    def test_all_known_mismatches_have_zero_match_full_confidence_and_zero_combined(self):
        profile = make_profile()
        scored = score_school(profile, school("ALL_MISMATCH", spark="No", transport="No"))
        self.assertEqual(scored["match_score"], 0.0)
        self.assertEqual(scored["profile_confidence"], 1.0)
        self.assertEqual(scored["combined_score"], 0.0)

    def test_unknown_evidence_does_not_change_match_denominator(self):
        scored = score_school(make_profile(), school("PARTIAL", transport=None))
        self.assertEqual(scored["match_score"], 100.0)
        self.assertEqual(scored["profile_confidence"], 0.57)
        self.assertEqual(scored["combined_score"], 75.6)
        self.assertEqual(scored["match_breakdown"][1]["status"], "unknown")

    def test_no_known_evidence_has_zero_match_and_zero_confidence(self):
        scored = score_school(make_profile(), school("UNKNOWN", spark=None, transport=None))
        self.assertEqual((scored["match_score"], scored["profile_confidence"], scored["combined_score"]), (0.0, 0.0, 0.0))

    def test_required_mismatch_is_excluded_but_unknown_is_retained(self):
        profile = {
            "preferences": {"spark_certified": {"value": True, "weight": 4, "desired": True}},
            "preference_items": [{"attribute": "spark_certified", "value": True, "importance": "required"}],
        }
        ranked = rank_schools(profile, [school("FAIL", spark="No"), school("UNKNOWN", spark=None)])
        self.assertEqual([item["school_id"] for item in ranked], ["UNKNOWN"])
        self.assertIsNone(ranked[0]["match_breakdown"][0]["matched"])
        self.assertEqual(ranked[0]["match_breakdown"][0]["status"], "unknown")

    def test_importance_multipliers_change_weighted_match(self):
        profile = make_profile(spark_importance="nice_to_have", transport_importance="high_priority")
        spark_only = school("SPARK", spark="Yes", transport="No")
        transport_only = school("TRANSPORT", spark="No", transport="Yes")
        ranked = rank_schools(profile, [spark_only, transport_only])
        self.assertEqual(ranked[0]["school_id"], "TRANSPORT")
        self.assertEqual(ranked[0]["match_score"], 69.2)
        self.assertEqual(ranked[1]["match_score"], 30.8)

    def test_combined_score_can_put_complete_candidate_first(self):
        profile = make_profile(spark_importance="nice_to_have", transport_importance="high_priority")
        incomplete_high_match = school("INCOMPLETE", spark="Yes", transport=None)
        complete_lower_match = school("COMPLETE", spark="No", transport="Yes")
        ranked = rank_schools(profile, [incomplete_high_match, complete_lower_match])
        self.assertEqual(ranked[0]["school_id"], "COMPLETE")
        self.assertEqual(ranked[0]["combined_score"], 83.2)
        self.assertLess(ranked[1]["combined_score"], ranked[0]["combined_score"])
        self.assertLess(ranked[0]["match_score"], ranked[1]["match_score"])
        expected_scores = {
            "COMPLETE": (69.23076923076923 * 100) ** 0.5,
            "INCOMPLETE": (100 * (2 / 6.5 * 100)) ** 0.5,
        }
        for item in ranked:
            self.assertAlmostEqual(
                item["combined_score"], round(expected_scores[item["school_id"]], 1),
            )

    def test_ties_use_ascending_stable_school_id(self):
        profile = {"preferences": {"spark_certified": {"value": True, "weight": 1}}, "preference_items": []}
        ranked = rank_schools(profile, [school("Z", name="Alpha"), school("A", name="Zulu")])
        self.assertEqual([item["school_id"] for item in ranked], ["A", "Z"])

    def test_zero_preferences_have_neutral_scores(self):
        scored = score_school({"preferences": {}, "preference_items": []}, school("NONE"))
        self.assertEqual((scored["match_score"], scored["profile_confidence"], scored["combined_score"]), (100.0, 1.0, 100.0))

    def test_missing_sentinels_are_unknown_across_supported_evidence_fields(self):
        cases = (
            ("spark_certified", True, "spark_certified", " n/a "),
            ("transport", True, "provision_of_transport", "UNKNOWN"),
            ("operator_scheme", "Anchor Operator Scheme", "operator_scheme", "null"),
            ("food", "halal", "food_offered", "not available"),
            ("full_day", True, "weekday_full_day", "unknown"),
            ("pedagogy", "Montessori", "pedagogy", " NA "),
            ("language:Chinese", "Chinese", "second_languages_offered", "n/a"),
        )
        for attribute, target, field, value in cases:
            with self.subTest(field=field, value=value):
                preference_key = attribute
                item_attribute = "language" if attribute.startswith("language:") else attribute
                profile = {
                    "preferences": {preference_key: {"value": target, "weight": 1}},
                    "preference_items": [{
                        "attribute": item_attribute, "value": target, "importance": "preferred",
                    }],
                }
                scored = score_school(profile, {field: value})
                self.assertEqual(scored["match_breakdown"][0]["status"], "unknown")
                self.assertEqual(scored["profile_confidence"], 0.0)

    def test_missing_language_tokens_do_not_become_languages_or_mismatches(self):
        profile = {
            "preferences": {"language:Chinese": {"value": "Chinese", "weight": 4}},
            "preference_items": [{"attribute": "language", "value": "Chinese", "importance": "preferred"}],
        }
        for value in ("na", "n/a", "unknown", "Chinese|na|unknown"):
            with self.subTest(value=value):
                scored = score_school(profile, {"second_languages_offered": value})
                if value == "Chinese|na|unknown":
                    self.assertEqual(scored["match_breakdown"][0]["status"], "matched")
                    self.assertEqual(scored["profile_confidence"], 1.0)
                else:
                    self.assertEqual(scored["match_breakdown"][0]["status"], "unknown")
                    self.assertEqual(scored["profile_confidence"], 0.0)

    def test_full_day_requires_a_known_status_or_structured_hours(self):
        profile = {
            "preferences": {"full_day": {"value": True, "weight": 1}},
            "preference_items": [{"attribute": "full_day", "value": True, "importance": "preferred"}],
        }
        for value in ("n/a", "unknown", "some text", ""):
            with self.subTest(value=value):
                scored = score_school(profile, {"weekday_full_day": value})
                self.assertEqual(scored["match_breakdown"][0]["status"], "unknown")
                self.assertEqual(scored["profile_confidence"], 0.0)

        confirmed_hours = score_school(profile, {"weekday_full_day": "07:00-19:00"})
        self.assertEqual(confirmed_hours["match_breakdown"][0]["status"], "matched")
        self.assertEqual(confirmed_hours["profile_confidence"], 1.0)
        confirmed_no = score_school(profile, {"weekday_full_day": "No"})
        self.assertEqual(confirmed_no["match_breakdown"][0]["status"], "not_matched")
        self.assertEqual(confirmed_no["profile_confidence"], 1.0)

    def test_pedagogy_availability_remains_partial_and_does_not_claim_a_match(self):
        profile = {
            "preferences": {"pedagogy": {"value": "Montessori", "weight": 2}},
            "preference_items": [{"attribute": "pedagogy", "value": "Montessori", "importance": "required"}],
        }
        scored = score_school(profile, {"school_id": "DERIVED", "pedagogy": "Montessori"})
        item = scored["match_breakdown"][0]
        self.assertEqual(item["availability"], 0.65)
        self.assertEqual(item["evidence_state"], "derived")
        self.assertEqual(item["status"], "inferred")
        self.assertIsNone(item["matched"])
        self.assertEqual(item["inferred_match"], True)
        self.assertEqual(item["contribution"], 0.0)
        self.assertEqual(scored["match_score"], 0.0)
        self.assertEqual(scored["profile_confidence"], 0.65)

    def test_food_matcher_requires_explicit_support_and_preserves_unknown(self):
        profile = {
            "preferences": {"food": {"value": "halal", "weight": 1}},
            "preference_items": [{"attribute": "food", "value": "halal", "importance": "required"}],
        }
        for text, expected in (("Halal meals", "partially_supported"),
                               ("No pork or lard", "unknown"),
                               ("Pork is served", "partially_supported"),
                               ("Meals are provided", "unknown"),
                               ("Kitchen information pending", "unknown")):
            with self.subTest(text=text):
                item = score_school(profile, {"food_offered": text})["match_breakdown"][0]
                self.assertEqual(item["status"], expected)
                if expected == "partially_supported":
                    self.assertIn(item["partial_match"], (True, False))
                    self.assertEqual(item["contribution"], 0.0)
                else:
                    self.assertIsNone(item["partial_match"])

        no_pork_profile = {
            "preferences": {"food": {"value": "no_pork", "weight": 1}},
            "preference_items": [{"attribute": "food", "value": "no_pork", "importance": "required"}],
        }
        no_pork_item = score_school(no_pork_profile, {"food_offered": "No pork or lard"})["match_breakdown"][0]
        self.assertEqual(no_pork_item["status"], "partially_supported")
        self.assertTrue(no_pork_item["partial_match"])

    def test_freshness_is_reported_without_turning_stale_data_into_a_mismatch(self):
        profile = {
            "preferences": {"spark_certified": {"value": True, "weight": 1}},
            "preference_items": [{"attribute": "spark_certified", "value": True, "importance": "required"}],
        }
        item = score_school(profile, {
            "spark_certified": "No", "last_updated": "2020-01-01",
        })["match_breakdown"][0]
        self.assertEqual(item["freshness"], "stale")
        self.assertEqual(item["status"], "unknown")
        self.assertIsNone(item["matched"])

    def test_ranking_uses_unrounded_score_for_near_ties_and_is_repeatable(self):
        profile = {"preferences": {
            "spark_certified": {"value": True, "weight": 1.0002},
            "transport": {"value": True, "weight": 1},
        }, "preference_items": []}
        # Both displayed match scores round to 50.0, while the exact weighted
        # score and combined score favor the first record.
        first = school("B", spark="Yes", transport="No")
        second = school("A", spark="No", transport="Yes")
        ordered = rank_schools(profile, [first, second])
        self.assertEqual([item["school_id"] for item in ordered], ["B", "A"])
        self.assertEqual([item["match_score"] for item in ordered], [50.0, 50.0])
        self.assertEqual(ordered, rank_schools(profile, [first, second]))

    def test_multiple_required_constraints_report_only_individually_actionable_relaxations(self):
        profile = {
            "preferences": {
                "spark_certified": {"value": True, "weight": 1},
                "transport": {"value": True, "weight": 1},
            },
            "preference_items": [
                {"attribute": "spark_certified", "value": True, "importance": "required"},
                {"attribute": "transport", "value": True, "importance": "required"},
            ],
        }
        schools = [school("A", spark="Yes", transport="No"), school("B", spark="No", transport="Yes")]
        self.assertEqual(rank_schools(profile, schools), [])
        self.assertEqual(
            individually_relaxable_required_preferences(profile, schools),
            ["spark_certified", "transport"],
        )


if __name__ == "__main__":
    unittest.main()
