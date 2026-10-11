import unittest

from stage1.scorer import rank_schools, score_school


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

    def test_ties_use_ascending_stable_school_id(self):
        profile = {"preferences": {"spark_certified": {"value": True, "weight": 1}}, "preference_items": []}
        ranked = rank_schools(profile, [school("Z", name="Alpha"), school("A", name="Zulu")])
        self.assertEqual([item["school_id"] for item in ranked], ["A", "Z"])

    def test_zero_preferences_have_neutral_scores(self):
        scored = score_school({"preferences": {}, "preference_items": []}, school("NONE"))
        self.assertEqual((scored["match_score"], scored["profile_confidence"], scored["combined_score"]), (100.0, 1.0, 100.0))


if __name__ == "__main__":
    unittest.main()
