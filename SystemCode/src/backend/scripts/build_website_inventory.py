"""Build an offline, auditable school-webpage candidate inventory."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = POC_ROOT.parents[1] / "data" / "processed" / "poc1" / "kindercompass_master.json"
MISSING = {"", "na", "n/a", "none", "null", "-"}
TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
SOCIAL_DOMAINS = {"facebook.com", "www.facebook.com", "instagram.com", "www.instagram.com", "linkedin.com", "www.linkedin.com"}


def normalize_url(value: Any) -> tuple[str | None, str | None]:
    """Return a stable HTTP(S) URL and an error label when normalization fails."""
    if value is None or str(value).strip().lower() in MISSING:
        return None, "missing"
    raw = str(value).strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None, "invalid_url"
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None, "invalid_url"
    host = parts.hostname.lower().rstrip(".")
    try:
        port = parts.port
    except ValueError:
        return None, "invalid_port"
    netloc = host if port is None else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode([
        (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS and not key.lower().startswith(TRACKING_PREFIXES)
    ])
    return urlunsplit((parts.scheme.lower(), netloc, path, query, "")), None


def build_inventory(records: list[dict[str, Any]]) -> dict[str, Any]:
    provisional = []
    all_urls = []
    for record in records:
        candidates = []
        errors = []
        for field in ("centre_website", "website_lifesg"):
            normalized, error = normalize_url(record.get(field))
            if normalized and normalized not in candidates:
                candidates.append(normalized)
                all_urls.append(normalized)
            elif error and error != "missing":
                errors.append(f"{field}:{error}")
        provisional.append((record, candidates, errors))

    sharing = Counter(all_urls)
    rows = []
    for record, candidates, errors in provisional:
        selected = candidates[0] if candidates else None
        domain = urlsplit(selected).hostname if selected else None
        shared_count = sharing[selected] if selected else 0
        if not selected:
            scope = "unavailable"
        elif domain in SOCIAL_DOMAINS:
            scope = "social_page_candidate"
        elif shared_count > 1:
            scope = "shared_operator_page_candidate"
        else:
            scope = "school_specific_candidate"
        rows.append({
            "school_id": record.get("school_id"),
            "school_name": record.get("centre_name_x") or record.get("Name"),
            "postal_code": record.get("postal_code"),
            "raw_centre_website": record.get("centre_website"),
            "raw_lifesg_website": record.get("website_lifesg"),
            "candidate_urls": candidates,
            "selected_candidate_url": selected,
            "domain": domain,
            "schools_sharing_selected_url": shared_count,
            "scope": scope,
            "identity_status": "not_verified" if selected else "unavailable",
            "normalization_errors": errors,
        })

    scopes = Counter(row["scope"] for row in rows)
    domains = Counter(row["domain"] for row in rows if row["domain"])
    return {
        "methodology": "Offline candidate discovery only. No webpage was fetched and no school identity was verified.",
        "summary": {
            "total_schools": len(rows),
            "schools_with_candidates": sum(bool(row["selected_candidate_url"]) for row in rows),
            "schools_without_candidates": sum(not row["selected_candidate_url"] for row in rows),
            "unique_candidate_urls": len(set(all_urls)),
            "scope_counts": dict(sorted(scopes.items())),
            "normalization_error_count": sum(len(row["normalization_errors"]) for row in rows),
        },
        "top_domains": [{"domain": domain, "schools": count} for domain, count in domains.most_common(20)],
        "schools": rows,
    }


def to_csv(report: dict[str, Any]) -> str:
    fields = [
        "school_id", "school_name", "postal_code", "selected_candidate_url", "domain",
        "schools_sharing_selected_url", "scope", "identity_status", "candidate_urls", "normalization_errors",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in report["schools"]:
        rendered = {key: row.get(key) for key in fields}
        rendered["candidate_urls"] = " | ".join(row["candidate_urls"])
        rendered["normalization_errors"] = " | ".join(row["normalization_errors"])
        writer.writerow(rendered)
    return buffer.getvalue()


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# School website candidate inventory",
        "",
        report["methodology"],
        "",
        f"- Total schools: {summary['total_schools']:,}",
        f"- Schools with candidate URLs: {summary['schools_with_candidates']:,}",
        f"- Schools without candidate URLs: {summary['schools_without_candidates']:,}",
        f"- Unique candidate URLs: {summary['unique_candidate_urls']:,}",
        f"- Normalization errors: {summary['normalization_error_count']:,}",
        "",
        "## Candidate scope",
        "",
        "| Scope | Schools |",
        "|---|---:|",
    ]
    lines.extend(f"| {scope} | {count:,} |" for scope, count in summary["scope_counts"].items())
    lines.extend(["", "## Top domains", "", "| Domain | Schools |", "|---|---:|"])
    lines.extend(f"| {item['domain']} | {item['schools']:,} |" for item in report["top_domains"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--format", choices=("markdown", "json", "csv"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = args.input.resolve()
    records = json.loads(dataset.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("The dataset must be a JSON array of school objects")
    report = build_inventory(records)
    content = to_csv(report) if args.format == "csv" else json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Website inventory written to {args.output}")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
