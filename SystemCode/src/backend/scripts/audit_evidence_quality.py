"""Audit source coverage, value states, derivation, and freshness of school evidence."""

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

from stage1.evidence import EVIDENCE_PROVENANCE, freshness  # noqa: E402


DEFAULT_DATASET = POC_ROOT.parents[1] / "data" / "processed" / "kindercompass_master.json"
FIELDS = {
    "language": "second_languages_offered",
    "spark_certified": "spark_certified",
    "transport": "provision_of_transport",
    "full_day": "weekday_full_day",
    "operator_scheme": "operator_scheme",
    "food": "food_offered",
    "pedagogy": "pedagogy",
}
MISSING = {"", "na", "n/a", "none", "null"}


def informative(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return str(value).strip().lower() not in MISSING


def audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = []
    invalid_provenance = []
    for attribute, field in FIELDS.items():
        provenance = EVIDENCE_PROVENANCE.get(attribute)
        if not provenance or not all(provenance.get(key) for key in ("source", "method", "reliability")):
            invalid_provenance.append(attribute)
            provenance = {"source": "Unknown source", "method": "unknown", "reliability": "unknown"}
        available = [
            record for record in records
            if informative(record.get(field))
            and not (attribute == "pedagogy" and str(record.get(field)).strip().lower() == "general")
        ]
        confirmed_no = sum(str(record.get(field)).strip().lower() == "no" for record in records)
        freshness_counts = {state: 0 for state in ("current", "stale", "future_dated", "unknown")}
        for record in available:
            freshness_counts[freshness(record.get("last_updated"))] += 1
        derived = len(available) if provenance["method"].startswith("derived") else 0
        fields.append({
            "attribute": attribute,
            "field": field,
            "source": provenance["source"],
            "method": provenance["method"],
            "reliability": provenance["reliability"],
            "available": len(available),
            "unknown": len(records) - len(available),
            "confirmed_no": confirmed_no,
            "derived": derived,
            "coverage_percent": round(len(available) / len(records) * 100, 1) if records else 0.0,
            "freshness": freshness_counts,
        })
    return {
        "total_records": len(records),
        "invalid_provenance_attributes": invalid_provenance,
        "fields": fields,
    }


def markdown(report: dict[str, Any], dataset: Path) -> str:
    lines = [
        "# Evidence quality audit",
        "",
        f"Dataset: `{dataset}`",
        "",
        f"- Total school records: {report['total_records']:,}",
        f"- Invalid provenance definitions: {len(report['invalid_provenance_attributes'])}",
        "",
        "| Attribute | Source | Method | Available | Unknown | Confirmed no | Derived | Current | Stale | Coverage |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["fields"]:
        lines.append(
            f"| {item['attribute']} | {item['source']} | {item['method']} | {item['available']:,} | "
            f"{item['unknown']:,} | {item['confirmed_no']:,} | {item['derived']:,} | "
            f"{item['freshness']['current']:,} | {item['freshness']['stale']:,} | {item['coverage_percent']:.1f}% |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = args.input.resolve()
    records = json.loads(dataset.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("The dataset must be a JSON array of school objects")
    report = audit(records)
    content = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else markdown(report, dataset)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Evidence audit written to {args.output}")
    else:
        print(content, end="")
    return 1 if report["invalid_provenance_attributes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
