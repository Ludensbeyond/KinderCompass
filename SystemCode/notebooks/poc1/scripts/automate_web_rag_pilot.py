"""Incrementally verify and ingest Phase 9 school and shared webpage candidates."""

from __future__ import annotations

import argparse
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from scripts.build_website_inventory import DEFAULT_DATASET, build_inventory
from stage1.web_rag import (
    PageContent,
    automate_allowlist,
    automate_shared_pages,
    fetch_page,
    fetch_page_with_browser_fallback,
    ingest_allowlist,
    ingest_operator_pages,
    load_json,
    refresh_due,
    save_json,
    webpage_freshness,
)


POC_ROOT = Path(__file__).resolve().parents[1]
SCHOOL_COMPLETE = {"approved", "approved_operator", "pending_review", "rejected"}
OPERATOR_COMPLETE = {"approved_operator"}


def _retry_deferred(decision: dict[str, Any] | None, now: datetime) -> bool:
    if not decision or decision.get("review_status") != "fetch_failed":
        return False
    if decision.get("retryable") is False:
        return True
    value = decision.get("next_retry_at")
    if not value:
        return False
    try:
        retry_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return now < retry_at.astimezone(timezone.utc)


def _apply_attempt_metadata(
    decision: dict[str, Any], previous: dict[str, Any] | None, now: datetime
) -> None:
    attempts = int((previous or {}).get("attempt_count") or 0) + 1
    decision["attempt_count"] = attempts
    if decision.get("review_status") != "fetch_failed":
        decision["next_retry_at"] = None
        return
    if decision.get("retryable") is False:
        decision["next_retry_at"] = None
        return
    base_delay = int(decision.get("retry_after_seconds") or 1800)
    delay = min(base_delay * (2 ** min(attempts - 1, 8)), 30 * 86400)
    decision["next_retry_at"] = (now + timedelta(seconds=delay)).isoformat()


def _load_list(path: Path, fresh: bool) -> list[dict[str, Any]]:
    if fresh or not path.exists():
        return []
    value = load_json(path)
    if not isinstance(value, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return value


def _empty_index() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "purpose": "explanation_only",
        "pages": [],
        "failures": [],
        "operator_pages": [],
        "operator_failures": [],
    }


def _load_index(path: Path, fresh: bool) -> dict[str, Any]:
    if fresh or not path.exists():
        return _empty_index()
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    base = _empty_index()
    base.update(value)
    return base


