"""Replay generated recommendation scenarios against their frozen records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from SystemCode.src.backend.evaluation.benchmark_generation import evaluate_frozen_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New output path; existing reports are never overwritten")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite existing report: {args.output}")
    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        report = evaluate_frozen_dataset(dataset)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"could not evaluate frozen benchmark: {type(error).__name__}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2, ensure_ascii=False)
        target.write("\n")
    print(f"Evaluated {report['case_count']} frozen cases: {args.output}")
    print("No Neo4j or LLM calls were made; retrieval and relevance remain unevaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
