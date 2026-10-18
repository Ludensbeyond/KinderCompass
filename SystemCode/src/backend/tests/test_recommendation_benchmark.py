import json
import unittest
from pathlib import Path

from SystemCode.src.backend.evaluation.benchmark_validation import validate_benchmark
from SystemCode.src.backend.evaluation.recommendation_metrics import grounded_claim_rate, hard_constraint_metrics
from SystemCode.src.backend.evaluation.run_recommendation_evaluation import evaluate_dataset, readable_summary
from SystemCode.src.backend.pipeline.stage1.scorer import rank_schools, score_school
from SystemCode.src.backend.pipeline.stage1.preference_schema import validate_preference_profile


BENCHMARK_DIR = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark"
SYNTHETIC_FIXTURE = Path(__file__).resolve().parents[1] / "evaluation" / "synthetic_fixtures.json"


def empty_benchmark(split="development"):
    return {
        "schema_version": 1,
        "benchmark_id": "unit-test-benchmark",
        "benchmark_version": "1.0.0",
        "dataset_kind": "manual_label_benchmark",
        "split": split,
        "reference_label_status": "not_reviewed",
        "ranking_cases": [],
        "eligibility_fee_claims": [],
        "explanation_claims": [],
        "human_judge_ratings": [],
        "judge_configuration": None,
        "confidence_cases": [],
        "not_applicable_labels": [],
        "label_provenance": [],
    }


