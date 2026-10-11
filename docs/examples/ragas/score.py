"""Score captured agent answers; --validate-only makes no model calls."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import math
import json
import os
from pathlib import Path


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prepare(cases, runs):
    case_map = {case["case_id"]: case for case in cases}
    if len(case_map) != len(cases):
        raise ValueError("Duplicate case IDs in the dataset")
    seen = set()
    rows = []
    ids = []
    behaviour = []
    for run in runs:
        case_id = run["case_id"]
        if case_id in seen:
            raise ValueError(f"Duplicate run: {case_id}")
        seen.add(case_id)
        case = case_map[case_id]
        response = run["response"]
        contexts = run["retrieved_contexts"]
        if not isinstance(response, str) or not response.strip():
            raise ValueError(f"{case_id}: response must contain the actual agent answer")
        if not isinstance(contexts, list) or any(
            not isinstance(text, str) or not text.strip() for text in contexts
        ):
            raise ValueError(f"{case_id}: retrieved_contexts must be a list of passage texts")
        if case["evaluation"] == "behaviour":
            behaviour.append({
                "case_id": case_id,
                "response": response,
                "retrieved_contexts": contexts,
                "checks": case["checks"],
            })
            continue
        rows.append({
            "user_input": case["user_input"],
            "response": response,
            "retrieved_contexts": contexts,
            "reference": case["reference"],
        })
        ids.append(case_id)
    if seen != set(case_map):
        raise ValueError(f"Missing runs: {sorted(set(case_map) - seen)}")
    return rows, ids, behaviour



METRICS = ("faithfulness", "llm_context_precision_with_reference", "context_recall")


def inspect_runs(cases, runs):
    """Retain the full dataset denominator, including absent and invalid captures."""
    case_map = {case["case_id"]: case for case in cases}
    if len(case_map) != len(cases):
        raise ValueError("Duplicate case IDs in the dataset")
    run_map = {}
    for run in runs:
        case_id = run["case_id"]
        if case_id not in case_map:
            raise ValueError(f"Unknown run: {case_id}")
        if case_id in run_map:
            raise ValueError(f"Duplicate run: {case_id}")
        run_map[case_id] = run
    results = []
    for case in cases:
        run = run_map.get(case["case_id"])
        entry = {"case_id": case["case_id"], "evaluation": case["evaluation"],
                 "category": case.get("category"), "executed": False,
                 "agent_status": run.get("status", "unrecorded") if run else None,
                 "status": "ready", "reason": None, "metrics": {}}
        if run is None:
            entry.update(status="missing_capture", reason="No capture for this case")
        elif run.get("execution_error") or run.get("status") == "execution_error":
            entry.update(status="execution_failed", reason="Agent/provider/tool execution failed",
                         execution_error=run.get("execution_error"))
        elif not isinstance(run.get("response"), str) or not run["response"].strip():
            entry.update(status="invalid_capture", reason="Empty or invalid actual answer")
        else:
            entry["executed"] = True
            contexts = run.get("retrieved_contexts")
            if not isinstance(contexts, list) or any(
                not isinstance(text, str) or not text.strip() for text in contexts
            ):
                entry.update(status="invalid_capture", reason="Invalid retrieved passage texts")
            elif case["evaluation"] == "behaviour":
                entry["status"] = "behaviour_review"
            elif not contexts:
                entry.update(status="empty_evidence", reason="No retrieved evidence; metrics not called")
        results.append(entry)
    return results, run_map


def apply_reviews(cases, results, reviews):
    """Validate explicit, case-keyed reviews; verdicts never come from score thresholds."""
    case_map = {case["case_id"]: case for case in cases}
    if set(reviews) - set(case_map):
        raise ValueError("Review contains unknown case IDs")
    for entry in results:
        case = case_map[entry["case_id"]]
        review = reviews.get(entry["case_id"])
        if review is None:
            entry["review"] = {"status": "pending"}
            continue
        if not entry["executed"] or entry["status"] == "invalid_capture":
            raise ValueError(f"Cannot review invalid execution: {entry['case_id']}")
        if case["evaluation"] == "behaviour":
            checks = review.get("checks", [])
            if [check.get("check") for check in checks] != case["checks"]:
                raise ValueError(f"Review must cover every check in order: {entry['case_id']}")
            verdicts = checks
        else:
            verdicts = [review]
        if any(type(v.get("pass")) is not bool or not isinstance(v.get("reason"), str)
               or not v["reason"].strip() for v in verdicts):
            raise ValueError(f"Review needs pass/fail and a reason: {entry['case_id']}")
        entry["review"] = {**review, "status": "complete"}


def score_results(cases, results, run_map, score_metric):
    for case, entry in zip(cases, results):
        if entry["status"] != "ready":
            continue
        run = run_map[case["case_id"]]
        row = {"user_input": case["user_input"], "response": run["response"],
               "retrieved_contexts": run["retrieved_contexts"], "reference": case["reference"]}
        for metric in METRICS:
            try:
                value = float(score_metric(row, metric))
                if not math.isfinite(value):
                    outcome = {"status": "undefined", "value": None,
                               "reason": "Judge returned a non-finite score"}
                elif not 0 <= value <= 1:
                    outcome = {"status": "scoring_failed", "value": None,
                               "reason": "Judge returned a score outside [0, 1]"}
                else:
                    outcome = {"status": "scored", "value": value}
            except Exception as error:
                # Error type only: exception messages may contain credentials or raw prompts.
                outcome = {"status": "scoring_failed", "value": None,
                           "reason": type(error).__name__}
            entry["metrics"][metric] = outcome
        states = {outcome["status"] for outcome in entry["metrics"].values()}
        entry["status"] = ("scoring_failed" if "scoring_failed" in states else
                           "undefined" if "undefined" in states else "scored")
        if entry["status"] != "scored":
            entry["reason"] = "See individual metric outcomes; partial scores retained"


def report_counts(results, attempted):
    return {"expected": len(results), "attempted": attempted,
            "executed": sum(e["executed"] for e in results),
            "scored": sum(e["status"] == "scored" for e in results),
            "failed": sum(e["status"] in {"missing_capture", "execution_failed", "invalid_capture",
                                          "empty_evidence", "scoring_failed"} for e in results),
            "undefined": sum(any(m["status"] == "undefined" for m in e["metrics"].values())
                             for e in results),
            "execution_failed": sum(e["status"] == "execution_failed" for e in results),
            "scoring_failed": sum(e["status"] == "scoring_failed" for e in results),
            "behaviour_reviewed": sum(e["evaluation"] == "behaviour" and
                                      e["review"]["status"] == "complete" for e in results),
            "answer_completeness_reviewed": sum(e["evaluation"] == "ragas" and
                                               e["review"]["status"] == "complete" for e in results)}


def write_reports(output, report, cases, run_map):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "status", "reason", *METRICS])
        writer.writeheader()
        for entry in report["cases"]:
            writer.writerow({"case_id": entry["case_id"], "status": entry["status"],
                             "reason": entry["reason"],
                             **{m: entry["metrics"].get(m, {}).get("value") for m in METRICS}})
    output.with_suffix(".report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    behaviour = [{"case_id": case["case_id"],
                  "response": run_map.get(case["case_id"], {}).get("response"),
                  "checks": case["checks"], "review": entry["review"], "status": entry["status"]}
                 for case, entry in zip(cases, report["cases"]) if case["evaluation"] == "behaviour"]
    output.with_suffix(".behaviour.json").write_text(json.dumps(behaviour, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.jsonl"))
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("/tmp/kindercompass-ragas.csv"))
    parser.add_argument("--judge-model", help="Model available to your evaluation provider")
    parser.add_argument("--env-file", type=Path, help="Read only OPENAI_API_KEY; exported key takes precedence")
    parser.add_argument("--reviews", type=Path, help="Case-keyed JSON with explicit behaviour/completeness reviews")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    cases, runs = read_jsonl(args.cases), read_jsonl(args.runs)
    if args.validate_only:
        if any(r.get("execution_error") or r.get("status") == "execution_error" for r in runs):
            raise ValueError("Capture includes execution failures; use scoring for a failure-aware report")
        rows, _, behaviour = prepare(cases, runs)
        print(f"Validated {len(rows)} RAGAS cases and {len(behaviour)} behaviour cases.")
        return
    if not args.judge_model:
        parser.error("--judge-model is required when scoring")
    results, run_map = inspect_runs(cases, runs)
    apply_reviews(cases, results, json.loads(args.reviews.read_text()) if args.reviews else {})
    os.environ.update(LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false", RAGAS_DO_NOT_TRACK="true")
    if args.env_file and not os.getenv("OPENAI_API_KEY"):
        from dotenv import dotenv_values
        key = dotenv_values(args.env_file).get("OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY or supply --env-file for the evaluation judge")

    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall
    from ragas.run_config import RunConfig

    judge = LangchainLLMWrapper(ChatOpenAI(model=args.judge_model, temperature=0, timeout=60, max_retries=1))
    metrics = dict(zip(METRICS, [Faithfulness(), LLMContextPrecisionWithReference(), LLMContextRecall()]))
    def score_metric(row, metric):
        result = evaluate(EvaluationDataset.from_list([row]), metrics=[metrics[metric]], llm=judge,
                          raise_exceptions=True, run_config=RunConfig(timeout=90, max_retries=1),
                          show_progress=False)
        return result.to_pandas().iloc[0][metric]

    score_results(cases, results, run_map, score_metric)
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
              "judge": {"provider": "openai", "model": args.judge_model, "temperature": 0},
              "versions": {name: importlib.metadata.version(name)
                           for name in ("ragas", "langchain-openai", "langchain-core", "openai")},
              "sha256": {"cases": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                         "runs": hashlib.sha256(args.runs.read_bytes()).hexdigest(),
                         "scorer": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         "reviews": hashlib.sha256(args.reviews.read_bytes()).hexdigest() if args.reviews else None},
              "counts": report_counts(results, len(runs)), "cases": results}
    write_reports(args.output, report, cases, run_map)
    print(json.dumps(report["counts"]))
    print(f"Per-case scores: {args.output}; outcomes: {args.output.with_suffix('.report.json')}")
    if report["counts"]["failed"] or report["counts"]["undefined"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
