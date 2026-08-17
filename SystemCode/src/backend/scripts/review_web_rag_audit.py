"""Export human-review CSV packets and import validated Phase 9 audit labels."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from stage1.web_rag import load_json, retrieve, retrieve_operator_evidence, save_json


POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_DIR = POC_ROOT / "output" / "web_rag_review"
ALLOWED_STATUSES = {"approved", "pending_review", "rejected", "fetch_failed", "approved_operator"}
ALLOWED_IDENTITIES = {"school", "operator", "incorrect", "ambiguous", "unverified"}
STATUS_IDENTITY = {
    "approved": "school", "approved_operator": "operator", "rejected": "incorrect",
    "pending_review": "ambiguous", "fetch_failed": "unverified",
}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
TOPICS = (
    ("outdoor", "Does this preschool describe outdoor learning or outdoor facilities?", ("outdoor", "garden", "playground")),
    ("curriculum", "What curriculum or teaching approach does this preschool describe?", ("curriculum", "programme", "framework", "approach")),
    ("language", "What language-learning opportunities are described?", ("language", "bilingual", "mandarin", "chinese", "english")),
    ("fees", "What does the page say about fees or subsidies?", ("fee", "fees", "subsidy", "cost")),
    ("enrichment", "What enrichment activities or programmes are described?", ("enrichment", "music", "art", "drama")),
    ("philosophy", "What learning philosophy does the page describe?", ("philosophy", "vision", "believe", "learning")),
    ("facilities", "What facilities or learning environment are described?", ("facility", "facilities", "classroom", "environment")),
)


def _safe_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite review file: {path}; pass --overwrite explicitly")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _safe_cell(row.get(field)) for field in fields})


def _matched_identifiers(decision: dict[str, Any]) -> str:
    return " | ".join(
        str(item.get("type")) for item in decision.get("identity_matches", []) if item.get("matched") is True
    )


def export_packets(
    index: dict[str, Any],
    school_decisions: list[dict[str, Any]],
    operator_decisions: list[dict[str, Any]],
    *,
    identity_path: Path,
    retrieval_path: Path,
    overwrite: bool = False,
) -> dict[str, int]:
    identity_rows = []
    for decision in school_decisions:
        identity_rows.append({
            "case_id": f"identity-school-{str(decision.get('school_id', '')).replace(':', '-').lower()}",
            "evidence_scope": "school", "school_id": decision.get("school_id"),
            "school_name": decision.get("school_name"), "url": decision.get("url"),
            "automated_status": decision.get("review_status"),
            "identity_confidence": decision.get("identity_confidence"),
            "matched_identifiers": _matched_identifiers(decision),
            "failure_code": decision.get("failure_code"), "automated_notes": decision.get("notes"),
            "include_in_audit": "", "human_expected_identity": "", "human_expected_status": "", "reviewer_notes": "",
        })
    for decision in operator_decisions:
        identity_rows.append({
            "case_id": f"identity-operator-{decision.get('operator_id', '').replace(':', '-').lower()}",
            "evidence_scope": "operator", "school_id": "", "school_name": decision.get("operator_name"),
            "url": decision.get("url"), "automated_status": decision.get("review_status"),
            "identity_confidence": "operator_level", "matched_identifiers": "shared catalogue URL",
            "failure_code": decision.get("failure_code"), "automated_notes": decision.get("notes"),
            "include_in_audit": "", "human_expected_identity": "", "human_expected_status": "", "reviewer_notes": "",
        })

    retrieval_rows = []
    for scope, pages in (("school", index.get("pages", [])), ("operator", index.get("operator_pages", []))):
        for page in pages:
            combined = " ".join(chunk.get("text", "") for chunk in page.get("chunks", [])).casefold()
            school_id = page.get("school_id") if scope == "school" else next(iter(page.get("linked_school_ids", [])), None)
            if not school_id:
                continue
            suggestions = [(key, question) for key, question, terms in TOPICS if any(term in combined for term in terms)][:3]
            if not suggestions:
                suggestions = [("programme", "What programme information does this webpage provide?")]
            for topic, question in suggestions:
                results = (
                    retrieve(index, school_id, question, limit=1, min_relevance=0.2)
                    if scope == "school"
                    else retrieve_operator_evidence(index, school_id, question, limit=1, min_relevance=0.2)
                )
                top = results[0] if results else None
                identity = school_id.replace(":", "-").lower()
                retrieval_rows.append({
                    "case_id": f"retrieval-{scope}-{identity}-{topic}", "school_id": school_id,
                    "automated_scope": scope, "suggested_query": question,
                    "retrieved_passage": top.get("text") if top else "",
                    "source_url": top.get("source_url") if top else page.get("source_url"),
                    "relevance": top.get("relevance") if top else "",
                    "matched_query_terms": " | ".join(top.get("matched_query_terms", [])) if top else "",
                    "include_in_audit": "", "human_query": "", "human_expected_scope": "",
                    "human_evidence_expected": "", "human_expected_terms": "",
                    "human_expected_source_contains": "", "reviewer_notes": "",
                })

    identity_fields = [
        "case_id", "evidence_scope", "school_id", "school_name", "url", "automated_status",
        "identity_confidence", "matched_identifiers", "failure_code", "automated_notes",
        "include_in_audit", "human_expected_identity", "human_expected_status", "reviewer_notes",
    ]
    retrieval_fields = [
        "case_id", "school_id", "automated_scope", "suggested_query", "retrieved_passage",
        "source_url", "relevance", "matched_query_terms", "include_in_audit", "human_query",
        "human_expected_scope", "human_evidence_expected", "human_expected_terms",
        "human_expected_source_contains", "reviewer_notes",
    ]
    _write_csv(identity_path, identity_fields, identity_rows, overwrite)
    _write_csv(retrieval_path, retrieval_fields, retrieval_rows, overwrite)
    return {"identity_rows": len(identity_rows), "retrieval_rows": len(retrieval_rows)}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _included(value: str) -> bool:
    return value.strip().casefold() in TRUE_VALUES


def _parse_bool(value: str, field: str, case_id: str) -> bool:
    normalised = value.strip().casefold()
    if normalised in TRUE_VALUES:
        return True
    if normalised in FALSE_VALUES:
        return False
    raise ValueError(f"{case_id}: {field} must be yes or no")


def import_packets(
    identity_path: Path, retrieval_path: Path, labels_path: Path
) -> dict[str, int]:
    labels = load_json(labels_path) if labels_path.exists() else {"identity_cases": [], "retrieval_cases": []}
    identity_cases = {}
    for item in labels.get("identity_cases", []):
        normalised = dict(item)
        if "expected_identity" not in normalised:
            normalised["expected_identity"] = STATUS_IDENTITY.get(
                normalised.pop("expected_status", ""), "unverified"
            )
        identity_cases[normalised["case_id"]] = normalised
    retrieval_cases = {item["case_id"]: item for item in labels.get("retrieval_cases", [])}
    imported_identity = imported_retrieval = 0
    for row in _read_csv(identity_path):
        if not _included(row.get("include_in_audit", "")):
            continue
        case_id = row.get("case_id", "").strip()
        expected_status = row.get("human_expected_status", "").strip()
        expected_identity = row.get("human_expected_identity", "").strip()
        if not expected_identity:
            if expected_status not in ALLOWED_STATUSES:
                raise ValueError(f"{case_id}: identity or valid legacy status is required")
            expected_identity = STATUS_IDENTITY[expected_status]
        if expected_identity not in ALLOWED_IDENTITIES:
            raise ValueError(f"{case_id}: invalid human_expected_identity {expected_identity!r}")
        scope = row.get("evidence_scope", "").strip()
        case = {"case_id": case_id, "evidence_scope": scope, "expected_identity": expected_identity}
        if scope == "school":
            case["school_id"] = row.get("school_id", "").strip()
            if not case["school_id"]:
                raise ValueError(f"{case_id}: school_id is required")
        elif scope == "operator":
            case["url"] = row.get("url", "").strip()
            if not case["url"]:
                raise ValueError(f"{case_id}: url is required")
        else:
            raise ValueError(f"{case_id}: invalid evidence_scope {scope!r}")
        identity_cases[case_id] = case
        imported_identity += 1

    for row in _read_csv(retrieval_path):
        if not _included(row.get("include_in_audit", "")):
            continue
        case_id = row.get("case_id", "").strip()
        scope = (row.get("human_expected_scope") or row.get("automated_scope") or "").strip()
        if scope not in {"school", "operator"}:
            raise ValueError(f"{case_id}: expected scope must be school or operator")
        query = (row.get("human_query") or row.get("suggested_query") or "").strip()
        school_id = row.get("school_id", "").strip()
        if not query or not school_id:
            raise ValueError(f"{case_id}: school_id and query are required")
        evidence_expected = _parse_bool(row.get("human_evidence_expected", ""), "human_evidence_expected", case_id)
        terms = [term.strip() for term in re.split(r"[|,]", row.get("human_expected_terms", "")) if term.strip()]
        if evidence_expected and not terms:
            raise ValueError(f"{case_id}: positive evidence requires at least one human_expected_term")
        retrieval_cases[case_id] = {
            "case_id": case_id, "school_id": school_id, "query": query,
            "expected_scope": scope, "evidence_expected": evidence_expected,
            "expected_terms": terms,
            "expected_source_contains": row.get("human_expected_source_contains", "").strip(),
        }
        imported_retrieval += 1

    save_json(labels_path, {
        "identity_cases": list(identity_cases.values()),
        "retrieval_cases": list(retrieval_cases.values()),
    })
    return {"identity_imported": imported_identity, "retrieval_imported": imported_retrieval}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--index", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    export_parser.add_argument("--school-decisions", type=Path, default=POC_ROOT / "web_rag" / "pilot_allowlist.json")
    export_parser.add_argument("--operator-decisions", type=Path, default=POC_ROOT / "web_rag" / "operator_page_allowlist.json")
    export_parser.add_argument("--output-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    export_parser.add_argument("--overwrite", action="store_true")
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--input-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    import_parser.add_argument("--labels", type=Path, default=POC_ROOT / "web_rag" / "production_audit_labels.json")
    args = parser.parse_args()
    if args.command == "export":
        result = export_packets(
            load_json(args.index), load_json(args.school_decisions), load_json(args.operator_decisions),
            identity_path=args.output_dir / "identity_review.csv",
            retrieval_path=args.output_dir / "retrieval_review.csv", overwrite=args.overwrite,
        )
    else:
        result = import_packets(
            args.input_dir / "identity_review.csv", args.input_dir / "retrieval_review.csv", args.labels
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
