"""Run offline golden checks for the Phase 9 school-isolation and citation contract."""

from __future__ import annotations

import argparse
import json

from stage1.web_rag import retrieve, retrieve_operator_evidence


def evaluate() -> dict:
    index = {
        "purpose": "explanation_only",
        "pages": [
            {"school_id": "A", "chunks": [{
                "chunk_id": "A:hash:0", "school_id": "A", "text": "Outdoor play and a garden programme.",
                "source_url": "https://a.example/official", "title": "A official",
                "retrieved_at": "2026-08-10T00:00:00+00:00", "content_hash": "a" * 64,
            }]},
            {"school_id": "B", "chunks": [{
                "chunk_id": "B:hash:0", "school_id": "B", "text": "Outdoor robotics programme.",
                "source_url": "https://b.example/official", "title": "B official",
                "retrieved_at": "2026-08-10T00:00:00+00:00", "content_hash": "b" * 64,
            }]},
        ],
        "operator_pages": [{
            "operator_id": "OPERATOR_PAGE:shared", "linked_school_ids": ["A", "B"],
            "chunks": [{
                "chunk_id": "OPERATOR_PAGE:shared:hash:0", "operator_id": "OPERATOR_PAGE:shared",
                "school_id": None, "linked_school_ids": ["A", "B"], "evidence_scope": "operator",
                "text": "The operator describes a bilingual programme.",
                "source_url": "https://operator.example/about", "title": "Operator official",
                "retrieved_at": "2026-08-10T00:00:00+00:00", "content_hash": "c" * 64,
            }],
        }],
    }
    a_results = retrieve(index, "A", "outdoor robotics garden")
    missing_results = retrieve(index, "C", "outdoor")
    operator_results = retrieve_operator_evidence(index, "A", "bilingual programme")
    ranking_index = {"pages": [{"school_id": "R", "chunks": [
        {
            "chunk_id": "R:scattered", "school_id": "R", "text": "Outdoor spaces support play and learning.",
            "source_url": "https://r.example", "title": "R", "retrieved_at": "2026-08-10", "content_hash": "r",
        },
        {
            "chunk_id": "R:phrase", "school_id": "R", "text": "Children enjoy outdoor learning in our garden.",
            "source_url": "https://r.example", "title": "R", "retrieved_at": "2026-08-10", "content_hash": "r",
        },
    ]}]}
    ranked_results = retrieve(ranking_index, "R", "outdoor learning")
    checks = {
        "school_isolation": bool(a_results) and all(item["school_id"] == "A" for item in a_results),
        "no_cross_school_text": all("robotics" not in item["text"].lower() for item in a_results),
        "citations_complete": all(
            item.get("citation", {}).get(field)
            for item in a_results for field in ("url", "title", "retrieved_at", "chunk_id")
        ),
        "unavailable_evidence_is_empty": missing_results == [],
        "explanation_only_contract": index["purpose"] == "explanation_only",
        "operator_evidence_explicit": bool(operator_results) and all(
            item.get("evidence_scope") == "operator"
            and item.get("school_id") is None
            and "not verified" in item.get("claim_boundary", "")
            for item in operator_results
        ),
        "operator_evidence_not_in_school_results": all(
            item.get("school_id") == "A" and item.get("evidence_scope") != "operator"
            for item in retrieve(index, "A", "bilingual programme")
        ),
        "phrase_ranking": bool(ranked_results) and ranked_results[0]["chunk_id"] == "R:phrase",
        "synonym_retrieval": bool(retrieve(ranking_index, "R", "playground")),
        "weak_match_rejected": retrieve(
            ranking_index, "R", "outdoor bilingual fees transport robotics"
        ) == [],
    }
    return {"passed": all(checks.values()), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = evaluate()
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        for name, passed in report["checks"].items():
            print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
