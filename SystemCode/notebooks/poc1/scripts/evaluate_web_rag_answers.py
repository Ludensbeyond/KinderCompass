"""Evaluate deterministic or LLM-synthesised Phase 9 chat answers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from stage1.conversation import update_conversation
from stage1.web_rag import load_json, save_json


POC_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CITATION_FIELDS = ("url", "title", "retrieved_at", "chunk_id")


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0


def evaluate(index: dict[str, Any], labels: dict[str, Any], *, use_llm: bool = False) -> dict[str, Any]:
    previous = os.environ.get("OPENAI_WEB_RAG_ANSWERS_ENABLED")
    os.environ["OPENAI_WEB_RAG_ANSWERS_ENABLED"] = "true" if use_llm else "false"
    chunk_owner = {
        chunk.get("chunk_id"): page.get("school_id")
        for page in index.get("pages", [])
        for chunk in page.get("chunks", [])
    }
    results = []
    try:
        for case in labels.get("cases", []):
            turn = update_conversation(
                None,
                case["question"],
                [{"school_id": case["school_id"], "name": case["school_name"]}],
                web_rag_index=index,
            )
            answer = str(turn.get("question") or "")
            folded = answer.casefold()
            citations = turn.get("citations") or []
            expected_evidence = bool(case.get("evidence_expected"))
            evidence_correct = bool(citations) == expected_evidence
            expected_terms = [str(term).casefold() for term in case.get("expected_terms", [])]
            terms_correct = not expected_terms or any(term in folded for term in expected_terms)
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
        "citation_validity": _rate(sum(item["citations_complete"] and item["school_isolated"] for item in results), total),
        "unsupported_claim_free_rate": _rate(sum(item["unsupported_claim_free"] for item in results), total),
        "conciseness_rate": _rate(sum(item["concise"] for item in results), total),
        "llm_grounded_rate": _rate(grounded, total),
        "fallback_rate": _rate(fallbacks, total),
    }
    return {"mode": "llm" if use_llm else "deterministic", "passed": all(item["passed"] for item in results), "metrics": metrics, "results": results}


def main() -> int:
    load_dotenv(POC_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    parser.add_argument("--labels", type=Path, default=POC_ROOT / "web_rag" / "answer_quality_labels.json")
    parser.add_argument("--use-llm", action="store_true", help="Call the configured OpenAI model instead of forcing deterministic answers")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(load_json(args.index), load_json(args.labels), use_llm=args.use_llm)
    if args.output:
        save_json(args.output, report)
        print(f"Answer evaluation written to {args.output}")
    print(json.dumps({"mode": report["mode"], "passed": report["passed"], "metrics": report["metrics"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
