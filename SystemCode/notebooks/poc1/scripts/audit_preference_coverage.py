"""Audit preschool data coverage for parent-facing preference attributes."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_DATASET = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "poc1"
    / "kindercompass_master.json"
)

FIELDS = {
    "care_levels": "Child's care level",
    "second_languages_offered": "Second language",
    "spark_certified": "SPARK certification",
    "operator_scheme": "Operator scheme",
    "provision_of_transport": "Transport",
    "food_offered": "Food policy",
    "weekday_full_day": "Full-day care",
    "pedagogy": "Pedagogy field",
    "philosophy": "Philosophy field",
    "base_fee": "Monthly base fee",
    "geometry": "Location geometry",
    "has_fee_data": "Fee coverage flag",
    "has_licence_data": "Licence coverage flag",
    "has_vacancy_data": "Vacancy coverage flag",
}

MISSING_STRINGS = {"", "na", "n/a", "none", "null"}


def is_informative(value: Any) -> bool:
    """Return whether a value represents available evidence."""
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return str(value).strip().lower() not in MISSING_STRINGS


def display_value(value: Any) -> str:
    """Produce a stable, compact value for distribution reporting."""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load and validate the master preschool JSON array."""
    with path.open(encoding="utf-8") as source:
        records = json.load(source)
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("The dataset must be a JSON array of school objects")
    return records


def audit(records: list[dict[str, Any]], top_values: int = 8) -> dict[str, Any]:
    """Calculate field coverage and common value distributions."""
    total = len(records)
    school_ids = [record.get("school_id") for record in records]
    usable_ids = [value for value in school_ids if is_informative(value)]
    duplicate_ids = sorted(value for value, count in Counter(usable_ids).items() if count > 1)

    fields = []
    for field, label in FIELDS.items():
        values = [record.get(field) for record in records if is_informative(record.get(field))]
        distribution = Counter(display_value(value) for value in values).most_common(top_values)
        fields.append(
            {
                "field": field,
                "label": label,
                "available": len(values),
                "missing": total - len(values),
                "coverage_percent": round((len(values) / total * 100) if total else 0, 1),
                "top_values": [{"value": value, "count": count} for value, count in distribution],
            }
        )

    specific_pedagogy = sum(
        str(record.get("pedagogy") or "").strip().lower()
        not in MISSING_STRINGS | {"general"}
        for record in records
    )
    return {
        "total_records": total,
        "unique_school_ids": len(set(usable_ids)),
        "missing_school_ids": total - len(usable_ids),
        "duplicate_school_ids": duplicate_ids,
        "specific_pedagogy_records": specific_pedagogy,
        "specific_pedagogy_percent": round((specific_pedagogy / total * 100) if total else 0, 1),
        "fields": fields,
    }


def to_markdown(report: dict[str, Any], dataset: Path) -> str:
    """Render a concise, reproducible Markdown coverage report."""
    lines = [
        "# Preference coverage statistics",
        "",
        f"Dataset: `{dataset}`",
        "",
        f"- Total records: {report['total_records']:,}",
        f"- Unique school IDs: {report['unique_school_ids']:,}",
        f"- Missing school IDs: {report['missing_school_ids']:,}",
        f"- Duplicate school IDs: {len(report['duplicate_school_ids']):,}",
        f"- Specific pedagogy evidence: {report['specific_pedagogy_records']:,} ({report['specific_pedagogy_percent']:.1f}%)",
        "",
        "| Preference evidence | Field | Available | Missing | Coverage |",
        "|---|---|---:|---:|---:|",
    ]
    for field in report["fields"]:
        lines.append(
            f"| {field['label']} | `{field['field']}` | {field['available']:,} | "
            f"{field['missing']:,} | {field['coverage_percent']:.1f}% |"
        )

    lines.extend(["", "## Most common values", ""])
    for field in report["fields"]:
        lines.extend([f"### {field['label']} (`{field['field']}`)", ""])
        if not field["top_values"]:
            lines.extend(["No informative values.", ""])
            continue
        lines.extend(["| Value | Count |", "|---|---:|"])
        for item in field["top_values"]:
            safe_value = item["value"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {safe_value} | {item['count']:,} |")
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET, help="Master preschool JSON file")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="Write the report to a file instead of standard output")
    parser.add_argument("--top-values", type=int, default=8, help="Number of common values per field")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top_values < 1:
        raise ValueError("--top-values must be at least 1")
    dataset = args.input.resolve()
    report = audit(load_records(dataset), args.top_values)
    content = (
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.format == "json"
        else to_markdown(report, dataset)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
