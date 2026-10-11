"""Verify scoring with one synthetic fixture; never executes the KinderCompass agent."""

import argparse
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/kindercompass-ragas-fixture"))
    parser.add_argument("--judge-model", help="Explicit evaluation model, independent of agent settings")
    parser.add_argument("--env-file", type=Path, help="Read only OPENAI_API_KEY from this local secret file")
    parser.add_argument("--validate-only", action="store_true", help="No dependencies or paid calls")
    args = parser.parse_args()
    if not args.validate_only and not args.judge_model:
        parser.error("--judge-model is required for the paid smoke test")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    case_id = "synthetic_format_fixture"
    passage = "The fictional Example Preschool opens at 9 am on Mondays."
    case = {
        "case_id": case_id,
        "evaluation": "ragas",
        "user_input": "When does the fictional Example Preschool open on Mondays?",
        "reference": "It opens at 9 am on Mondays.",
    }
    run = {
        "case_id": case_id,
        "response": "It opens at 9 am on Mondays.",
        "retrieved_contexts": [passage],
        "fixture": True,
    }
    cases_path = args.output_dir / "fixture.cases.jsonl"
    runs_path = args.output_dir / "fixture.runs.jsonl"
    output_path = args.output_dir / "fixture.scores.csv"
    for path, row in ((cases_path, case), (runs_path, run)):
        path.write_text(json.dumps(row) + "\n")
    command = [
        sys.executable, str(Path(__file__).with_name("score.py")),
        "--cases", str(cases_path), "--runs", str(runs_path),
    ]
    subprocess.run([*command, "--validate-only"], check=True)
    print("Synthetic fixture only; no agent execution or baseline results.", flush=True)
    if args.validate_only:
        return

    # Do not load agent models, Azure credentials or other application settings.
    judge_env = dict(os.environ)
    if args.env_file:
        from dotenv import dotenv_values

        key = dotenv_values(args.env_file).get("OPENAI_API_KEY")
        if not judge_env.get("OPENAI_API_KEY") and key:
            judge_env["OPENAI_API_KEY"] = key
    if not judge_env.get("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY or supply --env-file for the evaluation judge")
    # Keep fixture text out of optional third-party tracing and usage telemetry.
    judge_env["LANGCHAIN_TRACING_V2"] = "false"
    judge_env["LANGSMITH_TRACING"] = "false"
    judge_env["RAGAS_DO_NOT_TRACK"] = "true"
    subprocess.run(
        [*command, "--judge-model", args.judge_model, "--output", str(output_path)],
        env=judge_env,
        check=True,
    )
    with output_path.open(newline="") as handle:
        scores = list(csv.DictReader(handle))
    if len(scores) != 1 or scores[0]["case_id"] != case_id:
        raise ValueError("Expected exactly one synthetic fixture in the CSV export")
    for metric in ("faithfulness", "llm_context_precision_with_reference", "context_recall"):
        score = float(scores[0][metric])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"Invalid fixture score for {metric}: {score}")
    print(f"Verified three finite fixture scores and CSV export: {output_path}")


if __name__ == "__main__":
    main()
