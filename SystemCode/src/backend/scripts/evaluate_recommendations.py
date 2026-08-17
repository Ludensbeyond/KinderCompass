"""Run privacy-safe golden scenarios against the Stage 1 ranking logic."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


POC_ROOT = Path(__file__).resolve().parents[1]
SRC = POC_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stage1.nlp_mapper import map_text_to_filters  # noqa: E402
from stage1.scorer import rank_schools, score_school  # noqa: E402


BASE = {
    "name": "Synthetic Preschool",
    "pedagogy": None,
    "spark_certified": None,
    "provision_of_transport": None,
    "second_languages_offered": None,
    "operator_scheme": None,
    "food_offered": None,
    "weekday_full_day": None,
}


def school(school_id: str, **values: Any) -> dict[str, Any]:
    return {**BASE, "school_id": school_id, "name": f"Synthetic {school_id}", **values}


def _result(name: str, passed: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {"scenario": name, "passed": passed, **details}


def evaluate() -> dict[str, Any]:
    """Evaluate synthetic scenarios without postal codes, income, dates, or chat logs."""
    scenarios = []

    required_profile = map_text_to_filters("Montessori")
    required_ranked = rank_schools(required_profile, [
        school("MATCH", pedagogy="Montessori"),
        school("FAIL", pedagogy="Play-based"),
        school("UNKNOWN"),
    ])
    required_ids = [item["school_id"] for item in required_ranked]
    violations = sum(item["school_id"] == "FAIL" for item in required_ranked)
    scenarios.append(_result("required_preference_enforcement", violations == 0 and "MATCH" in required_ids and "UNKNOWN" in required_ids, {
        "result_ids": required_ids,
        "required_constraint_violations": violations,
    }))

    unknown_profile = map_text_to_filters("SPARK")
    unknown = score_school(unknown_profile, school("UNKNOWN"))
    scenarios.append(_result("unknown_evidence_no_credit", unknown["match_score"] == 0 and unknown["profile_confidence"] == 0, {
        "match_score": unknown["match_score"],
        "evidence_confidence": unknown["profile_confidence"],
        "evidence_status": unknown["match_breakdown"][0]["status"],
    }))

    importance_profile = map_text_to_filters("SPARK with transport")
    for item in importance_profile["preference_items"]:
        item["importance"] = "nice_to_have" if item["attribute"] == "spark_certified" else "high_priority"
    importance_ranked = rank_schools(importance_profile, [
        school("SPARK", spark_certified="Yes", provision_of_transport="No"),
        school("TRANSPORT", spark_certified="No", provision_of_transport="Yes"),
    ])
    scenarios.append(_result("importance_changes_order", importance_ranked[0]["school_id"] == "TRANSPORT", {
        "ordered_ids": [item["school_id"] for item in importance_ranked],
        "scores": [item["match_score"] for item in importance_ranked],
    }))

    tie_profile = map_text_to_filters("SPARK with transport")
    tie_ranked = rank_schools(tie_profile, [
        school("COMPLETE", spark_certified="Yes", provision_of_transport="Yes"),
        school("PARTIAL", spark_certified="Yes"),
    ])
    scenarios.append(_result("evidence_confidence_breaks_match_tie", tie_ranked[0]["school_id"] == "COMPLETE", {
        "ordered_ids": [item["school_id"] for item in tie_ranked],
        "match_scores": [item["match_score"] for item in tie_ranked],
        "evidence_confidence": [item["profile_confidence"] for item in tie_ranked],
    }))

    hard_only = map_text_to_filters("I need Chinese")
    hard_ranked = rank_schools(hard_only, [school("HARD", second_languages_offered="Chinese")])
    scenarios.append(_result("hard_constraints_only", hard_ranked[0]["match_score"] == 100 and not hard_ranked[0]["match_breakdown"], {
        "match_score": hard_ranked[0]["match_score"],
        "weighted_preferences": len(hard_ranked[0]["match_breakdown"]),
    }))

    passed = sum(item["passed"] for item in scenarios)
    return {
        "privacy": "Synthetic fixtures only; no family details, postal codes, or chat history.",
        "summary": {"total": len(scenarios), "passed": passed, "failed": len(scenarios) - passed},
        "scenarios": scenarios,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 7 recommendation evaluation",
        "",
        report["privacy"],
        "",
        f"**Result:** {report['summary']['passed']}/{report['summary']['total']} scenarios passed.",
        "",
        "| Scenario | Status | Diagnostics |",
        "|---|---|---|",
    ]
    for item in report["scenarios"]:
        diagnostics = json.dumps({key: value for key, value in item.items() if key not in {"scenario", "passed"}}, ensure_ascii=False)
        lines.append(f"| {item['scenario']} | {'PASS' if item['passed'] else 'FAIL'} | `{diagnostics}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate KinderCompass recommendation ranking with synthetic golden scenarios")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Evaluation report written to {args.output}")
    else:
        print(rendered, end="")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
