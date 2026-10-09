"""Offline failure/reporting tests; judge outcomes are controlled, no API calls."""
import json
from pathlib import Path
import tempfile
import unittest

from score import METRICS, apply_reviews, inspect_runs, report_counts, score_results, write_reports


def case(cid, evaluation="ragas"):
    return {"case_id": cid, "evaluation": evaluation, "user_input": "Question?",
            "reference": "Expected fact.", "checks": ["Does not invent."]}


def run(cid, **extra):
    return {"case_id": cid, "response": "Actual fact.", "retrieved_contexts": ["Evidence."],
            "status": "agent", **extra}


class ScoreTests(unittest.TestCase):
    def test_full_denominator_and_failures_never_reach_judge(self):
        cases = [case(str(i)) for i in range(6)]
        runs = [run("0"), run("1", status="fallback", execution_error={"type": "Timeout"}),
                run("2", response=""), run("3", retrieved_contexts=[]),
                run("4", retrieved_contexts=[None])]
        results, mapping = inspect_runs(cases, runs)
        calls = []
        score_results(cases, results, mapping, lambda row, metric: calls.append(metric) or 1)
        apply_reviews(cases, results, {})
        counts = report_counts(results, len(runs))
        self.assertEqual((counts["expected"], counts["attempted"], counts["executed"],
                          counts["scored"], counts["failed"]), (6, 5, 3, 1, 5))
        self.assertEqual(calls, list(METRICS))
        self.assertEqual([r["status"] for r in results], ["scored", "execution_failed",
                         "invalid_capture", "empty_evidence", "invalid_capture", "missing_capture"])

    def test_metric_errors_and_undefined_preserve_partial_scores(self):
        cases = [case("a"), case("b")]
        results, mapping = inspect_runs(cases, [run("a"), run("b")])
        def judge(row, metric):
            if metric == METRICS[1]:
                return float("nan")
            if metric == METRICS[2]:
                raise TimeoutError("secret should not escape")
            return .75
        score_results(cases, results, mapping, judge)
        apply_reviews(cases, results, {})
        self.assertEqual(report_counts(results, 2)["undefined"], 2)
        self.assertEqual(results[0]["status"], "scoring_failed")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scores.csv"
            write_reports(output, {"cases": results}, cases, mapping)
            raw = output.with_suffix(".report.json").read_text()
            self.assertNotIn("secret", raw)
            self.assertNotIn("NaN", raw)
            self.assertEqual(json.loads(raw)["cases"][0]["metrics"][METRICS[0]]["value"], .75)

    def test_undefined_only_and_out_of_range(self):
        cases = [case("a")]
        for value, expected in [(float("nan"), "undefined"), (1.5, "scoring_failed")]:
            results, mapping = inspect_runs(cases, [run("a")])
            score_results(cases, results, mapping, lambda row, metric: value)
            self.assertEqual(results[0]["status"], expected)

    def test_reviews_cover_every_check_and_completeness(self):
        cases = [case("a"), case("b", "behaviour")]
        results, _ = inspect_runs(cases, [run("a"), run("b", retrieved_contexts=[])])
        with self.assertRaises(ValueError):
            apply_reviews(cases, results, {"b": {"checks": []}})
        reviews = {"a": {"pass": False, "reason": "Missing reference fact."},
                   "b": {"checks": [{"check": "Does not invent.", "pass": True,
                                      "reason": "Declines the requested invention."}]}}
        apply_reviews(cases, results, reviews)
        counts = report_counts(results, 2)
        self.assertEqual(counts["behaviour_reviewed"], 1)
        self.assertEqual(counts["answer_completeness_reviewed"], 1)

    def test_successful_fallback_keeps_origin_and_never_receives_labels_as_contexts(self):
        cases = [case("a")]
        cases[0]["reference_contexts"] = ["Label-only passage."]
        results, mapping = inspect_runs(cases, [run("a", status="fallback")])
        def judge(row, metric):
            self.assertEqual(row["retrieved_contexts"], ["Evidence."])
            self.assertEqual(row["response"], "Actual fact.")
            return 1
        score_results(cases, results, mapping, judge)
        self.assertEqual(results[0]["status"], "scored")
        self.assertEqual(results[0]["agent_status"], "fallback")

    def test_duplicate_unknown_and_missing_ids(self):
        with self.assertRaises(ValueError):
            inspect_runs([case("a"), case("a")], [])
        with self.assertRaises(ValueError):
            inspect_runs([case("a")], [run("a"), run("a")])
        with self.assertRaises(ValueError):
            inspect_runs([case("a")], [run("unknown")])
        results, _ = inspect_runs([case("a")], [])
        self.assertEqual(results[0]["status"], "missing_capture")


if __name__ == "__main__":
    unittest.main()
