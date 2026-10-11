"""Run the explicitly opt-in LLM recommendation judge on a sanitized dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from SystemCode.src.backend.evaluation.llm_judge import (
    RecommendationJudgeDataset,
    call_openai_judge,
    evaluate_recommendation_judge,
    recommendation_judge_enabled,
)


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "judge_cases.json"


def main() -> int:
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--live", action="store_true",
        help="explicitly permit external model calls (also set OPENAI_RECOMMENDATION_JUDGE_ENABLED=true)",
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("live judging is opt-in; pass --live and set OPENAI_RECOMMENDATION_JUDGE_ENABLED=true")
    if not recommendation_judge_enabled():
        parser.error("OPENAI_RECOMMENDATION_JUDGE_ENABLED must be explicitly true")

    dataset = RecommendationJudgeDataset.model_validate_json(
        args.dataset.read_text(encoding="utf-8")
    )
    result = evaluate_recommendation_judge(
        dataset, call_openai_judge, repeats=args.repeats, mode="live",
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if result["summary"]["invalid_or_failed_runs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
