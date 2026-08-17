"""Fetch an approved Phase 9 allowlist and build a school-isolated pilot index."""

from __future__ import annotations

import argparse
from pathlib import Path

from stage1.web_rag import ingest_allowlist, load_json, save_json


POC_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", type=Path, default=POC_ROOT / "resources" / "web_rag" / "pilot_allowlist.json")
    parser.add_argument("--output", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    args = parser.parse_args()
    entries = load_json(args.allowlist)
    if not isinstance(entries, list):
        raise ValueError("Allowlist must be a JSON array")
    report = ingest_allowlist(entries, delay_seconds=max(0.0, args.delay_seconds))
    save_json(args.output, report)
    print(f"Indexed {len(report['pages'])} pages; {len(report['failures'])} failures")
    print(f"Pilot index written to {args.output}")
    return 0 if report["pages"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
