"""Focused offline capture boundary tests; no provider calls or labels."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from capture_dataset import capture, composer_evidence, execution_case, run_dataset


def item(case_id="first"):
    return {"case_id": case_id, "user_input": "What is Montessori?",
            "setup": {"profile": {}, "selected_school_ids": [], "conversation_history": []}}


def payload(facts, ids):
    return {"grounding_facts": facts, "citations": [{"citation_id": cid} for cid in ids]}


def invocation(tool_payload):
    return [{"messages": [{"type": "tool", "content": json.dumps(tool_payload)}]}]


class CaptureTests(unittest.TestCase):
    def test_irrelevant_passage_survives_in_composer_order(self):
        observed = [{"chunk_id": "useful", "text": "Useful."},
                    {"chunk_id": "distractor", "text": "Unrelated."}]
        _, facts, passages = composer_evidence(
            invocation(payload(["Unrelated.", "Useful."], ["useful", "distractor"])), observed)
        self.assertEqual(facts, ["Unrelated.", "Useful."])
        self.assertEqual([p["chunk_id"] for p in passages], ["distractor", "useful"])

    def test_school_provenance_survives(self):
        school = {"chunk_id": "school:1", "text": "School passage.", "school_id": "centre-123",
                  "citation": {"school_id": "centre-123", "url": "https://school.example"}}
        _, _, passages = composer_evidence(
            invocation(payload([school["text"]], [school["chunk_id"]])), [school])
        self.assertEqual(passages, [school])
        self.assertEqual(school["school_id"], "centre-123")

    def test_labels_rejected_and_only_setup_applied(self):
        labelled = {**item(), "reference": "secret reference"}
        with self.assertRaises(ValueError):
            execution_case(labelled)
        setup = item()
        setup["setup"]["profile"] = {"preferences": {"language": "Chinese"}}
        setup["setup"]["selected_school_ids"] = ["centre-123"]
        case = execution_case(setup)
        self.assertEqual(case.message, setup["user_input"])
        self.assertEqual(case.profile, setup["setup"]["profile"])
        self.assertEqual(case.selected_school_ids, ["centre-123"])
        case.profile.clear()
        self.assertTrue(setup["setup"]["profile"])

    def test_fallback_uses_controller_passages_and_retains_provider_failure(self):
        citation = {"chunk_id": "general:1", "evidence_scope": "general", "url": "https://example.org"}
        def fake_runner(service, model_factory):
            def run(case):
                conversation._answer_general_knowledge(case.message, {
                    "chunks": [{"chunk_id": "general:1", "text": "Original controller evidence."}]})
                return SimpleNamespace(
                    agent_response={"question": "Controller answer."}, deterministic_response={},
                    metadata=SimpleNamespace(validation_succeeded=False, fallback_reason="model_error",
                                             model_dump=lambda **kw: {"fallback_reason": "model_error"}))
            return run
        from capture_dataset import conversation
        with patch("capture_dataset.staged_runner", fake_runner), patch.object(
            conversation, "_answer_general_knowledge", return_value=("Controller answer.", [citation])
        ):
            row = capture(object(), item(), object())
        self.assertEqual(row["status"], "fallback")
        self.assertEqual(row["retrieved_contexts"], ["Original controller evidence."])
        self.assertEqual(row["passages"][0]["citation"], citation)
        self.assertEqual(row["execution_error"]["reason"], "model_error")

    def test_case_state_is_fresh_and_failure_retains_denominator(self):
        inputs = [item("first"), item("second"), item("third")]
        originals = deepcopy(inputs)
        states = []
        def execute(value):
            states.append(deepcopy(execution_case(value).profile))
            value["setup"]["profile"]["leak"] = True
            if value["case_id"] == "second":
                raise RuntimeError("sensitive provider details")
            return {"case_id": value["case_id"], "status": "agent", "response": "Actual answer.",
                    "retrieved_contexts": []}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            rows, manifest = run_dataset(inputs, output, {}, execute)
            self.assertEqual(len(output.read_text().splitlines()), 3)
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual((manifest["attempted"], manifest["failed"]), (3, 1))
            self.assertIsNone(rows[1]["response"])
            self.assertNotIn("sensitive", output.read_text())
            self.assertEqual(json.loads(output.with_suffix(".manifest.json").read_text()), manifest)
        self.assertEqual(states, [{}, {}, {}])
        self.assertEqual(inputs, originals)

    def test_unobserved_or_ambiguous_evidence_fails_closed(self):
        with self.assertRaises(ValueError):
            composer_evidence(invocation(payload(["Invented."], ["x"])), [])
        self.assertEqual(composer_evidence([] , []), ([], [], []))

    def test_repeated_retrieval_keeps_repeated_model_contexts(self):
        passage = {"chunk_id": "x", "text": "Repeated evidence."}
        _, facts, passages = composer_evidence(
            invocation(payload([passage["text"], passage["text"]], ["x"])),
            [passage, deepcopy(passage)])
        self.assertEqual(facts, [passage["text"], passage["text"]])
        self.assertEqual(passages, [passage, passage])


if __name__ == "__main__":
    unittest.main()
