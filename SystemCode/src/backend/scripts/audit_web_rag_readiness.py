"""Audit Phase 9 evidence against labelled cases and production-readiness gates."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from stage1.web_rag import load_json, retrieve, retrieve_operator_evidence, save_json


POC_ROOT = Path(__file__).resolve().parents[1]
NOISE_RE = re.compile(r"cookie|privacy overview|google review|manage consent", re.I)
REQUIRED_CITATION_FIELDS = ("url", "title", "retrieved_at", "chunk_id")
DEFAULT_THRESHOLDS = {
    "minimum_identity_cases": 50,
    "minimum_identity_assessed_cases": 30,
    "minimum_retrieval_cases": 30,
    "identity_accuracy": 0.95,
    "fetch_success_rate": 0.80,
    "retrieval_accuracy": 0.90,
    "citation_completeness": 1.0,
    "scope_accuracy": 1.0,
    "school_isolation": 1.0,
    "clean_page_rate": 0.95,
}

STATUS_IDENTITY = {
    "approved": "school",
    "approved_operator": "operator",
    "rejected": "incorrect",
    "pending_review": "unassessed",
}

LEGACY_EXPECTED_IDENTITY = {
    **STATUS_IDENTITY,
    "fetch_failed": "unverified",
}


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0


def audit(
    index: dict[str, Any],
    school_decisions: list[dict[str, Any]],
    operator_decisions: list[dict[str, Any]],
    labels: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    school_by_id = {item.get("school_id"): item for item in school_decisions}
    operator_by_url = {item.get("url"): item for item in operator_decisions}

    identity_results = []
    for case in labels.get("identity_cases", []):
        decision = school_by_id.get(case.get("school_id")) if case.get("evidence_scope", "school") == "school" else operator_by_url.get(case.get("url"))
        actual_status = decision.get("review_status") if decision else "missing_decision"
        actual_identity = STATUS_IDENTITY.get(actual_status, "unassessed")
        expected_identity = case.get("expected_identity") or LEGACY_EXPECTED_IDENTITY.get(
            case.get("expected_status"), "unverified"
        )
        identity_labelled = expected_identity != "unverified"
        identity_assessed = identity_labelled and actual_identity != "unassessed"
        identity_results.append({
            "case_id": case.get("case_id"),
            "expected_identity": expected_identity,
            "actual_identity": actual_identity,
            "actual_status": actual_status,
            "identity_labelled": identity_labelled,
            "identity_assessed": identity_assessed,
            "passed": identity_assessed and actual_identity == expected_identity,
            "fetch_succeeded": actual_status not in {"fetch_failed", "missing_decision"},
            "policy_excluded": bool(decision and decision.get("failure_code") == "robots_disallowed"),
        })

    retrieval_results = []
    citation_passes = scope_passes = isolation_passes = 0
    for case in labels.get("retrieval_cases", []):
        scope = case.get("expected_scope", "school")
        if scope == "operator":
            results = retrieve_operator_evidence(index, case["school_id"], case["query"], limit=1)
        else:
            results = retrieve(index, case["school_id"], case["query"], limit=1)
        expected_evidence = bool(case.get("evidence_expected", True))
        top = results[0] if results else None
        evidence_correct = bool(top) == expected_evidence
        expected_terms = [str(term).casefold() for term in case.get("expected_terms", [])]
        terms_correct = (
            not expected_evidence or not expected_terms
            or bool(top) and any(term in top.get("text", "").casefold() for term in expected_terms)
        )
        source_expected = str(case.get("expected_source_contains") or "").casefold()
        source_correct = (
            not expected_evidence or not source_expected
            or bool(top) and source_expected in top.get("source_url", "").casefold()
        )
        citation_correct = not top or all(top.get("citation", {}).get(field) for field in REQUIRED_CITATION_FIELDS)
        scope_correct = not top or (
            (scope == "operator" and top.get("evidence_scope") == "operator" and top.get("school_id") is None)
            or (scope == "school" and top.get("school_id") == case["school_id"] and top.get("evidence_scope") != "operator")
        )
        isolation_correct = not top or top.get("school_id") in {None, case["school_id"]}
        passed = evidence_correct and terms_correct and source_correct and citation_correct and scope_correct and isolation_correct
        citation_passes += int(citation_correct)
        scope_passes += int(scope_correct)
        isolation_passes += int(isolation_correct)
        retrieval_results.append({
            "case_id": case.get("case_id"), "passed": passed, "result_count": len(results),
            "evidence_correct": evidence_correct, "terms_correct": terms_correct,
            "source_correct": source_correct, "citation_correct": citation_correct,
            "scope_correct": scope_correct, "isolation_correct": isolation_correct,
            "top_chunk_id": top.get("chunk_id") if top else None,
        })

    pages = list(index.get("pages", [])) + list(index.get("operator_pages", []))
    clean_pages = 0
    for page in pages:
        combined = " ".join(chunk.get("text", "") for chunk in page.get("chunks", []))
        clean_pages += int(not NOISE_RE.search(combined))
    freshness = Counter(page.get("freshness", "unknown") for page in pages)
    failures = Counter(
        item.get("failure_code", "unclassified")
        for item in school_decisions + operator_decisions if item.get("review_status") == "fetch_failed"
    )
    labelled_identity_results = [item for item in identity_results if item["identity_labelled"]]
    assessed_identity_results = [item for item in identity_results if item["identity_assessed"]]
    identity_passes = sum(item["passed"] for item in assessed_identity_results)
    fetch_eligible_results = [item for item in identity_results if not item["policy_excluded"]]
    fetch_successes = sum(item["fetch_succeeded"] for item in fetch_eligible_results)
    retrieval_passes = sum(item["passed"] for item in retrieval_results)
    metrics = {
        "identity_cases": len(identity_results),
        "identity_labelled_cases": len(labelled_identity_results),
        "identity_assessed_cases": len(assessed_identity_results),
        "retrieval_cases": len(retrieval_results),
        "identity_accuracy": _rate(identity_passes, len(assessed_identity_results)),
        "identity_assessment_coverage": _rate(len(assessed_identity_results), len(labelled_identity_results)),
        "fetch_eligible_cases": len(fetch_eligible_results),
        "policy_excluded_cases": len(identity_results) - len(fetch_eligible_results),
        "fetch_success_rate": _rate(fetch_successes, len(fetch_eligible_results)),
        "retrieval_accuracy": _rate(retrieval_passes, len(retrieval_results)),
        "citation_completeness": _rate(citation_passes, len(retrieval_results)),
        "scope_accuracy": _rate(scope_passes, len(retrieval_results)),
        "school_isolation": _rate(isolation_passes, len(retrieval_results)),
        "clean_page_rate": _rate(clean_pages, len(pages)),
        "indexed_school_pages": len(index.get("pages", [])),
        "indexed_operator_pages": len(index.get("operator_pages", [])),
    }
    gates = {
        "identity_sample_size": metrics["identity_labelled_cases"] >= thresholds["minimum_identity_cases"],
        "identity_assessed_sample_size": metrics["identity_assessed_cases"] >= thresholds["minimum_identity_assessed_cases"],
        "retrieval_sample_size": metrics["retrieval_cases"] >= thresholds["minimum_retrieval_cases"],
        **{
            key: metrics[key] >= thresholds[key]
            for key in ("identity_accuracy", "fetch_success_rate", "retrieval_accuracy", "citation_completeness", "scope_accuracy", "school_isolation", "clean_page_rate")
        },
    }
    return {
        "production_ready": all(gates.values()),
        "metrics": metrics,
        "thresholds": thresholds,
        "gates": gates,
        "freshness": dict(sorted(freshness.items())),
        "failures": dict(sorted(failures.items())),
        "identity_results": identity_results,
        "retrieval_results": retrieval_results,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 9 production-readiness audit", "",
        f"**Production ready: {'YES' if report['production_ready'] else 'NO'}**", "",
        "## Acceptance gates", "", "| Gate | Result |", "|---|---|",
    ]
    lines.extend(f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in report["gates"].items())
    lines.extend(["", "## Metrics", "", "| Metric | Value |", "|---|---:|"])
    lines.extend(f"| {name} | {value} |" for name, value in report["metrics"].items())
    lines.extend(["", "## Freshness", "", json.dumps(report["freshness"], sort_keys=True), "", "## Failures", "", json.dumps(report["failures"], sort_keys=True), ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    parser.add_argument("--school-decisions", type=Path, default=POC_ROOT / "web_rag" / "pilot_allowlist.json")
    parser.add_argument("--operator-decisions", type=Path, default=POC_ROOT / "web_rag" / "operator_page_allowlist.json")
    parser.add_argument("--labels", type=Path, default=POC_ROOT / "web_rag" / "production_audit_labels.json")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(load_json(args.index), load_json(args.school_decisions), load_json(args.operator_decisions), load_json(args.labels))
    content = json.dumps(report, indent=2) + "\n" if args.format == "json" else markdown(report)
    if args.output:
        if args.format == "json":
            save_json(args.output, report)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
        print(f"Audit written to {args.output}")
    else:
        print(content)
    return 0 if report["production_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
