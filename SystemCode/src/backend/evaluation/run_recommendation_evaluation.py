"""Run the offline recommendation evaluation on a labelled JSON dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from SystemCode.src.backend.evaluation.recommendation_metrics import (
    aggregate_case_metrics,
    claim_accuracy,
    confidence_completeness_error,
    grounded_claim_rate,
    hard_constraint_metrics,
    eligibility_violation_metrics,
    evaluate_ranking_case,
    quadratic_weighted_kappa,
)
from SystemCode.src.backend.evaluation.legacy_match_first import rank_schools as legacy_rank_schools
from SystemCode.src.backend.pipeline.stage1.scorer import rank_schools


DEFAULT_DATASET = Path(__file__).with_name("synthetic_fixtures.json")


def _aggregate_safety(reports: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if key == "eligibility":
        names = ("eligible", "ineligible", "unknown", "unlabelled")
        counts = {name: sum(item[name] for item in reports) for name in names}
        known = counts["eligible"] + counts["ineligible"]
        total = sum(counts.values())
        return {
            **counts,
            "confirmed_ineligible_recommendation_rate": counts["ineligible"] / known if known else None,
            "known_eligibility_denominator": known,
            "unknown_recommendation_rate": counts["unknown"] / total if total else None,
            "unknown_denominator": total,
            "case_count": len(reports),
        }
    names = ("true_positive", "false_positive", "false_negative", "true_negative",
             "unknown_retained", "unknown_excluded")
    counts = {name: sum(item[name] for item in reports) for name in names}
    failures = counts["true_positive"] + counts["false_negative"]
    passes = counts["false_positive"] + counts["true_negative"]
    unknown = counts["unknown_retained"] + counts["unknown_excluded"]
    return {
        **counts,
        "confirmed_failure_violation_rate": counts["false_negative"] / failures if failures else None,
        "confirmed_failure_denominator": failures,
        "confirmed_pass_over_exclusion_rate": counts["false_positive"] / passes if passes else None,
        "confirmed_pass_denominator": passes,
        "unknown_retention_rate": counts["unknown_retained"] / unknown if unknown else None,
        "unknown_denominator": unknown,
        "case_count": len(reports),
    }


def evaluate_dataset(dataset: dict[str, Any], judge_report: dict[str, Any] | None = None) -> dict[str, Any]:
    ranking_reports = []
    old_case_metrics = []
    new_case_metrics = []
    eligibility_reports = []
    hard_reports = []
    for case in dataset.get("ranking_cases", []):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"ranking case has invalid case_id: {case_id!r}; expected a non-empty scenario ID")
        reference_case_id = case.get("reference_case_id")
        if not isinstance(reference_case_id, str) or not reference_case_id.strip():
            raise ValueError(
                f"ranking case {case_id!r} has invalid reference_case_id: {reference_case_id!r}; "
                "expected an explicit non-empty ID"
            )
        if case_id != reference_case_id:
            raise ValueError(
                f"ranking case {case_id!r} does not match reference case {reference_case_id!r}"
            )
        if "profile" not in case or "schools" not in case:
            raise ValueError(f"ranking case {case_id!r} needs profile and schools to generate rankings")
        schools = case["schools"]
        candidate_ids = [item.get("school_id") or item.get("id") for item in schools]
        if any(not isinstance(school_id, str) or not school_id.strip() for school_id in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError(f"ranking case {case_id!r} needs unique, non-empty school IDs")
        profile = case["profile"]
        old_ids = [str(item.get("school_id") or item.get("id"))
                   for item in legacy_rank_schools(profile, schools, limit=len(schools))]
        new_ids = [str(item.get("school_id") or item.get("id"))
                   for item in rank_schools(profile, schools, limit=len(schools))]
        relevance = case.get("relevance", {})
        references = case.get("reference_ids")
        old_metrics = evaluate_ranking_case(
            old_ids, relevance, case_id=case_id, reference_case_id=reference_case_id,
            reference_ids=references, labels_complete=case.get("labels_complete"),
        )
        new_metrics = evaluate_ranking_case(
            new_ids, relevance, case_id=case_id, reference_case_id=reference_case_id,
            reference_ids=references, labels_complete=case.get("labels_complete"),
        )
        old_case_metrics.append(old_metrics)
        new_case_metrics.append(new_metrics)
        candidate_ids = [str(school_id) for school_id in candidate_ids]
        if "eligibility" in case:
            eligibility_reports.append({
                "case_id": case_id,
                **eligibility_violation_metrics(new_ids, case["eligibility"]),
            })
        if "hard_constraint_outcomes" in case:
            new_retained = set(new_ids)
            hard_reports.append({
                "case_id": case_id,
                **hard_constraint_metrics(
                    candidate_ids, [school_id for school_id in candidate_ids if school_id not in new_retained],
                    case["hard_constraint_outcomes"],
                ),
            })
        ranking_reports.append({
            "case_id": case_id,
            "reference_case_id": reference_case_id,
            "old_match_first": {"ranking_ids": old_ids, "metrics": old_metrics["metrics"]},
            "new_combined_score": {"ranking_ids": new_ids, "metrics": new_metrics["metrics"]},
            "duplicate_policy": "remove duplicate result IDs, preserving their first occurrence",
        })
    hard = dataset.get("hard_constraints", {})
    ratings = dataset.get("paired_ratings", {})
    claims = dataset.get("eligibility_fee_claims", [])
    return {
        "dataset_kind": dataset.get("dataset_kind", "unlabelled"),
        "ranking_algorithm_comparison_status": (
            "generated: frozen main baseline and current production ranker ran on the same cases and labels; bundled fixture is synthetic only"
        ),
        "ranking_comparison": ranking_reports,
        "quantitative_ranking_evaluation": {
            "method": "generated legacy match-first and current combined-score orders from the same profile and school records",
            "limitations": "Legacy implementation is frozen from main at c86d269; bundled labels and school records are synthetic and are not performance evidence.",
            "relevance_scale": {0: "not relevant", 1: "marginally relevant", 2: "relevant", 3: "highly relevant"},
            "binary_relevance_threshold": 2,
            "old_match_first": {
                "per_case": old_case_metrics,
                "aggregate": aggregate_case_metrics(old_case_metrics),
            },
            "new_combined_score": {
                "per_case": new_case_metrics,
                "aggregate": aggregate_case_metrics(new_case_metrics),
            },
            "eligibility": {"per_case": eligibility_reports, "aggregate": _aggregate_safety(eligibility_reports, "eligibility")},
            "hard_constraints": {"per_case": hard_reports, "aggregate": _aggregate_safety(hard_reports, "hard")},
        },
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
        "llm_judge_explanation_quality": (
            {
                "status": "included as separate judge evaluation; scores are not ranking metrics",
                "scores": judge_report,
            }
            if judge_report is not None
            else {
                "status": "not included; supply a completed judge report with --judge-report",
                "scores": None,
            }
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--judge-report", type=Path,
                        help="include an already-completed LLM judge report as a separate section; makes no model calls")
    args = parser.parse_args()
    judge_report = json.loads(args.judge_report.read_text(encoding="utf-8")) if args.judge_report else None
    result = evaluate_dataset(
        json.loads(args.dataset.read_text(encoding="utf-8")), judge_report=judge_report,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
