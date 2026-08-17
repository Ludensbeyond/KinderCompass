"""Evaluate deterministic or LLM-synthesised Phase 9 chat answers."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from stage1.conversation import update_conversation
from stage1.web_rag import load_json, save_json


POC_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CITATION_FIELDS = ("url", "title", "retrieved_at", "chunk_id")
DEFAULT_THRESHOLDS = {
    "minimum_cases": 30,
    "answer_accuracy": 0.90,
    "citation_validity": 1.0,
    "unsupported_claim_free_rate": 1.0,
    "conciseness_rate": 0.95,
    "school_isolation": 1.0,
    "maximum_fallback_rate": 0.10,
}


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0


def _expected_term_matches(answer: str, expected: str) -> bool:
    def normal(value: str) -> str:
        value = re.sub(r"\b(?:[a-z]\.){2,}[a-z]?\.?", lambda match: match.group(0).replace(".", ""), value.casefold())
        return re.sub(r"[^a-z0-9]+", " ", value).strip()
    answer_normal = normal(answer)
    expected_normal = normal(expected)
    if expected_normal in answer_normal:
        return True
    expected_tokens = set(expected_normal.split())
    answer_tokens = set(answer_normal.split())
    return bool(expected_tokens) and len(expected_tokens & answer_tokens) / len(expected_tokens) >= 0.5


def _answer_cases(index: dict[str, Any], labels: dict[str, Any]) -> list[dict[str, Any]]:
    if "cases" in labels:
        return labels["cases"]
    school_names = {
        page.get("school_id"): page.get("school_name") or page.get("school_id")
        for page in index.get("pages", [])
    }
    return [
        {
            "case_id": case["case_id"], "school_id": case["school_id"],
            "school_name": school_names[case["school_id"]], "question": case["query"],
            "evidence_expected": bool(case.get("evidence_expected", True)),
            "expected_terms": case.get("expected_terms", []), "forbidden_terms": [],
        }
        for case in labels.get("retrieval_cases", [])
        if case.get("expected_scope", "school") == "school" and case.get("school_id") in school_names
    ]


def evaluate(
    index: dict[str, Any], labels: dict[str, Any], *, use_llm: bool = False,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    previous = os.environ.get("OPENAI_WEB_RAG_ANSWERS_ENABLED")
    os.environ["OPENAI_WEB_RAG_ANSWERS_ENABLED"] = "true" if use_llm else "false"
    chunk_owner = {
        chunk.get("chunk_id"): page.get("school_id")
        for page in index.get("pages", [])
        for chunk in page.get("chunks", [])
    }
    results = []
    try:
        for case in _answer_cases(index, labels):
            question = case["question"]
            if not any(marker in question.casefold() for marker in ("this school", "this preschool", "selected school", "selected preschool")):
                question = question.rstrip() + " For this school."
            turn = update_conversation(
                None,
                question,
                [{"school_id": case["school_id"], "name": case["school_name"]}],
                web_rag_index=index,
            )
            answer = str(turn.get("question") or "")
            folded = answer.casefold()
            citations = turn.get("citations") or []
            expected_evidence = bool(case.get("evidence_expected"))
            evidence_correct = bool(citations) == expected_evidence
            expected_terms = [str(term) for term in case.get("expected_terms", [])]
            terms_correct = not expected_terms or any(
                _expected_term_matches(answer, term) for term in expected_terms
            )
            forbidden_terms = [str(term).casefold() for term in case.get("forbidden_terms", [])]
            unsupported_claim_free = not any(term in folded for term in forbidden_terms)
            citations_complete = all(
                all(citation.get(field) for field in REQUIRED_CITATION_FIELDS)
                for citation in citations
            )
            school_isolated = all(
                chunk_owner.get(citation.get("chunk_id")) == case["school_id"]
                for citation in citations
            )
            concise = len(answer.split()) <= int(case.get("maximum_words", 60))
            passed = all((
                evidence_correct, terms_correct, unsupported_claim_free,
                citations_complete, school_isolated, concise,
            ))
            results.append({
                "case_id": case["case_id"], "passed": passed,
                "answer": answer, "answer_method": turn.get("web_answer_method"),
                "fallback_reason": turn.get("web_answer_fallback_reason"),
                "word_count": len(answer.split()), "citation_count": len(citations),
                "evidence_correct": evidence_correct, "terms_correct": terms_correct,
                "unsupported_claim_free": unsupported_claim_free,
                "citations_complete": citations_complete,
                "school_isolated": school_isolated, "concise": concise,
            })
    finally:
        if previous is None:
            os.environ.pop("OPENAI_WEB_RAG_ANSWERS_ENABLED", None)
        else:
            os.environ["OPENAI_WEB_RAG_ANSWERS_ENABLED"] = previous

    total = len(results)
    grounded = sum(item["answer_method"] == "llm_grounded" for item in results)
    fallbacks = sum(item["answer_method"] == "deterministic_fallback" for item in results)
    metrics = {
        "cases": total,
        "answer_accuracy": _rate(sum(item["passed"] for item in results), total),
        "evidence_availability_accuracy": _rate(sum(item["evidence_correct"] for item in results), total),
        "answer_content_accuracy": _rate(sum(item["terms_correct"] for item in results), total),
        "citation_validity": _rate(sum(item["citations_complete"] and item["school_isolated"] for item in results), total),
        "school_isolation": _rate(sum(item["school_isolated"] for item in results), total),
        "unsupported_claim_free_rate": _rate(sum(item["unsupported_claim_free"] for item in results), total),
        "conciseness_rate": _rate(sum(item["concise"] for item in results), total),
        "llm_grounded_rate": _rate(grounded, total),
        "fallback_rate": _rate(fallbacks, total),
    }
    gates = {
        "sample_size": metrics["cases"] >= thresholds["minimum_cases"],
        "answer_accuracy": metrics["answer_accuracy"] >= thresholds["answer_accuracy"],
        "citation_validity": metrics["citation_validity"] >= thresholds["citation_validity"],
        "unsupported_claim_free_rate": metrics["unsupported_claim_free_rate"] >= thresholds["unsupported_claim_free_rate"],
        "conciseness_rate": metrics["conciseness_rate"] >= thresholds["conciseness_rate"],
        "school_isolation": metrics["school_isolation"] >= thresholds["school_isolation"],
        "fallback_rate": (not use_llm) or metrics["fallback_rate"] <= thresholds["maximum_fallback_rate"],
    }
    return {
        "mode": "llm" if use_llm else "deterministic", "passed": all(gates.values()),
        "metrics": metrics, "thresholds": thresholds, "gates": gates, "results": results,
    }


def main() -> int:
    load_dotenv(POC_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    parser.add_argument("--labels", type=Path, default=POC_ROOT / "web_rag" / "production_audit_labels.json")
    parser.add_argument("--use-llm", action="store_true", help="Call the configured OpenAI model instead of forcing deterministic answers")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(load_json(args.index), load_json(args.labels), use_llm=args.use_llm)
    if args.output:
        save_json(args.output, report)
        print(f"Answer evaluation written to {args.output}")
    print(json.dumps({"mode": report["mode"], "passed": report["passed"], "metrics": report["metrics"], "gates": report["gates"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
