"""Evaluate Stage 1 against competency questions and labelled graph queries.

Run from the repository root:

    $env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
    .venv\\Scripts\\python.exe SystemCode/src/backend/scripts/evaluate_stage1_graph.py

Offline shape checks always run. Live Neo4j precision/recall runs unless
--offline is set. Gold sets are independent canonical Cypher, not query_builder.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
PIPELINE = BACKEND / "pipeline"
for path in (str(BACKEND), str(PIPELINE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from stage1.graph_evaluation import (  # noqa: E402
    combine_report,
    evaluate_live,
    evaluate_offline,
    load_labels,
    markdown,
)
from stage1.kg_client import get_driver, run_query, verify_connectivity  # noqa: E402


DEFAULT_OUTPUT = BACKEND / "output" / "stage1_graph_evaluation.json"


def _live(labels) -> dict:
    driver = get_driver()
    verify_connectivity(driver)

    def execute(query, params=None):
        return run_query(driver, query, params or {})

    try:
        return evaluate_live(execute, labels)
    finally:
        driver.close()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--offline", action="store_true", help="Skip the live Neo4j run")
    args = parser.parse_args()

    labels = load_labels(args.labels)
    offline = evaluate_offline(labels)
    live = None
    if not args.offline:
        try:
            live = _live(labels)
        except Exception as exc:
            live = {
                "live": True,
                "passed": False,
                "error": str(exc),
                "preschool_count": 0,
                "failed_ids": ["neo4j_unavailable"],
                "macro": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
                "multi_hop_success_rate": 0.0,
                "provenance_complete_rate": 0.0,
                "cases": [],
            }

    report = combine_report(offline, live)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Evaluation report written to {args.output}")
    print(markdown(report) if args.format == "markdown" else rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