class RecommendationBenchmarkTests(unittest.TestCase):
    def test_populated_synthetic_splits_validate_and_are_disjoint(self):
        documents = []
        all_case_ids = set()
        for filename, split, expected_count in (
            ("development.json", "development", 30),
            ("held_out_test.json", "held_out_test", 20),
        ):
            document = json.loads((BENCHMARK_DIR / filename).read_text(encoding="utf-8"))
            self.assertEqual(validate_benchmark(document)["split"], split)
            self.assertEqual(document["dataset_kind"], "synthetic_test_fixture")
            self.assertEqual(document["reference_label_status"], "illustrative_only")
            self.assertEqual(len(document["ranking_cases"]), expected_count)
            case_ids = {case["case_id"] for case in document["ranking_cases"]}
            self.assertEqual(len(case_ids), expected_count)
            self.assertFalse(case_ids & all_case_ids)
            all_case_ids |= case_ids
            for case in document["ranking_cases"]:
                self.assertTrue(case["synthetic"])
                validate_preference_profile(case["profile"])
                self.assertTrue(all(school["synthetic"] for school in case["schools"]))
                self.assertTrue(all(school["school_id"].startswith("SYN-") for school in case["schools"]))
                self.assertIsNone(case.get("reference_order"))
                self.assertEqual(set(case["relevance"]) - {s["school_id"] for s in case["schools"]}, set())
            documents.append(document)
        self.assertEqual(documents[0]["benchmark_id"], documents[1]["benchmark_id"])
        tags = {tag for document in documents for case in document["ranking_cases"] for tag in case["scenario_tags"]}
        self.assertTrue({"required_preference", "distance_context_only", "budget_context_only",
                         "programme_context", "conflicting_preferences", "missing_information",
                         "stale_evidence_input", "zero_stage1_results", "different_relevance_levels"} <= tags)

    def test_synthetic_rankings_and_required_exclusions_follow_production_ranker(self):
        saw_empty_stage1 = False
        for filename in ("development.json", "held_out_test.json"):
            document = json.loads((BENCHMARK_DIR / filename).read_text(encoding="utf-8"))
            report = evaluate_dataset(document)
            self.assertEqual(report["evaluation_status"], "illustrative_only")
            self.assertEqual(report["benchmark_details"]["ranking_scenarios"], len(document["ranking_cases"]))
            generated = {item["case_id"]: item["new_combined_score"]["ranking_ids"]
                         for item in report["ranking_comparison"]}
            for case in document["ranking_cases"]:
                expected = [item["school_id"] for item in rank_schools(
                    case["profile"], case["schools"], limit=len(case["schools"])
                )]
                self.assertEqual(generated[case["case_id"]], expected)
                self.assertEqual(expected, [item["school_id"] for item in rank_schools(
                    case["profile"], case["schools"], limit=len(case["schools"])
                )])
                saw_empty_stage1 = saw_empty_stage1 or not expected
                outcomes = case.get("hard_constraint_outcomes", {})
                self.assertFalse(set(expected) & {school_id for school_id, value in outcomes.items() if value == "fail"})
                required = {
                    (f"language:{item['value']}" if item["attribute"] == "language" else item["attribute"])
                    for item in case["profile"].get("preference_items", [])
                    if item.get("importance") == "required"
                }
                for school in case["schools"]:
                    if school["school_id"] not in outcomes:
                        continue
                    breakdown = score_school(case["profile"], school)["match_breakdown"]
                    required_results = [item["matched"] for item in breakdown if item["attribute"] in required]
                    expected_outcome = (
                        "fail" if False in required_results else
                        "unknown" if not required_results or None in required_results else "pass"
                    )
                    self.assertEqual(outcomes[school["school_id"]], expected_outcome)
        self.assertTrue(saw_empty_stage1)

    def test_synthetic_validator_rejects_unmarked_data_and_fake_provenance(self):
        document = json.loads((BENCHMARK_DIR / "development.json").read_text(encoding="utf-8"))
        document["ranking_cases"][0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "synthetic.*must be true"):
            validate_benchmark(document)
        document = json.loads((BENCHMARK_DIR / "development.json").read_text(encoding="utf-8"))
        document["label_provenance"] = [{"case_id": document["ranking_cases"][0]["case_id"],
            "label_type": "relevance", "label_key": next(iter(document["ranking_cases"][0]["relevance"])),
            "source": "invented", "reference": "invented", "verified_at": "2026-01-01", "reviewer": "synthetic"}]
        with self.assertRaisesRegex(ValueError, "synthetic illustrative labels must not claim source"):
            validate_benchmark(document)

    def test_benchmark_case_reports_identity_split_and_undefined_metrics(self):
        dataset = empty_benchmark("held_out_test")
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a",
            "profile": {"preferences": {}, "preference_items": []},
            "schools": [{"school_id": "school-a", "name": "Recorded name"}],
            "reference_ids": [], "labels_complete": True, "relevance": {},
        }]
        report = evaluate_dataset(dataset)
        self.assertEqual(report["benchmark_details"]["benchmark_id"], "unit-test-benchmark")
        self.assertEqual(report["benchmark_details"]["split"], "held_out_test")
        self.assertEqual(report["evaluation_status"], "manual_labels_not_independently_audited")
        summary = readable_summary(report)
        self.assertIn("benchmark: unit-test-benchmark", summary.lower())
        self.assertIn("split=held_out_test", summary)
        metric = report["quantitative_ranking_evaluation"]["new_combined_score"]["per_case"][0]["metrics"]["ndcg_at_3"]
        self.assertIsNone(metric["value"])
        self.assertEqual(metric["exclusion_reason"], "empty_reference_pool")

    def test_unknown_reference_label_requires_provenance_and_stays_unknown(self):
        dataset = empty_benchmark()
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a",
            "profile": {"preferences": {}, "preference_items": []},
            "schools": [{"school_id": "school-a", "name": "Recorded name"}],
            "hard_constraint_outcomes": {"school-a": "unknown"},
        }]
        with self.assertRaisesRegex(ValueError, "case-a/hard_constraint_outcomes/school-a"):
            validate_benchmark(dataset)
        dataset["label_provenance"] = [{
            "case_id": "case-a", "label_type": "hard_constraint_outcomes", "label_key": "school-a",
            "source": "manually checked source", "reference": "stable-reference",
            "verified_at": "2026-05-01", "reviewer": "reviewer role",
        }]
        report = evaluate_dataset(dataset)
        hard = report["quantitative_ranking_evaluation"]["hard_constraints"]["per_case"][0]
        self.assertEqual(hard["unknown_retained"], 1)
        self.assertEqual(hard["true_negative"], 0)
        self.assertEqual(hard["false_negative"], 0)

    def test_missing_constraint_labels_and_not_applicable_labels_stay_distinct(self):
        metric = hard_constraint_metrics(["unknown", "missing"], ["missing"], {"unknown": "unknown"})
        self.assertEqual(metric["unknown_denominator"], 1)
        self.assertEqual(metric["unlabelled_denominator"], 1)
        self.assertEqual(metric["unlabelled_excluded"], 1)
        grounded = grounded_claim_rate([{
            "claim_id": "na-claim", "claim": "Not applicable", "factual": True,
            "evidence_available": False, "status": "not_applicable",
        }])
        self.assertEqual(grounded["not_applicable"], 1)
        self.assertEqual(grounded["unverifiable"], 0)
        self.assertIsNone(grounded["rate"])

        dataset = empty_benchmark()
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a",
            "profile": {"preferences": {}, "preference_items": []},
            "schools": [
                {"school_id": "unknown-school", "name": "Recorded name"},
                {"school_id": "missing-school", "name": "Recorded name"},
            ],
            "hard_constraint_outcomes": {"unknown-school": "unknown"},
        }]
        dataset["label_provenance"] = [{
            "case_id": "case-a", "label_type": "hard_constraint_outcomes", "label_key": "unknown-school",
            "source": "review record", "reference": "record-id",
            "verified_at": "2026-05-01", "reviewer": "reviewer role",
        }]
        dataset["not_applicable_labels"] = [{
            "case_id": "case-a", "label_type": "eligibility", "label_key": "missing-school",
            "reason": "This evaluation dimension does not apply to this case.",
            "reviewer": "reviewer role", "decided_at": "2026-05-01",
        }]
        report = evaluate_dataset(dataset)
        hard = report["quantitative_ranking_evaluation"]["hard_constraints"]["per_case"][0]
        self.assertEqual(hard["unknown_denominator"], 1)
        self.assertEqual(hard["unlabelled_denominator"], 1)
        self.assertEqual(report["benchmark_details"]["not_applicable_labels"], 1)
        self.assertEqual(report["benchmark_details"]["not_applicable_label_records"][0]["reason"],
                         "This evaluation dimension does not apply to this case.")

    def test_invalid_grade_split_date_and_candidate_reference_are_rejected(self):
        dataset = empty_benchmark("development")
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a",
            "profile": {}, "schools": [{"school_id": "school-a", "name": "Recorded name"}],
            "reference_ids": ["outside"], "labels_complete": False,
            "relevance": {"school-a": 4},
        }]
        with self.assertRaisesRegex(ValueError, "reference_ids.*absent from schools"):
            validate_benchmark(dataset)
        dataset["ranking_cases"][0]["reference_ids"] = ["school-a"]
        with self.assertRaisesRegex(ValueError, "relevance.school-a.*integer from 0 to 3"):
            validate_benchmark(dataset)
        dataset["ranking_cases"][0]["relevance"]["school-a"] = 2
        dataset["label_provenance"] = [{
            "case_id": "case-a", "label_type": "relevance", "label_key": "school-a",
            "source": "reference", "reference": "record", "verified_at": "not-a-date", "reviewer": "role",
        }]
        with self.assertRaisesRegex(ValueError, "verified_at.*valid ISO date"):
            validate_benchmark(dataset)
        dataset["split"] = "test"
        with self.assertRaisesRegex(ValueError, "split.*development.*held_out_test"):
            validate_benchmark(dataset)

    def test_missing_metadata_and_invalid_outcome_are_rejected(self):
        dataset = empty_benchmark()
        del dataset["benchmark_id"]
        with self.assertRaisesRegex(ValueError, "benchmark_id: is required"):
            validate_benchmark(dataset)
        dataset = empty_benchmark()
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a", "profile": {},
            "schools": [{"school_id": "school-a", "name": "Recorded name"}],
            "eligibility": {"school-a": "maybe"},
        }]
        with self.assertRaisesRegex(ValueError, "eligibility.school-a"):
            validate_benchmark(dataset)

    def test_claim_and_explanation_labels_require_per_label_provenance(self):
        dataset = empty_benchmark()
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a", "profile": {},
            "schools": [{"school_id": "school-a", "name": "Recorded name"}],
        }]
        dataset["eligibility_fee_claims"] = [{
            "case_id": "case-a", "claim_id": "fee-claim", "school_id": "school-a",
            "claim_type": "fee", "verified": True, "predicted": 500, "expected": 500,
            "reference": {"source": "source", "reference": "fee-record"},
        }]
        dataset["explanation_claims"] = [{
            "case_id": "case-a", "claim_id": "explanation-claim", "claim": "Atomic factual claim",
            "factual": True, "evidence_available": True,
            "evidence": {"source": "source", "reference": "evidence-record"}, "status": "supported",
        }]
        with self.assertRaisesRegex(ValueError, "label_provenance: missing source/date/reviewer"):
            validate_benchmark(dataset)
        dataset["label_provenance"] = [
            {"case_id": "case-a", "label_type": "eligibility_fee_claims", "label_key": "fee-claim",
             "source": "source", "reference": "fee-record", "verified_at": "2026-05-01", "reviewer": "reviewer"},
            {"case_id": "case-a", "label_type": "explanation_claims", "label_key": "explanation-claim",
             "source": "source", "reference": "evidence-record", "verified_at": "2026-05-01", "reviewer": "reviewer"},
        ]
        report = evaluate_dataset(dataset)
        self.assertEqual(report["eligibility_and_fee_claims"]["overall"]["accuracy"], 1.0)
        self.assertEqual(report["grounded_claims"]["rate"], 1.0)

    def test_verified_factual_claim_requires_reference_and_provenance(self):
        dataset = empty_benchmark()
        dataset["ranking_cases"] = [{
            "case_id": "case-a", "reference_case_id": "case-a", "profile": {}, "schools": [],
        }]
        dataset["eligibility_fee_claims"] = [{
            "case_id": "case-a", "claim_id": "fee-1", "claim_type": "fee",
            "verified": True, "predicted": 600, "expected": 500,
        }]
        with self.assertRaisesRegex(ValueError, r"eligibility_fee_claims\[0\].reference"):
            validate_benchmark(dataset)

    def test_synthetic_fixture_remains_compatible_and_illustrative(self):
        fixture = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))
        report = evaluate_dataset(fixture)
        self.assertEqual(report["evaluation_status"], "illustrative_only")
        self.assertIsNone(report["benchmark_details"]["split"])


if __name__ == "__main__":
    unittest.main()
