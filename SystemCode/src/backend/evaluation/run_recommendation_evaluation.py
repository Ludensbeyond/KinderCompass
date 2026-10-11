"""Run the offline recommendation evaluation on a labelled JSON dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from SystemCode.src.backend.evaluation.recommendation_metrics import (
    claim_accuracy,
    compare_rankings,
    confidence_completeness_error,
    grounded_claim_rate,
    hard_constraint_metrics,
    quadratic_weighted_kappa,
)


DEFAULT_DATASET = Path(__file__).with_name("synthetic_fixtures.json")


def evaluate_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    ranking_reports = []
    for case in dataset.get("ranking_cases", []):
        ranking_reports.append({
            "case_id": case["case_id"],
            **compare_rankings(
                case["old_order"], case["new_order"], case["relevance"], case["reference_order"],
            ),
        })
    hard = dataset.get("hard_constraints", {})
    ratings = dataset.get("paired_ratings", {})
    claims = dataset.get("eligibility_fee_claims", [])
    return {
        "dataset_kind": dataset.get("dataset_kind", "unlabelled"),
        "ranking_algorithm_comparison_status": (
            "unfinished: this runner measures supplied ranking orders and does not run the old or current ranking algorithm"
        ),
        "ranking_comparison": ranking_reports,
        "hard_constraints": hard_constraint_metrics(
            hard.get("candidate_ids", []), hard.get("excluded_ids", []), hard.get("outcomes", {}),
        ),
        "eligibility_and_fee_claims": {
            "overall": claim_accuracy(claims),
            "by_claim_type": {
                claim_type: claim_accuracy([item for item in claims if item.get("claim_type") == claim_type])
                for claim_type in sorted({item.get("claim_type", "unspecified") for item in claims})
            },
        },
        "grounded_claims": grounded_claim_rate(dataset.get("explanation_claims", [])),
        "human_llm_quadratic_weighted_kappa": quadratic_weighted_kappa(
            ratings.get("human", []), ratings.get("llm_judge", []),
        ),
        "confidence_completeness": confidence_completeness_error(dataset.get("confidence_cases", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_dataset(json.loads(args.dataset.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
