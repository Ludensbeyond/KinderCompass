import unittest

from pydantic import ValidationError

from SystemCode.src.backend.evaluation.benchmark_generation import (
    ScenarioBatch, build_generated_dataset, evaluate_frozen_dataset,
    snapshot_school_records,
)


def proposal(ids):
    return {
        "scenario": "A family prioritises Chinese language and full day care.",
        "preference_items": [
            {"attribute": "language", "value": "Chinese", "importance": "required"},
            {"attribute": "full_day", "value": "true", "importance": "preferred"},
        ],
        "candidate_school_ids": ids,
        "dob": "2022-01-01", "admission_date": "2026-01-01",
        "gross_household_income": 5000, "citizenship": "SC",
        "programme_type": "full_day", "working_hours_per_month": 56,
        "household_size": 4, "non_earning_dependants": 1,
        "special_approval": False,
    }


def school(school_id, language, hours):
    return {
        "school_id": school_id, "name": "A real recorded centre",
        "care_levels": ["Nursery (4 yrs old)"],
        "second_languages_offered": language, "weekday_full_day": hours,
        "base_fee": 900, "services_menu": [{
            "class_of_licence": "Child Care Centre",
            "levels_offered": "Nursery (4 yrs old)", "type_of_service": "Full Day",
            "type_of_citizenship": "SC", "fees": 900,
        }],
    }


class BenchmarkGenerationTests(unittest.TestCase):
    def test_structured_output_rejects_extra_fields(self):
        case = proposal(["school-a", "school-b"])
        case["expected_ranking"] = ["school-a"]
        with self.assertRaises(ValidationError):
            ScenarioBatch.model_validate({"cases": [case]})

    def test_snapshot_requires_overlapping_real_school_ids_and_preserves_null(self):
        graph = [{"school_id": "school-a", "name": "Recorded", "pedagogy": None}]
        catalogue = [{"school_id": "school-a", "pedagogy": "Montessori", "services_menu": []}]
        frozen = snapshot_school_records(graph, catalogue)
        self.assertIsNone(frozen[0]["pedagogy"])
        self.assertEqual(frozen[0]["services_menu"], [])
        with self.assertRaisesRegex(ValueError, "absent from processed catalogue"):
            snapshot_school_records(graph, [])

    def test_fabricated_school_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absent from the frozen snapshot"):
            build_generated_dataset(
                {"cases": [proposal(["school-a", "invented-school"])]},
                split="development", seed=7,
                school_snapshot=[school("school-a", "Chinese", True)],
                snapshot_version="snapshot", catalogue_version="catalogue",
                policy_version="policy", model="test-model", generation_settings={},
            )

    def test_hard_constraint_labels_are_rule_derived_and_relevance_is_unlabelled(self):
        result = build_generated_dataset(
            {"cases": [proposal(["school-a", "school-b"])]},
            split="development", seed=7,
            school_snapshot=[school("school-a", "Chinese", True), school("school-b", None, None)],
            snapshot_version="snapshot", catalogue_version="catalogue",
            policy_version="policy", model="test-model", generation_settings={},
        )
        case = result["ranking_cases"][0]
        self.assertEqual(case["hard_constraint_outcomes"], {"school-a": "pass", "school-b": "unknown"})
        self.assertEqual(case["relevance"], {})
        self.assertEqual(case["llm_proposed_labels"], [])
        self.assertEqual(case["label_status"], "no_independent_relevance_labels")
        self.assertIn("stage2_eligibility_and_fee", case["predicted"])

    def test_duplicate_scenarios_are_rejected(self):
        case = proposal(["school-a", "school-b"])
        with self.assertRaisesRegex(ValueError, "Duplicate generated scenario"):
            build_generated_dataset(
                {"cases": [case, case]}, split="held_out_test", seed=8,
                school_snapshot=[school("school-a", "Chinese", True), school("school-b", "Malay", False)],
                snapshot_version="snapshot", catalogue_version="catalogue",
                policy_version="policy", model="test-model", generation_settings={},
            )

    def test_frozen_evaluation_is_offline_and_reports_no_relevance_score(self):
        dataset = build_generated_dataset(
            {"cases": [proposal(["school-a", "school-b"])]},
            split="development", seed=7,
            school_snapshot=[school("school-a", "Chinese", True), school("school-b", "Malay", False)],
            snapshot_version="snapshot", catalogue_version="catalogue",
            policy_version="policy", model="test-model", generation_settings={},
        )
        report = evaluate_frozen_dataset(dataset)
        self.assertEqual(report["case_count"], 1)
        self.assertFalse(report["retrieval_evaluated"])
        self.assertFalse(report["relevance_evaluated"])
        self.assertIsNone(report["cases"][0]["independent_relevance_metrics"])
        broken = {**dataset, "ranking_cases": [{
            **dataset["ranking_cases"][0], "candidate_school_ids": ["outside"],
        }]}
        with self.assertRaisesRegex(ValueError, "candidate IDs do not match"):
            evaluate_frozen_dataset(broken)


if __name__ == "__main__":
    unittest.main()
