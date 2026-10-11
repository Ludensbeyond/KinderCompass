import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from SystemCode.src.backend.evaluation.llm_judge import (
    JUDGE_SYSTEM_PROMPT,
    RUBRIC_DIMENSIONS,
    JudgeDisabledError,
    RecommendationJudgeDataset,
    RecommendationJudgeResult,
    call_openai_judge,
    evaluate_recommendation_judge,
    recommendation_judge_enabled,
)


DATASET_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "judge_cases.json"


def result_for(case_id, *, score=4, critical_failures=None, unsupported=None):
    ratings = {
        dimension: {
            "applicable": True,
            "score": score,
            "rationale": f"Evidence-based {dimension} assessment.",
        }
        for dimension in RUBRIC_DIMENSIONS
    }
    return {
        "case_id": case_id,
        "ratings": ratings,
        "unsupported_factual_claims": unsupported or [],
        "critical_failures": critical_failures or [],
        "overall_assessment": "mixed" if critical_failures else "strong",
        "overall_rationale": "The assessment uses only the supplied example evidence.",
        "requires_human_review": bool(critical_failures),
    }


class RecommendationLLMJudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    def test_synthetic_dataset_is_versioned_and_ids_are_stable(self):
        dataset = RecommendationJudgeDataset.model_validate(self.dataset)
        self.assertEqual(dataset.dataset_kind, "synthetic_unreviewed")
        self.assertEqual(dataset.dataset_version, "1.0.0")
        self.assertEqual(len({case.case_id for case in dataset.cases}), len(dataset.cases))
        self.assertFalse(any(case.human_ratings for case in dataset.cases))

    def test_valid_judge_output_is_accepted(self):
        parsed = RecommendationJudgeResult.model_validate(result_for("rec_eval_001"))
        self.assertEqual(parsed.case_id, "rec_eval_001")
        self.assertEqual(parsed.ratings.evidence_grounding.score, 4)

    def test_missing_dimensions_and_out_of_range_scores_are_rejected(self):
        missing = result_for("rec_eval_001")
        del missing["ratings"]["evidence_grounding"]
        with self.assertRaises(ValidationError):
            RecommendationJudgeResult.model_validate(missing)

        out_of_range = result_for("rec_eval_001", score=6)
        with self.assertRaises(ValidationError):
            RecommendationJudgeResult.model_validate(out_of_range)

    def test_applicable_dimension_cannot_omit_score(self):
        payload = result_for("rec_eval_001")
        payload["ratings"]["preference_alignment"]["score"] = None
        with self.assertRaises(ValidationError):
            RecommendationJudgeResult.model_validate(payload)

    def test_not_applicable_dimension_requires_explicit_null_score(self):
        payload = result_for("rec_eval_001")
        payload["ratings"]["ranking_justification"] = {
            "applicable": False,
            "rationale": "Only one school was recommended, so no ranking comparison was requested.",
        }
        with self.assertRaises(ValidationError):
            RecommendationJudgeResult.model_validate(payload)

        payload["ratings"]["ranking_justification"]["score"] = None
        parsed = RecommendationJudgeResult.model_validate(payload)
        self.assertFalse(parsed.ratings.ranking_justification.applicable)

    def test_unsupported_claim_is_recorded_with_evidence_comparison(self):
        unsupported = [{
            "claim": "The school has a swimming pool.",
            "evidence_comparison": "The supplied catalogue evidence mentions pedagogy only and says nothing about a pool.",
        }]
        parsed = RecommendationJudgeResult.model_validate(
            result_for("rec_eval_009", unsupported=unsupported)
        )
        self.assertEqual(parsed.unsupported_factual_claims[0].claim, unsupported[0]["claim"])

    def test_critical_eligibility_failures_require_human_review(self):
        failure = [{
            "code": "eligibility_misrepresentation",
            "rationale": "The supplied result is explicitly ineligible, but the answer calls it eligible.",
        }]
        parsed = RecommendationJudgeResult.model_validate(
            result_for("rec_eval_002", critical_failures=failure)
        )
        self.assertEqual(parsed.critical_failures[0].code, "eligibility_misrepresentation")
        self.assertTrue(parsed.requires_human_review)

        malformed = result_for("rec_eval_003", critical_failures=failure)
        malformed["requires_human_review"] = False
        with self.assertRaises(ValidationError):
            RecommendationJudgeResult.model_validate(malformed)

    def test_judge_output_must_match_the_input_case_id(self):
        report = evaluate_recommendation_judge(
            {**self.dataset, "cases": [self.dataset["cases"][0]]},
            lambda _case: result_for("rec_eval_003"),
            repeats=1,
        )
        self.assertEqual(report["summary"]["invalid_or_failed_runs"], 1)
        self.assertEqual(report["cases"][0]["case_id"], "rec_eval_001")
        self.assertEqual(report["cases"][0]["runs"][0]["error_type"], "ValueError")
        self.assertTrue(report["cases"][0]["requires_human_review"])

    def test_ineligible_and_unknown_cases_are_explicit_judge_inputs(self):
        ineligible = next(case for case in self.dataset["cases"] if case["case_id"] == "rec_eval_002")
        unknown = next(case for case in self.dataset["cases"] if case["case_id"] == "rec_eval_003")
        missing_family = next(case for case in self.dataset["cases"] if case["case_id"] == "rec_eval_004")
        self.assertIs(ineligible["candidates"][0]["eligible"], False)
        self.assertIsNone(unknown["candidates"][0]["eligible"])
        self.assertIs(missing_family["family_details_available"], False)

        cases = [ineligible, unknown]
        unsafe_dataset = {**self.dataset, "cases": cases}

        def unsafe_eligibility_judgement(case):
            return result_for(case["case_id"], critical_failures=[{
                "code": "eligibility_misrepresentation",
                "rationale": "The response calls a false or unverified eligibility result confirmed.",
            }])

        report = evaluate_recommendation_judge(unsafe_dataset, unsafe_eligibility_judgement, repeats=1)
        self.assertEqual(report["summary"]["critical_failure_count"], 2)
        self.assertTrue(all(item["requires_human_review"] for item in report["cases"]))

    def test_provider_timeout_is_reported_as_invalid_not_a_pass(self):
        dataset = {**self.dataset, "cases": [self.dataset["cases"][0]]}

        def timeout(_case):
            raise TimeoutError

        report = evaluate_recommendation_judge(dataset, timeout, repeats=2)
        self.assertEqual(report["summary"]["invalid_or_failed_runs"], 2)
        self.assertEqual(report["summary"]["valid_runs"], 0)
        self.assertEqual(report["evaluation_status"], "no_valid_judge_results")
        self.assertEqual(report["cases"][0]["runs"][0]["error_type"], "TimeoutError")

    def test_repeatability_and_aggregation_are_reported(self):
        dataset = {**self.dataset, "cases": [self.dataset["cases"][0]]}
        scores = iter((3, 5))
        report = evaluate_recommendation_judge(
            dataset, lambda case: result_for(case["case_id"], score=next(scores)), repeats=2,
        )
        self.assertEqual(report["summary"]["valid_runs"], 2)
        self.assertEqual(
            report["summary"]["dimension_scores"]["preference_alignment"]["mean_score"], 4,
        )
        self.assertEqual(
            report["cases"][0]["repeat_rating_and_critical_failure_agreement"], 0,
        )

    def test_absent_human_labels_are_reported_without_fabricated_agreement(self):
        dataset = {**self.dataset, "cases": [self.dataset["cases"][0]]}
        report = evaluate_recommendation_judge(
            dataset, lambda case: result_for(case["case_id"]), repeats=1,
        )
        self.assertFalse(report["summary"]["human_labels_present"])
        self.assertEqual(
            report["summary"]["human_agreement"]["preference_alignment"],
            {"quadratic_weighted_kappa": None, "paired_ratings": 0},
        )

    def test_repeat_runs_count_once_per_case_for_human_agreement(self):
        case = copy.deepcopy(self.dataset["cases"][0])
        case["human_ratings"] = {"preference_alignment": 4}
        dataset = {
            **self.dataset,
            "dataset_kind": "human_reviewed",
            "cases": [case],
        }
        report = evaluate_recommendation_judge(
            dataset, lambda item: result_for(item["case_id"], score=4), repeats=3,
        )
        agreement = report["summary"]["human_agreement"]["preference_alignment"]
        self.assertEqual(agreement["paired_ratings"], 1)
        self.assertEqual(agreement["quadratic_weighted_kappa"], None)

    def test_human_labels_are_not_sent_to_the_provider(self):
        case = copy.deepcopy(self.dataset["cases"][0])
        case["human_ratings"] = {"preference_alignment": 5}
        captured = {}

        class FakeResponses:
            def parse(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(output_parsed=result_for(case["case_id"]))

        fake_client = SimpleNamespace(responses=FakeResponses())
        call_openai_judge(
            case,
            environ={"OPENAI_RECOMMENDATION_JUDGE_ENABLED": "true"},
            client=fake_client,
        )
        self.assertNotIn("human_ratings", json.loads(captured["input"]))
        self.assertNotIn("case_type", json.loads(captured["input"]))
        self.assertNotIn("safety_expectations", json.loads(captured["input"]))
        self.assertIs(captured["store"], False)
        self.assertIn("supplied", captured["instructions"])

    def test_live_provider_requires_explicit_opt_in(self):
        self.assertFalse(recommendation_judge_enabled({}))
        with self.assertRaises(JudgeDisabledError):
            call_openai_judge(self.dataset["cases"][0], environ={}, client=Mock())

    def test_human_reference_scores_reject_booleans_and_out_of_range_values(self):
        case = copy.deepcopy(self.dataset["cases"][0])
        case["human_ratings"] = {"preference_alignment": True}
        invalid_dataset = {
            **self.dataset,
            "dataset_kind": "human_reviewed",
            "cases": [case],
        }
        with self.assertRaises(ValidationError):
            RecommendationJudgeDataset.model_validate(invalid_dataset)

    def test_judge_does_not_mutate_dataset_or_production_rankings(self):
        from stage1.nlp_mapper import map_text_to_filters
        from stage1.scorer import rank_schools

        profile = map_text_to_filters("SPARK is preferred")
        schools = [
            {"school_id": "RANK-A", "spark_certified": "Yes"},
            {"school_id": "RANK-B", "spark_certified": "No"},
        ]
        before_ranked = rank_schools(profile, copy.deepcopy(schools))
        before_dataset = copy.deepcopy(self.dataset)
        evaluate_recommendation_judge(
            self.dataset, lambda case: result_for(case["case_id"]), repeats=1,
        )
        after_ranked = rank_schools(profile, copy.deepcopy(schools))
        self.assertEqual(before_ranked, after_ranked)
        self.assertEqual(self.dataset, before_dataset)


if __name__ == "__main__":
    unittest.main()
