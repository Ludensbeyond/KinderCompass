import json
import unittest
from pathlib import Path

from SystemCode.src.backend.evaluation.recommendation_metrics import (
    claim_accuracy,
    compare_rankings,
    confidence_completeness_error,
    aggregate_case_metrics,
    eligibility_violation_metrics,
    evaluate_ranking_case,
    grounded_claim_rate,
    hard_constraint_metrics,
    kendall_tau_b,
    ndcg_at_k,
    paired_rating_agreement,
    quadratic_weighted_kappa,
)
from SystemCode.src.backend.evaluation.run_recommendation_evaluation import evaluate_dataset


FIXTURE = Path(__file__).resolve().parents[1] / "evaluation" / "synthetic_fixtures.json"


class RecommendationMetricTests(unittest.TestCase):
    def test_fixture_is_explicitly_synthetic_and_compares_same_cases(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["dataset_kind"], "synthetic_test_fixture")
        result = evaluate_dataset(fixture)["quantitative_ranking_evaluation"]
        new_ndcg = result["new_combined_score"]["per_case"][0]["metrics"]["ndcg_at_3"]["value"]
        self.assertIsNone(new_ndcg)
        self.assertEqual(result["new_combined_score"]["per_case"][0]["metrics"]["ndcg_at_3"]["exclusion_reason"], "idcg_zero_no_positive_relevance")

    def test_hard_constraint_metrics_keep_unknown_separate(self):
        result = hard_constraint_metrics(["fail", "pass", "unknown"], ["fail", "pass"],
                                         {"fail": "fail", "pass": "pass", "unknown": "unknown"})
        self.assertEqual((result["precision"], result["recall"], result["f1"]), (0.5, 1.0, 2 / 3))
        self.assertEqual(result["unknown_retention_rate"], 1.0)
        self.assertEqual((result["precision_denominator"], result["recall_denominator"]), (2, 1))
        no_predictions = hard_constraint_metrics(["failed"], [], {"failed": "fail"})
        self.assertIsNone(no_predictions["precision"])
        self.assertEqual(no_predictions["recall"], 0.0)
        self.assertEqual(no_predictions["f1"], 0.0)
        with self.assertRaisesRegex(ValueError, "unique family–preschool pairs"):
            hard_constraint_metrics(["same", "same"], [], {})
        with self.assertRaisesRegex(ValueError, "drawn from candidate_ids"):
            hard_constraint_metrics(["one"], ["outside"], {})

    def test_ndcg_empty_unjudged_and_tied_rankings(self):
        self.assertEqual(ndcg_at_k(["a", "b"], {"a": 3, "b": 1}, 2), 1.0)
        self.assertIsNone(ndcg_at_k([], {}, 3))
        self.assertIsNone(kendall_tau_b(["a"], ["a"]))
        self.assertIsNone(kendall_tau_b({"a": 1, "b": 1}, ["a", "b"]))
        self.assertEqual(kendall_tau_b({"a": 1, "b": 1, "c": 3}, {"a": 1, "b": 1, "c": 3}), 1.0)
        tied_comparison = compare_rankings(
            {"a": 1, "b": 1}, {"a": 1, "b": 1},
            {"a": 2, "b": 1}, {"a": 1, "b": 1},
        )
        self.assertIsNone(tied_comparison["new_combined_score"]["kendall_tau_b"])

    def test_claim_metrics_report_unverified_separately(self):
        reference = {"source": "independent fixture", "reference": "case-1"}
        claims = [{"verified": True, "predicted": True, "expected": True, "reference": reference},
                  {"verified": True, "predicted": False, "expected": True, "reference": reference}, {"verified": False}]
        self.assertEqual(claim_accuracy(claims), {"accuracy": 0.5, "correct": 1, "incorrect": 1, "unverified": 1, "verified_claims": 2})
        grounded = grounded_claim_rate([
            {"claim_id": "g", "claim": "claim A", "factual": True, "evidence_available": True, "supported": True,
             "evidence": {"source": "test fixture", "reference": "A"}},
            {"claim_id": "u", "claim": "claim B", "factual": True, "evidence_available": True, "supported": False,
             "evidence": {"source": "test fixture", "reference": "B"}},
            {"factual": True, "evidence_available": False},
            {"claim_id": "c", "claim": "claim C", "factual": True, "evidence_available": True, "status": "contradicted",
             "evidence": {"source": "test fixture", "reference": "C"}},
            {"factual": False, "evidence_available": False},
        ])
        self.assertEqual((grounded["rate"], grounded["unverifiable"], grounded["contradicted"]), (1 / 3, 1, 1))
        self.assertEqual(grounded["non_factual_excluded"], 1)
        self.assertEqual(grounded["per_claim"][0]["evidence"]["source"], "test fixture")
        missing_identity = grounded_claim_rate([{
            "factual": True, "evidence_available": True, "supported": True,
            "evidence": {"source": "test fixture", "reference": "without-id"},
        }])
        self.assertEqual(missing_identity["unverifiable"], 1)

    def test_claim_accuracy_compares_fees_and_statuses_without_bool_coercion(self):
        result = claim_accuracy([
            {"claim_type": "fee", "verified": True, "predicted": 500, "expected": 450, "reference": {"source": "reference", "reference": "fee-1"}},
            {"claim_type": "fee", "verified": True, "predicted": "450.00", "expected": 450, "reference": {"source": "reference", "reference": "fee-2"}},
            {"claim_type": "eligibility", "verified": True, "predicted": "ineligible", "expected": "eligible", "reference": {"source": "reference", "reference": "eligibility-1"}},
            {"claim_type": "eligibility", "verified": True, "predicted": " Eligible ", "expected": "eligible", "reference": {"source": "reference", "reference": "eligibility-2"}},
            {"claim_type": "fee", "verified": True, "predicted": None, "expected": 0, "reference": {"source": "reference", "reference": "fee-3"}},
            {"claim_type": "eligibility", "verified": True, "predicted": "", "expected": "eligible"},
            {"claim_type": "fee", "verified": False, "predicted": 300, "expected": 300},
        ])
        self.assertEqual(result["correct"], 2)
        self.assertEqual(result["incorrect"], 2)
        self.assertEqual(result["unverified"], 3)
        self.assertEqual(result["accuracy"], 0.5)

    def test_claim_numeric_tolerance_units_dates_and_contradictions(self):
        result = claim_accuracy([
            {"claim_type": "fee", "verified": True, "predicted": 450.01, "expected": 450, "tolerance": 0.02, "unit": "SGD/month", "reference": {"source": "reference", "reference": "fee-a"}},
            {"claim_type": "fee", "verified": True, "predicted": 450.01, "expected": 450, "tolerance": 0.02, "unit": "SGD/month", "expected_unit": "SGD", "reference": {"source": "reference", "reference": "fee-b"}},
            {"claim_type": "admission_date", "verified": True, "predicted": "2026-01-01", "expected": "2026-01-01T00:00:00", "reference": {"source": "reference", "reference": "date-a"}},
            {"claim_type": "fee", "verified": True, "predicted": 450.10, "expected": 450, "tolerance": 0.02, "unit": "SGD", "reference": {"source": "reference", "reference": "fee-c"}},
        ])
        self.assertEqual((result["correct"], result["incorrect"], result["unverified"]), (2, 1, 1))

    def test_ordinal_agreement_and_confidence_completeness(self):
        self.assertEqual(quadratic_weighted_kappa([1, 2, 4, 5], [1, 2, 4, 5]), 1.0)
        self.assertIsNone(quadratic_weighted_kappa([], []))
        result = confidence_completeness_error([
            {"total_weight": 4, "known_weight": 2, "reported_confidence": 0.5},
            {"total_weight": 0, "known_weight": 0, "reported_confidence": 1},
        ])
        self.assertEqual(result["mean_absolute_error"], 0.0)
        self.assertIn("not factual correctness", result["interpretation"])

    def test_paired_human_judge_agreement_keeps_samples_and_reports_raw_and_kappa(self):
        result = paired_rating_agreement([
            {"case_id": "one", "dimension": "grounding", "human": 5, "llm_judge": 5},
            {"case_id": "two", "dimension": "grounding", "human": 4, "llm_judge": 3},
        ])
        dimension = result["by_dimension"]["grounding"]
        self.assertEqual(result["sample_size"], 2)
        self.assertEqual(dimension["raw_agreement"], 0.5)
        self.assertEqual(dimension["sample_size"], 2)
        self.assertEqual(len(dimension["paired_ratings"]), 2)
        self.assertEqual(len(dimension["raw_agreement_95_percent_wilson_interval"]), 2)
        with self.assertRaisesRegex(ValueError, "duplicate paired rating"):
            paired_rating_agreement([
                {"case_id": "one", "dimension": "grounding", "human": 5, "llm_judge": 5},
                {"case_id": "one", "dimension": "grounding", "human": 4, "llm_judge": 3},
            ])

    def test_missing_and_insufficient_labels_are_safe(self):
        self.assertIsNone(hard_constraint_metrics([], [], {})["precision"])
        self.assertIsNone(hard_constraint_metrics([], [], {})["f1"])
        self.assertIsNone(claim_accuracy([])["accuracy"])
        self.assertIsNone(grounded_claim_rate([])["rate"])
        self.assertIsNone(quadratic_weighted_kappa([3, 3], [3, 3]))

    def test_offline_runner_reports_metrics_without_live_judge(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        report = evaluate_dataset(fixture)
        self.assertEqual(report["dataset_kind"], "synthetic_test_fixture")
        self.assertIn("generated", report["ranking_algorithm_comparison_status"])
        self.assertIn("eligibility", report["eligibility_and_fee_claims"]["by_claim_type"])
        self.assertIn("fee", report["eligibility_and_fee_claims"]["by_claim_type"])
        self.assertEqual(report["confidence_completeness"]["mean_absolute_error"], 0.0)
        self.assertEqual(report["human_llm_agreement"]["status"], "not_measured_dataset_not_human_reviewed")
        self.assertEqual(report["human_llm_agreement"]["overall"]["quadratic_weighted_cohen_kappa"], None)
        self.assertEqual(report["evaluation_status"], "illustrative_only")

    def test_ranking_metrics_ideal_reversed_tied_and_short_results(self):
        ideal = evaluate_ranking_case(
            ["a", "b", "c"], {"a": 3, "b": 2, "c": 0}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b", "c"], reference_order=["a", "b", "c"],
        )
        reversed_order = evaluate_ranking_case(
            ["c", "b", "a"], {"a": 3, "b": 2, "c": 0}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b", "c"], reference_order=["a", "b", "c"],
        )
        tied = evaluate_ranking_case(
            ["a", "b"], {"a": 2, "b": 2}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b"], reference_order={"a": 1, "b": 1},
        )
        short = evaluate_ranking_case(
            ["a", "b"], {"a": 3, "b": 0}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b"],
        )
        self.assertEqual(ideal["metrics"]["ndcg_at_3"]["value"], 1.0)
        self.assertEqual(ideal["metrics"]["ndcg_at_5"]["value"], 1.0)
        self.assertLess(reversed_order["metrics"]["ndcg_at_3"]["value"], 1.0)
        self.assertEqual(reversed_order["metrics"]["kendall_tau_b"]["value"], -1.0)
        self.assertEqual(ideal["metrics"]["kendall_tau_b"]["value"], 1.0)
        self.assertIsNone(tied["metrics"]["kendall_tau_b"]["value"])
        self.assertEqual(tied["metrics"]["ndcg_at_3"]["value"], 1.0)
        self.assertEqual(short["metrics"]["precision_at_3"]["value"], 0.5)
        self.assertEqual(short["metrics"]["precision_at_3"]["items_in_denominator"], 2)
        self.assertEqual(short["metrics"]["recall_at_3"]["value"], 1.0)
        self.assertEqual(short["metrics"]["ndcg_at_5"]["value"], 1.0)
        relevant_at_four = evaluate_ranking_case(
            ["a", "b", "c", "d"], {"a": 0, "b": 0, "c": 0, "d": 3},
            case_id="x", reference_case_id="x", reference_ids=["a", "b", "c", "d"],
        )
        self.assertEqual(relevant_at_four["metrics"]["mrr"]["value"], 0.25)
        self.assertEqual(relevant_at_four["metrics"]["hit_rate_at_3"]["value"], 0.0)

    def test_empty_zero_gain_and_incomplete_labels_are_explicit(self):
        empty = evaluate_ranking_case([], {}, case_id="x", reference_case_id="x")
        no_relevant = evaluate_ranking_case(
            ["a", "b"], {"a": 0, "b": 0}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b"],
        )
        missing = evaluate_ranking_case(
            ["a", "unjudged"], {"a": 3}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b"], labels_complete=False,
        )
        self.assertEqual(empty["metrics"]["ndcg_at_3"]["exclusion_reason"], "reference_completeness_not_declared")
        self.assertEqual(empty["reference_data_status"], "missing_reference_data")
        self.assertEqual(no_relevant["metrics"]["ndcg_at_3"]["exclusion_reason"], "idcg_zero_no_positive_relevance")
        self.assertEqual(no_relevant["metrics"]["precision_at_3"]["value"], 0.0)
        self.assertEqual(no_relevant["metrics"]["mrr"]["value"], 0.0)
        self.assertEqual(no_relevant["metrics"]["hit_rate_at_3"]["value"], 0.0)
        self.assertIsNone(no_relevant["metrics"]["recall_at_3"]["value"])
        self.assertEqual(missing["metrics"]["precision_at_3"]["exclusion_reason"], "unlabelled_result_in_top_k")
        self.assertEqual(missing["metrics"]["recall_at_3"]["exclusion_reason"], "unlabelled_result_in_top_k")
        with self.assertRaisesRegex(ValueError, "complete reference pool that omits known relevant IDs"):
            evaluate_ranking_case(
                ["a"], {"a": 0, "outside-reference-pool": 3}, case_id="x", reference_case_id="x",
                reference_ids=["a"],
            )

    def test_duplicate_ids_keep_first_occurrence_and_reference_case_must_match(self):
        result = evaluate_ranking_case(
            ["a", "a", "b"], {"a": 3, "b": 0}, case_id="same", reference_case_id="same",
            reference_ids=["a", "b"],
        )
        self.assertEqual(result["ranking_ids"], ["a", "b"])
        self.assertEqual(result["duplicate_result_ids_removed"], 1)
        with self.assertRaisesRegex(ValueError, "does not match reference case"):
            evaluate_ranking_case(["a"], {"a": 3}, case_id="ranking", reference_case_id="other")
        with self.assertRaisesRegex(ValueError, "expected an integer from 0 to 3"):
            evaluate_ranking_case(["a"], {"a": 1.5}, case_id="x", reference_case_id="x")

    def test_case_and_reference_scenario_ids_must_be_explicit_nonempty_and_equal(self):
        for invalid_case_id in (None, "", "   "):
            with self.subTest(case_id=invalid_case_id):
                with self.assertRaisesRegex(ValueError, "case_id must be a non-empty"):
                    evaluate_ranking_case(["a"], {"a": 3}, case_id=invalid_case_id, reference_case_id="x")
        with self.assertRaisesRegex(ValueError, "case_id must be a non-empty"):
            evaluate_ranking_case(["a"], {"a": 3}, reference_case_id="x")
        for invalid_reference_id in (None, "", "   "):
            with self.subTest(reference_case_id=invalid_reference_id):
                with self.assertRaisesRegex(ValueError, "reference_case_id must be a non-empty.*case 'x'"):
                    evaluate_ranking_case(["a"], {"a": 3}, case_id="x", reference_case_id=invalid_reference_id)
        with self.assertRaisesRegex(ValueError, "reference_case_id must be a non-empty"):
            evaluate_ranking_case(["a"], {"a": 3}, case_id="x")

    def test_recall_requires_explicit_reference_completeness(self):
        missing_both = evaluate_ranking_case([], {}, case_id="x", reference_case_id="x")
        missing_completeness = evaluate_ranking_case(
            ["a"], {"a": 3}, case_id="x", reference_case_id="x", labels_complete=None,
        )
        incomplete = evaluate_ranking_case(
            ["a"], {"a": 3}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b"], labels_complete=False,
        )
        explicit_complete_pool = evaluate_ranking_case(
            ["a", "b"], {"a": 3, "b": 0}, case_id="x", reference_case_id="x",
            reference_ids=["a", "b"], labels_complete=True,
        )
        explicit_complete_labels = evaluate_ranking_case(
            ["a"], {"a": 3}, case_id="x", reference_case_id="x", labels_complete=True,
        )
        self.assertIsNone(missing_both["metrics"]["recall_at_3"]["value"])
        self.assertEqual(missing_both["metrics"]["recall_at_3"]["exclusion_reason"], "reference_completeness_not_declared")
        self.assertEqual(missing_both["reference_data_status"], "missing_reference_data")
        self.assertIsNone(missing_completeness["metrics"]["recall_at_3"]["value"])
        self.assertEqual(missing_completeness["metrics"]["recall_at_3"]["exclusion_reason"], "reference_completeness_not_declared")
        self.assertIsNone(incomplete["metrics"]["recall_at_3"]["value"])
        self.assertEqual(incomplete["metrics"]["recall_at_3"]["exclusion_reason"], "incomplete_reference_labels")
        self.assertEqual(explicit_complete_pool["metrics"]["recall_at_3"]["value"], 1.0)
        self.assertEqual(explicit_complete_labels["metrics"]["recall_at_3"]["value"], 1.0)

    def test_empty_reference_pool_is_distinct_from_missing_reference_data(self):
        empty_pool = evaluate_ranking_case(
            [], {}, case_id="empty", reference_case_id="empty", reference_ids=[], labels_complete=True,
        )
        missing_data = evaluate_ranking_case(
            [], {}, case_id="missing", reference_case_id="missing",
        )
        self.assertEqual(empty_pool["reference_data_status"], "empty_reference_pool")
        self.assertEqual(empty_pool["metrics"]["recall_at_3"]["exclusion_reason"], "empty_reference_pool")
        self.assertEqual(missing_data["reference_data_status"], "missing_reference_data")
        self.assertEqual(missing_data["metrics"]["recall_at_3"]["exclusion_reason"], "reference_completeness_not_declared")

    def test_complete_reference_declaration_rejects_missing_or_omitted_relevant_labels(self):
        with self.assertRaisesRegex(ValueError, "labels_complete=true but has no relevance labels"):
            evaluate_ranking_case(
                ["a"], {"a": 3}, case_id="x", reference_case_id="x",
                reference_ids=["a", "b"], labels_complete=True,
            )
        with self.assertRaisesRegex(ValueError, "complete reference pool that omits known relevant IDs"):
            evaluate_ranking_case(
                ["a"], {"a": 0, "b": 3}, case_id="x", reference_case_id="x",
                reference_ids=["a"], labels_complete=True,
            )
        with self.assertRaisesRegex(ValueError, "complete reference pool that omits known relevant IDs"):
            evaluate_ranking_case(
                ["a"], {"a": 0, "b": 3}, case_id="x", reference_case_id="x",
                reference_ids=["a"],
            )

    def test_runner_requires_explicit_case_and_reference_ids(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        case = fixture["ranking_cases"][0]
        missing_case = {**fixture, "ranking_cases": [{key: value for key, value in case.items() if key != "case_id"}]}
        missing_reference = {**fixture, "ranking_cases": [{key: value for key, value in case.items() if key != "reference_case_id"}]}
        mismatch = {**fixture, "ranking_cases": [{**case, "reference_case_id": "another-scenario"}]}
        with self.assertRaisesRegex(ValueError, "invalid case_id"):
            evaluate_dataset(missing_case)
        with self.assertRaisesRegex(ValueError, "synthetic_ordering.*invalid reference_case_id"):
            evaluate_dataset(missing_reference)
        with self.assertRaisesRegex(ValueError, "does not match reference case"):
            evaluate_dataset(mismatch)

    def test_aggregates_count_defined_and_excluded_cases(self):
        valid = evaluate_ranking_case(
            ["a"], {"a": 3}, case_id="a", reference_case_id="a", reference_ids=["a"],
        )
        excluded = evaluate_ranking_case([], {}, case_id="b", reference_case_id="b")
        aggregate = aggregate_case_metrics([valid, excluded])
        self.assertEqual(aggregate["metrics"]["ndcg_at_3"]["denominator"], 1)
        self.assertEqual(aggregate["metrics"]["ndcg_at_3"]["excluded_cases"], 1)

    def test_eligibility_and_hard_constraint_violation_rates_separate_unknown(self):
        eligibility = eligibility_violation_metrics(
            ["no", "yes", "unknown", "unlabelled"],
            {"no": "ineligible", "yes": "eligible", "unknown": "unknown"},
        )
        hard = hard_constraint_metrics(
            ["failed", "passed", "uncertain"], ["passed"],
            {"failed": "fail", "passed": "pass", "uncertain": "unknown"},
        )
        self.assertEqual(eligibility["confirmed_ineligible_recommendation_rate"], 0.5)
        self.assertEqual(eligibility["unknown_denominator"], 4)
        self.assertEqual(eligibility["unlabelled_recommendations"], 1)
        self.assertEqual(hard["confirmed_failure_violation_rate"], 1.0)
        self.assertEqual(hard["unknown_denominator"], 1)

    def test_known_hard_or_age_ineligible_school_cannot_gain_ranking_credit(self):
        result = evaluate_ranking_case(
            ["violator", "suitable"], {"violator": 3, "suitable": 2},
            case_id="family-A", reference_case_id="family-A", reference_ids=["violator", "suitable"],
            reference_order=["suitable", "violator"],
            hard_constraint_outcomes={"violator": "fail", "suitable": "pass"},
            eligibility={"violator": "eligible", "suitable": "eligible"},
        )
        self.assertEqual(result["hard_constraint_or_eligibility_violations_zeroed_for_ranking"], ["violator"])
        self.assertEqual(result["metrics"]["ndcg_at_3"]["value"], ndcg_at_k(["violator", "suitable"], {"violator": 0, "suitable": 2}, 3))
        self.assertEqual(result["metrics"]["recall_at_3"]["value"], 1.0)
        self.assertEqual(result["metrics"]["kendall_tau_b"]["comparable_items"], 1)
        with self.assertRaisesRegex(ValueError, "hard constraint outcomes"):
            evaluate_ranking_case(
                ["x"], {"x": 1}, case_id="c", reference_case_id="c", hard_constraint_outcomes={"x": "probably-fail"},
            )

    def test_runner_reports_individual_constraint_confusion_matrix(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        case = dict(fixture["ranking_cases"][0])
        case["hard_constraint_checks"] = [{
            "constraint": "required_language",
            "candidate_ids": ["A", "B", "C", "D"],
            "excluded_ids": ["A", "B", "C"],
            "outcomes": {"A": "fail", "B": "pass", "C": "unknown", "D": "fail"},
        }]
        fixture = {**fixture, "ranking_cases": [case]}
        report = evaluate_dataset(fixture)["quantitative_ranking_evaluation"]["hard_constraints"]
        by_language = report["per_constraint"]["required_language"]
        self.assertEqual((by_language["per_case"][0]["true_positive"], by_language["per_case"][0]["false_positive"],
                          by_language["per_case"][0]["false_negative"], by_language["per_case"][0]["true_negative"]), (1, 1, 1, 0))
        self.assertEqual(by_language["aggregate"]["f1"], 0.5)

    def test_runner_generates_both_rankings_for_same_scenario_and_labels(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        result = evaluate_dataset(fixture)["quantitative_ranking_evaluation"]
        old = result["old_match_first"]["per_case"][0]
        new = result["new_combined_score"]["per_case"][0]
        self.assertEqual(old["case_id"], new["case_id"])
        self.assertEqual(old["ranking_ids"][0], "S1")
        self.assertEqual(new["ranking_ids"][0], "S2")
        self.assertEqual(result["old_match_first"]["aggregate"]["case_count"], 1)
        self.assertEqual(result["new_combined_score"]["aggregate"]["case_count"], 1)
        self.assertEqual(result["eligibility"]["per_case"][0]["unknown"], 1)
        self.assertIsNone(evaluate_dataset(fixture)["llm_judge_explanation_quality"]["scores"])
        judge = {"evaluation_type": "llm_judge", "summary": {"mean_overall": 4.0}}
        combined = evaluate_dataset(fixture, judge_report=judge)
        self.assertEqual(combined["llm_judge_explanation_quality"]["scores"], judge)
        self.assertNotIn("mean_overall", combined["quantitative_ranking_evaluation"])


if __name__ == "__main__":
    unittest.main()
