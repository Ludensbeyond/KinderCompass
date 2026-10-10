import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from SystemCode.src.backend.scripts.evaluate_llm_first_conversation import score_capture, DATASET, INTEGRITY


class EvaluationScoringTests(unittest.TestCase):
    def test_school_demo_relaxes_completion_but_preserves_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            capture, review, output = [Path(directory) / name for name in ("capture.json", "review.json", "scored.json")]
            dataset = json.loads(DATASET.read_text())
            conversations = [{"case_id": c["case_id"], "turns": [
                {"turn": t["turn"], "result": {"answer_method": "llm_first"}} for t in c["turns"]]
                if c["case_id"] not in INTEGRITY else []} for c in dataset["conversations"]]
            report = {"dataset_id": dataset["dataset_id"], "gates": dataset["gates"],
                      "integrity": {k: {"passed": True} for k in INTEGRITY}, "conversations": conversations}
            capture.write_text(json.dumps(report))
            assessments = {f"{c['case_id']}:{t['turn']}": {
                "task": c["case_id"] not in {"comparison", "conflict", "income_scenario", "school_followup", "closest_missing"},
                "tool_use": True, "state": True, "grounding": True,
                "critical_error": False, "reason": "Synthetic gate fixture."}
                for c in conversations for t in c["turns"]}
            def write_review():
                review.write_text(json.dumps({"capture_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                                              "turns": assessments}))
            write_review()
            self.assertEqual(score_capture(capture, review, output), 2)
            self.assertEqual(score_capture(capture, review, output, evaluation_profile="school-demo"), 0)
            scored = json.loads(output.read_text())
            self.assertEqual(scored["task_completion_rate"], 0.8)
            self.assertEqual(scored["gates"]["task_completion_minimum"], 0.95)
            self.assertEqual(scored["effective_task_completion_minimum"], 0.75)
            self.assertNotIn("closest_missing", scored["required_conversations"])
            assessments["greeting:1"]["critical_error"] = True
            write_review()
            self.assertEqual(score_capture(capture, review, output, evaluation_profile="school-demo"), 2)
            assessments["greeting:1"]["critical_error"] = False
            report["integrity"]["concurrent"]["passed"] = False
            capture.write_text(json.dumps(report))
            write_review()
            self.assertEqual(score_capture(capture, review, output, evaluation_profile="school-demo"), 2)

    def test_review_is_bound_to_capture_and_served_response_alone_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            capture, review, output = [Path(directory) / name for name in ("capture.json", "review.json", "scored.json")]
            dataset = json.loads(DATASET.read_text())
            conversations = [{"case_id": c["case_id"], "turns": [
                {"turn": t["turn"], "result": {"answer_method": "llm_first"}} for t in c["turns"]]
                if c["case_id"] not in INTEGRITY else []} for c in dataset["conversations"]]
            capture.write_text(json.dumps({"dataset_id": dataset["dataset_id"],
                "gates": dataset["gates"], "integrity": {k: {"passed": True} for k in INTEGRITY},
                "conversations": conversations}))
            assessment = {"task": False, "tool_use": True, "state": True,
                          "grounding": True, "critical_error": False, "reason": "Wrong task."}
            review.write_text(json.dumps({"capture_sha256": "wrong", "turns": {f"{c['case_id']}:{t['turn']}": assessment for c in conversations for t in c["turns"]}}))
            with self.assertRaisesRegex(ValueError, "does not match"):
                score_capture(capture, review, output)
            values = json.loads(review.read_text())
            values["capture_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
            review.write_text(json.dumps(values))
            self.assertEqual(score_capture(capture, review, output), 2)
            self.assertFalse(json.loads(output.read_text())["passed"])
            values["turns"] = {}
            review.write_text(json.dumps(values))
            with self.assertRaisesRegex(ValueError, "every captured turn"):
                score_capture(capture, review, output)
