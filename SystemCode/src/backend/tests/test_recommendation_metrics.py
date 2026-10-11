import json
import unittest
from pathlib import Path

from SystemCode.src.backend.evaluation.recommendation_metrics import (
    claim_accuracy,
    compare_rankings,
    confidence_completeness_error,
    grounded_claim_rate,
    hard_constraint_metrics,
    kendall_tau_b,
    ndcg_at_k,
    quadratic_weighted_kappa,
)
from SystemCode.src.backend.evaluation.run_recommendation_evaluation import evaluate_dataset


FIXTURE = Path(__file__).resolve().parents[1] / "evaluation" / "synthetic_fixtures.json"


class RecommendationMetricTests(unittest.TestCase):
    def test_fixture_is_explicitly_synthetic_and_compares_same_cases(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["dataset_kind"], "synthetic_test_fixture")
        case = fixture["ranking_cases"][0]
        result = compare_rankings(case["old_order"], case["new_order"], case["relevance"], case["reference_order"])
        self.assertEqual(result["new_combined_score"]["ndcg_at_3"], 1.0)
        self.assertLess(result["old_match_first"]["ndcg_at_3"], 1.0)

    def test_hard_constraint_metrics_keep_unknown_separate(self):
        result = hard_constraint_metrics(["fail", "pass", "unknown"], ["fail", "pass"],
                                         {"fail": "fail", "pass": "pass", "unknown": "unknown"})
        self.assertEqual((result["precision"], result["recall"], result["f1"]), (0.5, 1.0, 2 / 3))
        self.assertEqual(result["unknown_retention_rate"], 1.0)

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
        claims = [{"verified": True, "predicted": True, "expected": True},
                  {"verified": True, "predicted": False, "expected": True}, {"verified": False}]
        self.assertEqual(claim_accuracy(claims), {"accuracy": 0.5, "correct": 1, "incorrect": 1, "unverified": 1, "verified_claims": 2})
        grounded = grounded_claim_rate([
            {"factual": True, "evidence_available": True, "supported": True},
            {"factual": True, "evidence_available": True, "supported": False},
            {"factual": True, "evidence_available": False},
        ])
        self.assertEqual((grounded["rate"], grounded["unverified"]), (0.5, 1))

    def test_claim_accuracy_compares_fees_and_statuses_without_bool_coercion(self):
        result = claim_accuracy([
            {"claim_type": "fee", "verified": True, "predicted": 500, "expected": 450},
            {"claim_type": "fee", "verified": True, "predicted": "450.00", "expected": 450},
            {"claim_type": "eligibility", "verified": True, "predicted": "ineligible", "expected": "eligible"},
            {"claim_type": "eligibility", "verified": True, "predicted": " Eligible ", "expected": "eligible"},
            {"claim_type": "fee", "verified": True, "predicted": None, "expected": 0},
            {"claim_type": "eligibility", "verified": True, "predicted": "", "expected": "eligible"},
            {"claim_type": "fee", "verified": False, "predicted": 300, "expected": 300},
        ])
        self.assertEqual(result["correct"], 2)
        self.assertEqual(result["incorrect"], 2)
        self.assertEqual(result["unverified"], 3)
        self.assertEqual(result["accuracy"], 0.5)

    def test_ordinal_agreement_and_confidence_completeness(self):
        self.assertEqual(quadratic_weighted_kappa([1, 2, 4, 5], [1, 2, 4, 5]), 1.0)
        self.assertIsNone(quadratic_weighted_kappa([], []))
        result = confidence_completeness_error([
            {"total_weight": 4, "known_weight": 2, "reported_confidence": 0.5},
            {"total_weight": 0, "known_weight": 0, "reported_confidence": 1},
        ])
        self.assertEqual(result["mean_absolute_error"], 0.0)
        self.assertIn("not factual correctness", result["interpretation"])

    def test_missing_and_insufficient_labels_are_safe(self):
        self.assertIsNone(hard_constraint_metrics([], [], {})["precision"])
        self.assertIsNone(claim_accuracy([])["accuracy"])
        self.assertIsNone(grounded_claim_rate([])["rate"])
        self.assertIsNone(quadratic_weighted_kappa([3, 3], [3, 3]))

    def test_offline_runner_reports_metrics_without_live_judge(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        report = evaluate_dataset(fixture)
        self.assertEqual(report["dataset_kind"], "synthetic_test_fixture")
        self.assertIn("unfinished", report["ranking_algorithm_comparison_status"])
        self.assertIn("eligibility", report["eligibility_and_fee_claims"]["by_claim_type"])
        self.assertIn("fee", report["eligibility_and_fee_claims"]["by_claim_type"])
        self.assertEqual(report["confidence_completeness"]["mean_absolute_error"], 0.0)


if __name__ == "__main__":
    unittest.main()
