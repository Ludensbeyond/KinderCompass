import unittest

from stage1.graph_evaluation import (
    combine_report,
    evaluate_live,
    evaluate_offline,
    extract_cypher_rels,
    load_labels,
    precision_recall,
    resolve_filters,
)
from stage1.query_builder import build_stage1_query


class GraphEvaluationMetricTests(unittest.TestCase):
    def test_perfect_overlap(self):
        metrics = precision_recall(["a", "b"], ["b", "a"])
        self.assertEqual((metrics["precision"], metrics["recall"], metrics["f1"]), (1.0, 1.0, 1.0))

    def test_empty_sets_are_perfect(self):
        metrics = precision_recall([], [])
        self.assertEqual(metrics["f1"], 1.0)

    def test_false_positives_drop_precision(self):
        metrics = precision_recall(["a", "extra"], ["a"])
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 1.0)

    def test_false_negatives_drop_recall(self):
        metrics = precision_recall(["a"], ["a", "missed"])
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 0.5)

    def test_extract_cypher_rels_preserves_order(self):
        query = "MATCH (p)-[:LOCATED_IN]->(t) MATCH (p)-[:SERVES_LEVEL]->(c) MATCH (p)-[:TEACHES_IN]->(l)"
        self.assertEqual(extract_cypher_rels(query), ["LOCATED_IN", "SERVES_LEVEL", "TEACHES_IN"])


class GraphEvaluationLabelTests(unittest.TestCase):
    def test_label_counts(self):
        labels = load_labels()
        self.assertEqual(len(labels["competency_questions"]), 10)
        self.assertEqual(len(labels["retrieval_cases"]), 20)
        self.assertGreaterEqual(sum(1 for case in labels["retrieval_cases"] if case["hops"] >= 2), 4)

    def test_offline_shape_checks_pass(self):
        report = evaluate_offline()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["competency_questions"]["schema_expressible"], 8)
        self.assertEqual(report["competency_questions"]["coverage"], 0.8)
        self.assertEqual(report["retrieval_shape"]["total"], 20)
        self.assertGreaterEqual(report["retrieval_shape"]["multi_hop"], 4)

    def test_spark_text_is_not_a_certification_match(self):
        labels = load_labels()
        spark = next(case for case in labels["retrieval_cases"] if case["id"] == "spark_preference")
        query, params = build_stage1_query(resolve_filters(spark))
        self.assertNotIn("[:HAS_CERTIFICATION]", query)
        self.assertEqual(params, {})

    def test_required_chinese_from_text_uses_teaches_in(self):
        labels = load_labels()
        case = next(item for item in labels["retrieval_cases"] if item["id"] == "language_chinese_required")
        query, params = build_stage1_query(resolve_filters(case))
        self.assertIn("[:TEACHES_IN]", query)
        self.assertEqual(params["language"], "Chinese")

    def test_gold_cypher_is_independent_of_query_builder(self):
        labels = load_labels()
        case = next(item for item in labels["retrieval_cases"] if item["id"] == "woodlands_nursery_chinese")
        stage_query, _params = build_stage1_query(resolve_filters(case))
        self.assertNotEqual(case["gold_cypher"].strip(), stage_query.strip())
        self.assertIn("[:LOCATED_IN]", case["gold_cypher"])
        self.assertIn("[:SERVES_LEVEL]", case["gold_cypher"])
        self.assertIn("[:TEACHES_IN]", case["gold_cypher"])


class GraphEvaluationLiveStubTests(unittest.TestCase):
    def test_live_scoring_against_independent_gold(self):
        labels = {
            "competency_questions": [],
            "retrieval_cases": [
                {
                    "id": "town_stub",
                    "kind": "graph_hard",
                    "hops": 1,
                    "filters": {"town": "Woodlands"},
                    "expected_rels": ["LOCATED_IN"],
                    "gold_cypher": "GOLD_TOWN",
                    "gold_params": {"town": "Woodlands"},
                    "ablation_cypher": "ABLATION_TOWN",
                    "ablation_params": {"town": "Woodlands"},
                }
            ],
        }

        def run_query(query, params=None):
            if query.startswith("MATCH (p:Preschool) RETURN count"):
                return [{"preschools": 2}]
            if query == "GOLD_TOWN":
                return [{"school_id": "a"}, {"school_id": "b"}]
            if query == "ABLATION_TOWN":
                return [{"school_id": "a"}]
            return [
                {"school_id": "a", "retrieval_path": [{"rel": "LOCATED_IN", "name": "WOODLANDS"}]},
                {"school_id": "b", "retrieval_path": [{"rel": "LOCATED_IN", "name": "WOODLANDS"}]},
            ]

        live = evaluate_live(run_query, labels)
        self.assertTrue(live["passed"])
        self.assertEqual(live["macro"]["f1"], 1.0)
        self.assertTrue(live["cases"][0]["ablation"]["keeps_unknown"])
        self.assertEqual(live["multi_hop_success_rate"], 0.0)

    def test_live_detects_mismatch_against_gold(self):
        labels = {
            "competency_questions": [],
            "retrieval_cases": [
                {
                    "id": "town_stub",
                    "kind": "graph_hard",
                    "hops": 1,
                    "filters": {"town": "Woodlands"},
                    "expected_rels": ["LOCATED_IN"],
                    "gold_cypher": "GOLD_TOWN",
                    "gold_params": {},
                }
            ],
        }

        def run_query(query, params=None):
            if "count(p)" in query:
                return [{"preschools": 2}]
            if query == "GOLD_TOWN":
                return [{"school_id": "a"}]
            return [{"school_id": "a", "retrieval_path": [{"rel": "LOCATED_IN"}]}, {"school_id": "extra", "retrieval_path": [{"rel": "LOCATED_IN"}]}]

        live = evaluate_live(run_query, labels)
        self.assertFalse(live["passed"])
        self.assertEqual(live["failed_ids"], ["town_stub"])
        self.assertEqual(live["cases"][0]["false_positives"], ["extra"])

    def test_combine_report_requires_both_sides_when_live_present(self):
        offline = evaluate_offline()
        report = combine_report(offline, {"passed": False, "preschool_count": 0})
        self.assertTrue(offline["passed"])
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
