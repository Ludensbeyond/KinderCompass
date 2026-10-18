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
    paired_rating_agreement,
)
from SystemCode.src.backend.evaluation.legacy_match_first import rank_schools as legacy_rank_schools
from SystemCode.src.backend.evaluation.benchmark_validation import BENCHMARK_KIND, SYNTHETIC_KIND, validate_benchmark
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
             "unknown_retained", "unknown_excluded", "unlabelled_retained", "unlabelled_excluded")
    counts = {name: sum(item[name] for item in reports) for name in names}
    failures = counts["true_positive"] + counts["false_negative"]
    passes = counts["false_positive"] + counts["true_negative"]
    unknown = counts["unknown_retained"] + counts["unknown_excluded"]
    unlabelled = counts["unlabelled_retained"] + counts["unlabelled_excluded"]
    precision = counts["true_positive"] / (counts["true_positive"] + counts["false_positive"]) if counts["true_positive"] + counts["false_positive"] else None
    recall = counts["true_positive"] / failures if failures else None
    f1_denominator = 2 * counts["true_positive"] + counts["false_positive"] + counts["false_negative"]
    f1 = 2 * counts["true_positive"] / f1_denominator if f1_denominator else None
    return {
        **counts,
        "precision": precision, "recall": recall, "f1": f1,
        "f1_denominator": f1_denominator,
        "confirmed_failure_violation_rate": counts["false_negative"] / failures if failures else None,
        "confirmed_failure_denominator": failures,
        "confirmed_pass_over_exclusion_rate": counts["false_positive"] / passes if passes else None,
        "confirmed_pass_denominator": passes,
        "unknown_retention_rate": counts["unknown_retained"] / unknown if unknown else None,
        "unknown_denominator": unknown,
        "unlabelled_denominator": unlabelled,
        "case_count": len(reports),
    }


