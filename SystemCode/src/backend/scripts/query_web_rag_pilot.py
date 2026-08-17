"""Query the explanation-only Phase 9 pilot index for one school."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stage1.web_rag import load_json, retrieve, retrieve_operator_evidence


POC_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    parser.add_argument("--school-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--min-relevance", type=float, default=0.25)
    parser.add_argument(
        "--include-operator",
        action="store_true",
        help="Also return clearly labelled operator-level evidence linked to this school",
    )
    args = parser.parse_args()
    index = load_json(args.index)
    results = retrieve(
        index, args.school_id, args.query, limit=args.limit,
        min_relevance=max(0.0, min(1.0, args.min_relevance)),
    )
    for item in results:
        print(f"[{item['citation']['chunk_id']}] {item['citation']['title']}")
        print(
            f"Relevance {item['relevance']:.0%}; matched: "
            + ", ".join(item["matched_query_terms"])
            + ("; phrase match" if item["phrase_match"] else "")
        )
        print(item["text"])
        print(item["citation"]["url"])
        print()
    if not results:
        print("No cited evidence available for this school and query.")
    if args.include_operator:
        operator_results = retrieve_operator_evidence(
            index, args.school_id, args.query, limit=args.limit,
            min_relevance=max(0.0, min(1.0, args.min_relevance)),
        )
        for item in operator_results:
            print(f"[OPERATOR LEVEL: {item['citation']['chunk_id']}] {item['citation']['title']}")
            print(item["claim_boundary"])
            print(
                f"Relevance {item['relevance']:.0%}; matched: "
                + ", ".join(item["matched_query_terms"])
                + ("; phrase match" if item["phrase_match"] else "")
            )
            print(item["text"])
            print(item["citation"]["url"])
            print()
        if not operator_results:
            print("No operator-level evidence available for this school and query.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