def _upsert(items: list[dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    expected = value.get(key)
    for index, item in enumerate(items):
        if item.get(key) == expected:
            items[index] = value
            return
    items.append(value)


def _replace_page(items: list[dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    items[:] = [item for item in items if item.get(key) != value.get(key)]
    items.append(value)


def run_incremental(
    records: list[dict[str, Any]],
    *,
    allowlist_path: Path,
    operator_allowlist_path: Path,
    output_path: Path,
    limit: int | None = None,
    shared_limit: int | None = None,
    delay_seconds: float = 1.0,
    fresh: bool = False,
    refresh_after_days: int = 30,
    school_ids: set[str] | None = None,
    now: datetime | None = None,
    fetcher: Callable[[str], PageContent] = fetch_page,
) -> dict[str, Any]:
    """Resume from checkpoints, saving decisions and index data after every attempt."""
    inventory = build_inventory(records)
    school_decisions = _load_list(allowlist_path, fresh)
    operator_decisions = _load_list(operator_allowlist_path, fresh)
    index = _load_index(output_path, fresh)
    school_candidates = [
        row for row in inventory["schools"] if row.get("scope") == "school_specific_candidate"
    ]
    grouped_shared: dict[str, list[dict[str, Any]]] = {}
    for row in inventory["schools"]:
        if row.get("scope") == "shared_operator_page_candidate" and row.get("selected_candidate_url"):
            grouped_shared.setdefault(row["selected_candidate_url"], []).append(row)
    active_school_ids = {row.get("school_id") for row in school_candidates}
    active_shared_urls = set(grouped_shared)
    school_decisions[:] = [item for item in school_decisions if item.get("school_id") in active_school_ids]
    operator_decisions[:] = [item for item in operator_decisions if item.get("url") in active_shared_urls]
    active_operator_ids = {item.get("operator_id") for item in operator_decisions}
    index["pages"][:] = [item for item in index["pages"] if item.get("school_id") in active_school_ids]
    index["operator_pages"][:] = [
        item for item in index["operator_pages"] if item.get("operator_id") in active_operator_ids
    ]
    school_by_id = {item.get("school_id"): item for item in school_decisions}
    operator_by_url = {item.get("url"): item for item in operator_decisions}
    indexed_schools = {item.get("school_id") for item in index["pages"]}
    indexed_operators = {item.get("operator_id") for item in index["operator_pages"]}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    checked_at = now.isoformat()
    refresh_after_days = max(0, refresh_after_days)
    for page_item in index["pages"] + index["operator_pages"]:
        page_item["freshness"] = webpage_freshness(page_item.get("retrieved_at"), now=now)

    delay_seconds = max(0.0, delay_seconds)
    school_attempts = school_skipped = operator_attempts = operator_skipped = 0
    last_host: str | None = None

    selected_school_candidates = [
        row for row in school_candidates
        if not school_ids or row.get("school_id") in school_ids
    ]
    for position, row in enumerate(selected_school_candidates, 1):
        school_id = row.get("school_id")
        existing = school_by_id.get(school_id)
        existing_page = next((item for item in index["pages"] if item.get("school_id") == school_id), None)
        due = bool(
            existing
            and existing.get("review_status") == "approved"
            and existing_page
            and refresh_due(existing_page.get("retrieved_at"), refresh_after_days, now=now)
        )
        complete = bool(
            existing and existing.get("url") == row.get("selected_candidate_url") and (
                (
                    existing.get("review_status") in SCHOOL_COMPLETE
                    and (existing.get("review_status") != "approved" or school_id in indexed_schools)
                    and not due
                )
                or _retry_deferred(existing, now)
            )
        )
        if complete and not school_ids:
            school_skipped += 1
            continue
        if limit is not None and school_attempts >= max(0, limit):
            break
        host = urlsplit(row["selected_candidate_url"]).hostname
        if delay_seconds and last_host == host:
            time.sleep(delay_seconds)
        decisions, fetched = automate_allowlist([row], records, fetcher=fetcher, limit=1, delay_seconds=0)
        if not decisions:
            continue
        decision = decisions[0]
        decision["last_checked_at"] = checked_at
        _apply_attempt_metadata(decision, existing, now)
        _upsert(school_decisions, "school_id", decision)
        school_by_id[school_id] = decision
        if decision["review_status"] == "approved":
            page_report = ingest_allowlist(
                [decision], fetcher=lambda url, pages=fetched: pages[url], delay_seconds=0
            )
            if page_report["pages"]:
                new_page = page_report["pages"][0]
                if existing_page and existing_page.get("source_url") != new_page.get("source_url"):
                    change_status = "redirected"
                elif existing_page and existing_page.get("content_hash") == new_page.get("content_hash"):
                    change_status = "unchanged"
                elif existing_page:
                    change_status = "changed"
                else:
                    change_status = "new"
                decision["change_status"] = change_status
                decision["previous_content_hash"] = existing_page.get("content_hash") if existing_page else None
                decision["current_content_hash"] = new_page.get("content_hash")
                decision["last_changed_at"] = (
                    existing.get("last_changed_at") if change_status == "unchanged" and existing else new_page["retrieved_at"]
                )
                new_page["change_status"] = change_status
                new_page["last_checked_at"] = checked_at
                new_page["freshness"] = webpage_freshness(new_page.get("retrieved_at"), now=now)
                _replace_page(index["pages"], "school_id", new_page)
                indexed_schools.add(school_id)
                _upsert(school_decisions, "school_id", decision)
        elif decision["review_status"] == "fetch_failed" and existing_page:
            decision["change_status"] = "unavailable"
            decision["last_successful_retrieval_at"] = existing_page.get("retrieved_at")
            existing_page["change_status"] = "unavailable"
            existing_page["last_checked_at"] = checked_at
            existing_page["last_refresh_error"] = decision.get("notes")
            existing_page["freshness"] = webpage_freshness(existing_page.get("retrieved_at"), now=now)
            _upsert(school_decisions, "school_id", decision)
        else:
            if existing_page:
                decision["change_status"] = "identity_changed"
                _upsert(school_decisions, "school_id", decision)
            index["pages"][:] = [item for item in index["pages"] if item.get("school_id") != school_id]
            indexed_schools.discard(school_id)
        save_json(allowlist_path, school_decisions)
        save_json(output_path, index)
        school_attempts += 1
        last_host = host
        print(f"School {position}/{len(selected_school_candidates)}: {school_id} -> {decision['review_status']}")

    last_host = None
    shared_groups = list(grouped_shared.items())
    for position, (url, rows) in enumerate(shared_groups, 1):
        existing = operator_by_url.get(url)
        existing_page = next(
            (item for item in index["operator_pages"] if item.get("operator_id") == (existing or {}).get("operator_id")),
            None,
        )
        due = bool(
            existing
            and existing.get("review_status") == "approved_operator"
            and existing_page
            and refresh_due(existing_page.get("retrieved_at"), refresh_after_days, now=now)
        )
        complete = bool(
            existing and (
                (
                    existing.get("review_status") in OPERATOR_COMPLETE
                    and existing.get("operator_id") in indexed_operators
                    and not due
                )
                or _retry_deferred(existing, now)
            )
        )
        if complete:
            operator_skipped += 1
            continue
        if shared_limit is not None and operator_attempts >= max(0, shared_limit):
            break
        host = urlsplit(url).hostname
        if delay_seconds and last_host == host:
            time.sleep(delay_seconds)
        decisions, fetched = automate_shared_pages(rows, fetcher=fetcher, limit=1, delay_seconds=0)
        if not decisions:
            continue
        decision = decisions[0]
        decision["last_checked_at"] = checked_at
        _apply_attempt_metadata(decision, existing, now)
        _upsert(operator_decisions, "url", decision)
        operator_by_url[url] = decision
        if decision["review_status"] == "approved_operator":
            pages, failures = ingest_operator_pages(
                [decision], fetcher=lambda value, fetched_pages=fetched: fetched_pages[value]
            )
            if pages:
                new_page = pages[0]
                if existing_page and existing_page.get("source_url") != new_page.get("source_url"):
                    change_status = "redirected"
                elif existing_page and existing_page.get("content_hash") == new_page.get("content_hash"):
                    change_status = "unchanged"
                elif existing_page:
                    change_status = "changed"
                else:
                    change_status = "new"
                decision["change_status"] = change_status
                decision["previous_content_hash"] = existing_page.get("content_hash") if existing_page else None
                decision["current_content_hash"] = new_page.get("content_hash")
                decision["last_changed_at"] = (
                    existing.get("last_changed_at") if change_status == "unchanged" and existing else new_page["retrieved_at"]
                )
                new_page["change_status"] = change_status
                new_page["last_checked_at"] = checked_at
                new_page["freshness"] = webpage_freshness(new_page.get("retrieved_at"), now=now)
                _replace_page(index["operator_pages"], "operator_id", new_page)
                indexed_operators.add(decision["operator_id"])
                _upsert(operator_decisions, "url", decision)
            index["operator_failures"] = [
                item for item in index["operator_failures"] if item.get("operator_id") != decision["operator_id"]
            ] + failures
        elif decision["review_status"] == "fetch_failed" and existing_page:
            decision["change_status"] = "unavailable"
            decision["last_successful_retrieval_at"] = existing_page.get("retrieved_at")
            existing_page["change_status"] = "unavailable"
            existing_page["last_checked_at"] = checked_at
            existing_page["last_refresh_error"] = decision.get("notes")
            existing_page["freshness"] = webpage_freshness(existing_page.get("retrieved_at"), now=now)
            _upsert(operator_decisions, "url", decision)
        save_json(operator_allowlist_path, operator_decisions)
        save_json(output_path, index)
        operator_attempts += 1
        last_host = host
        print(f"Shared {position}/{len(shared_groups)}: {url} -> {decision['review_status']}")

    # Ensure empty checkpoint files are created even when limits are zero.
    save_json(allowlist_path, school_decisions)
    save_json(operator_allowlist_path, operator_decisions)
    save_json(output_path, index)
    return {
        "school_attempts": school_attempts,
        "school_skipped": school_skipped,
        "operator_attempts": operator_attempts,
        "operator_skipped": operator_skipped,
        "school_decisions": school_decisions,
        "operator_decisions": operator_decisions,
        "index": index,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum new school-specific pages to attempt; omit to finish all pending candidates",
    )
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--allowlist", type=Path, default=POC_ROOT / "web_rag" / "pilot_allowlist.json")
    parser.add_argument(
        "--shared-limit", type=int, default=None,
        help="Maximum new shared pages to attempt; omit to finish all pending shared pages",
    )
    parser.add_argument(
        "--operator-allowlist", type=Path,
        default=POC_ROOT / "web_rag" / "operator_page_allowlist.json",
    )
    parser.add_argument("--output", type=Path, default=POC_ROOT / "output" / "web_rag_pilot_index.json")
    parser.add_argument(
        "--refresh-after-days", type=int, default=30,
        help="Refresh approved indexed pages at or beyond this age; use 0 to force a check",
    )
    parser.add_argument("--fresh", action="store_true", help="Discard existing checkpoints and rebuild from scratch")
    parser.add_argument(
        "--school-id", action="append", default=[],
        help="Reprocess only this school ID; repeat for multiple IDs without pruning other checkpoints",
    )
    parser.add_argument(
        "--browser-fallback", action="store_true",
        help="Render only policy-allowed pages whose ordinary HTML has no readable text",
    )
    args = parser.parse_args()
    records = load_json(args.input)
    if not isinstance(records, list):
        raise ValueError("Catalogue must be a JSON array")
    result = run_incremental(
        records,
        allowlist_path=args.allowlist,
        operator_allowlist_path=args.operator_allowlist,
        output_path=args.output,
        limit=args.limit,
        shared_limit=args.shared_limit,
        delay_seconds=args.delay_seconds,
        fresh=args.fresh,
        refresh_after_days=max(0, args.refresh_after_days),
        school_ids=set(args.school_id) or None,
        fetcher=fetch_page_with_browser_fallback if args.browser_fallback else fetch_page,
    )
    school_counts = Counter(item["review_status"] for item in result["school_decisions"])
    operator_counts = Counter(item["review_status"] for item in result["operator_decisions"])
    change_counts = Counter(
        item.get("change_status") for item in result["school_decisions"] + result["operator_decisions"]
        if item.get("change_status")
    )
    freshness_counts = Counter(
        item.get("freshness") for item in result["index"]["pages"] + result["index"]["operator_pages"]
        if item.get("freshness")
    )
    failure_counts = Counter(
        item.get("failure_code") for item in result["school_decisions"] + result["operator_decisions"]
        if item.get("review_status") == "fetch_failed"
    )
    print("Verification: " + ", ".join(f"{key}={value}" for key, value in sorted(school_counts.items())))
    print("Shared pages: " + ", ".join(f"{key}={value}" for key, value in sorted(operator_counts.items())))
    print("Page changes: " + (", ".join(f"{key}={value}" for key, value in sorted(change_counts.items())) or "none"))
    print("Freshness: " + (", ".join(f"{key}={value}" for key, value in sorted(freshness_counts.items())) or "none"))
    print("Failures: " + (", ".join(f"{key}={value}" for key, value in sorted(failure_counts.items())) or "none"))
    print(
        f"This run: attempted {result['school_attempts']} school pages and {result['operator_attempts']} shared pages; "
        f"skipped {result['school_skipped']} completed school pages and {result['operator_skipped']} completed shared pages"
    )
    print(f"Indexed {len(result['index']['pages'])} school pages and {len(result['index']['operator_pages'])} operator pages")
    return 0 if result["index"]["pages"] or result["index"]["operator_pages"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