def evaluate_dataset(dataset: dict[str, Any], judge_report: dict[str, Any] | None = None) -> dict[str, Any]:
    if dataset.get("dataset_kind") == BENCHMARK_KIND or (
        dataset.get("dataset_kind") == SYNTHETIC_KIND and "benchmark_id" in dataset
    ):
        validate_benchmark(dataset)
    ranking_reports = []
    old_case_metrics = []
    new_case_metrics = []
    eligibility_reports = []
    hard_reports = []
    individual_hard_reports: dict[str, list[dict[str, Any]]] = {}
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
            reference_order=case.get("reference_order"),
            hard_constraint_outcomes=case.get("hard_constraint_outcomes"),
            eligibility=case.get("eligibility"),
        )
        new_metrics = evaluate_ranking_case(
            new_ids, relevance, case_id=case_id, reference_case_id=reference_case_id,
            reference_ids=references, labels_complete=case.get("labels_complete"),
            reference_order=case.get("reference_order"),
            hard_constraint_outcomes=case.get("hard_constraint_outcomes"),
            eligibility=case.get("eligibility"),
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
        for check in case.get("hard_constraint_checks", []):
            name = check.get("constraint")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"hard constraint check in {case_id!r} needs a constraint name")
            individual_hard_reports.setdefault(name, []).append({
                "case_id": case_id,
                **hard_constraint_metrics(
                    check.get("candidate_ids", []), check.get("excluded_ids", []), check.get("outcomes", {}),
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
    rating_records = dataset.get("human_judge_ratings", [])
    claims = dataset.get("eligibility_fee_claims", [])
    agreement = (
        paired_rating_agreement(rating_records)
        if dataset.get("dataset_kind") in {"human_reviewed", BENCHMARK_KIND} and rating_records
        else {
            "status": "not_measured_no_paired_human_labels" if dataset.get("dataset_kind") == BENCHMARK_KIND else "not_measured_dataset_not_human_reviewed",
            "sample_size": 0,
            "overall": {"sample_size": 0, "raw_agreement": None,
                        "raw_agreement_95_percent_wilson_interval": None,
                        "quadratic_weighted_cohen_kappa": None, "paired_ratings": []},
            "by_dimension": {},
            "scale": {"minimum": 1, "maximum": 5, "type": "ordinal"},
        }
    )
    agreement["judge_configuration"] = dataset.get("judge_configuration")
    if agreement["sample_size"]:
        config = agreement["judge_configuration"]
        required_config = ("model", "prompt_version", "rubric_version", "settings")
        if not isinstance(config, dict) or any(not config.get(key) for key in required_config):
            agreement["status"] = "measured_incomplete_judge_configuration"
    ranking_cases = dataset.get("ranking_cases", [])
    label_status = dataset.get("reference_label_status", "not_declared")
    evaluation_status = (
        "illustrative_only" if dataset.get("dataset_kind") == "synthetic_test_fixture"
        else "manual_labels_not_independently_audited" if dataset.get("dataset_kind") == BENCHMARK_KIND
        else "reference_label_evaluation" if label_status in {"independently_reviewed", "independently_verified"}
        else "labels_not_independently_verified"
    )
    benchmark_details = {
        "benchmark_version": dataset.get("benchmark_version", "unspecified"),
        "schema_version": dataset.get("schema_version", "unspecified"),
        "dataset_kind": dataset.get("dataset_kind", "unlabelled"),
        "benchmark_id": dataset.get("benchmark_id"),
        "split": dataset.get("split"),
        "reference_label_status": "illustrative_only" if dataset.get("dataset_kind") == "synthetic_test_fixture" else label_status,
        "ranking_scenarios": len(ranking_cases),
        "candidate_school_records": sum(len(case.get("schools", [])) for case in ranking_cases),
        "relevance_labels": sum(len(case.get("relevance", {})) for case in ranking_cases),
        "missing_relevance_labels": sum(
            max(0, len(case.get("reference_ids", case.get("schools", []))) - len(case.get("relevance", {})))
            for case in ranking_cases
        ),
        "reference_rankings": sum(case.get("reference_order") is not None for case in ranking_cases),
        "hard_constraint_outcome_labels": sum(len(case.get("hard_constraint_outcomes", {})) for case in ranking_cases),
        "missing_hard_constraint_outcomes": sum(
            max(0, len(case.get("schools", [])) - len(case.get("hard_constraint_outcomes", {})))
            for case in ranking_cases
        ),
        "eligibility_labels": sum(len(case.get("eligibility", {})) for case in ranking_cases),
        "missing_eligibility_labels": sum(
            max(0, len(case.get("schools", [])) - len(case.get("eligibility", {})))
            for case in ranking_cases
        ),
        "hard_constraint_pairs": len(hard.get("candidate_ids", [])) + sum(len(case.get("hard_constraint_outcomes", {})) for case in ranking_cases),
        "individual_hard_constraint_checks": sum(len(case.get("hard_constraint_checks", [])) for case in ranking_cases),
        "claim_records": len(claims),
        "explanation_claim_annotations": len(dataset.get("explanation_claims", [])),
        "paired_human_judge_ratings": len(rating_records) if dataset.get("dataset_kind") in {"human_reviewed", BENCHMARK_KIND} else 0,
        "label_provenance_records": len(dataset.get("label_provenance", [])),
        "not_applicable_labels": len(dataset.get("not_applicable_labels", [])),
        "not_applicable_label_records": dataset.get("not_applicable_labels", []),
        "external_service_calls": 0,
    }
    return {
        "benchmark_details": benchmark_details,
        "evaluation_configuration": {
            "relevance_scale": {0: "not relevant", 1: "marginally relevant", 2: "relevant", 3: "highly relevant"},
            "binary_relevance_threshold": 2,
            "ndcg_gain": "2^relevance - 1",
            "ndcg_discount": "log2(rank + 1)",
            "kendall_variant": "tau-b; ties handled in denominator; known hard failures and ineligible candidates excluded",
            "ranking_aggregation": "macro mean over defined per-case values",
            "hard_constraint_positive_class": "confirmed violation requiring exclusion",
            "claim_accuracy": "verified atomic claims only; numeric comparisons use per-claim non-negative tolerance and matching units",
            "explanation_grounding": "manually segmented atomic factual claims with explicit evidence source/reference and adjudicated status",
            "agreement": "quadratic weighted Cohen kappa and raw agreement over paired ordinal ratings; only human_reviewed datasets",
        },
        "benchmark_id": dataset.get("benchmark_id"),
        "benchmark_version": dataset.get("benchmark_version", "unspecified"),
        "split": dataset.get("split"),
        "dataset_kind": dataset.get("dataset_kind", "unlabelled"),
        "evaluation_status": evaluation_status,
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
            "hard_constraints": {
                "per_case": hard_reports,
                "aggregate": _aggregate_safety(hard_reports, "hard"),
                "per_constraint": {
                    name: {"per_case": reports, "aggregate": _aggregate_safety(reports, "hard")}
                    for name, reports in sorted(individual_hard_reports.items())
                },
            },
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
        "human_llm_agreement": agreement,
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


def readable_summary(report: dict[str, Any]) -> str:
    """Render a concise text summary without promoting synthetic scores to results."""
    details = report.get("benchmark_details", {})
    lines = [
        f"KinderCompass recommendation evaluation ({report.get('dataset_kind', 'unlabelled')})",
        f"Status: {report.get('evaluation_status', 'unknown')}",
        f"Benchmark: {details.get('benchmark_id') or 'unspecified'}; version={details.get('benchmark_version', 'unspecified')}; split={details.get('split') or 'unspecified'}; cases={details.get('ranking_scenarios', 0)}",
        f"Labels: relevance={details.get('relevance_labels', 0)}; hard-constraint={details.get('hard_constraint_outcome_labels', 0)}; eligibility={details.get('eligibility_labels', 0)}; factual claims={details.get('claim_records', 0)}; explanation claims={details.get('explanation_claim_annotations', 0)}; paired ratings={details.get('paired_human_judge_ratings', 0)}; not applicable={details.get('not_applicable_labels', 0)}",
    ]
    hard = report["hard_constraints"]
    lines.append(
        "Hard-constraint exclusion: "
        f"precision={hard['precision']}, recall={hard['recall']}, F1={hard['f1']} "
        f"(TP={hard['true_positive']}, FP={hard['false_positive']}, "
        f"FN={hard['false_negative']}, TN={hard['true_negative']}, "
        f"unknown={hard['unknown_denominator']})"
    )
    for algorithm in ("old_match_first", "new_combined_score"):
        block = report["quantitative_ranking_evaluation"][algorithm]
        lines.append(f"Ranking {algorithm} (macro over defined scenarios):")
        for metric, value in block["aggregate"]["metrics"].items():
            lines.append(f"  {metric}: {value['value']} (n={value['denominator']}, excluded={value['excluded_cases']})")
    claims = report["eligibility_and_fee_claims"]["overall"]
    lines.append(
        f"Eligibility/fee claims: accuracy={claims['accuracy']} "
        f"(correct={claims['correct']}, incorrect={claims['incorrect']}, unverified={claims['unverified']})"
    )
    grounded = report["grounded_claims"]
    lines.append(
        f"Explanation grounding: rate={grounded['rate']} "
        f"(supported={grounded['supported']}, contradicted={grounded['contradicted']}, "
        f"unsupported={grounded['unsupported']}, unverifiable={grounded['unverifiable']})"
    )
    agreement = report["human_llm_agreement"]
    lines.append(
        f"Human–LLM agreement: {agreement['status']}, n={agreement['sample_size']}, "
        f"raw={agreement['overall']['raw_agreement']}, "
        f"quadratic weighted kappa={agreement['overall']['quadratic_weighted_cohen_kappa']}"
    )
    return "\n".join(lines) + "\n"


def readable_metric_summary(metric: str, results: dict[str, Any], metadata: dict[str, Any] | None = None) -> str:
    """Render one selected section without a JSON-only CLI surprise."""
    lines = [f"KinderCompass evaluation metric: {metric}"]
    if metadata:
        lines.append(
            f"Dataset: {metadata.get('dataset_kind', 'unlabelled')}; benchmark={metadata.get('benchmark_id') or 'unspecified'}; "
            f"version={metadata.get('benchmark_version', 'unspecified')}; split={metadata.get('split') or 'unspecified'}; "
            f"status={metadata.get('evaluation_status', 'unknown')}"
        )
    if metric == "hard-constraints":
        for key, section in results.items():
            if key == "ranking_hard_constraints":
                section = section["aggregate"]
            lines.append(f"{key}: precision={section.get('precision')}, recall={section.get('recall')}, F1={section.get('f1')}")
    elif metric == "ranking":
        for algorithm in ("old_match_first", "new_combined_score"):
            metrics = results[algorithm]["aggregate"]["metrics"]
            lines.append(f"{algorithm}:")
            lines.extend(f"  {name}: {value['value']} (n={value['denominator']})" for name, value in metrics.items())
    elif metric == "claims":
        lines.append(f"overall: {results['overall']}")
        lines.extend(f"{name}: {value}" for name, value in results["by_claim_type"].items())
    elif metric == "explanations":
        lines.append(str(results))
    elif metric == "agreement":
        lines.append(
            f"{results['status']}: n={results['sample_size']}, "
            f"raw={results['overall']['raw_agreement']}, "
            f"quadratic weighted kappa={results['overall']['quadratic_weighted_cohen_kappa']}"
        )
    else:
        lines.append(str(results))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--metric", choices=("all", "hard-constraints", "ranking", "claims", "explanations", "agreement"), default="all")
    parser.add_argument("--judge-report", type=Path,
                        help="include an already-completed LLM judge report as a separate section; makes no model calls")
    parser.add_argument("--validate-only", action="store_true",
                        help="validate a manual benchmark without calculating metrics")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if dataset.get("dataset_kind") == BENCHMARK_KIND or (
        dataset.get("dataset_kind") == SYNTHETIC_KIND and "benchmark_id" in dataset
    ):
        validate_benchmark(dataset)
    if args.validate_only:
        is_benchmark_dataset = dataset.get("dataset_kind") == BENCHMARK_KIND or (
            dataset.get("dataset_kind") == SYNTHETIC_KIND and "benchmark_id" in dataset
        )
        if not is_benchmark_dataset:
            parser.error("--validate-only is for manual_label_benchmark or synthetic_test_fixture datasets")
        print(json.dumps({
            "status": "valid",
            "dataset_kind": dataset["dataset_kind"],
            "benchmark_id": dataset["benchmark_id"],
            "benchmark_version": dataset["benchmark_version"],
            "split": dataset["split"],
            "case_count": len(dataset["ranking_cases"]),
            "reference_label_status": dataset["reference_label_status"],
            "note": (
                "Synthetic labels are illustrative only; no real facts or independent labels are asserted."
                if dataset["dataset_kind"] == SYNTHETIC_KIND else
                "Labels and source assertions are user supplied and are not independently audited by this validator."
            ),
        }, indent=2, ensure_ascii=False))
        return 0
    judge_report = json.loads(args.judge_report.read_text(encoding="utf-8")) if args.judge_report else None
    result = evaluate_dataset(
        dataset, judge_report=judge_report,
    )
    selected_sections = {
        "hard-constraints": {"hard_constraints": result["hard_constraints"],
                             "ranking_hard_constraints": result["quantitative_ranking_evaluation"]["hard_constraints"]},
        "ranking": result["quantitative_ranking_evaluation"],
        "claims": result["eligibility_and_fee_claims"],
        "explanations": result["grounded_claims"],
        "agreement": result["human_llm_agreement"],
    }
    if args.metric != "all":
        result = {"dataset_kind": result["dataset_kind"], "evaluation_status": result["evaluation_status"],
                  "benchmark_id": result.get("benchmark_id"), "benchmark_version": result.get("benchmark_version"),
                  "split": result.get("benchmark_details", {}).get("split"),
                  "benchmark_details": result.get("benchmark_details"),
                  "selected_metric": args.metric, "results": selected_sections[args.metric]}
    rendered = readable_summary(result) if args.format == "summary" and args.metric == "all" else (
        readable_metric_summary(args.metric, result["results"], result) if args.format == "summary" else
        json.dumps(result, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else
        json.dumps(result["results"], indent=2, ensure_ascii=False) + "\n"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
