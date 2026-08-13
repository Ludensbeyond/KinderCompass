"""Auditable, school-isolated webpage retrieval for the Phase 9 pilot."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import socket
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener
from urllib.robotparser import RobotFileParser


USER_AGENT = "KinderCompassResearchBot/0.1 (Phase 9 pilot; explanation-only)"
MAX_RESPONSE_BYTES = 2_000_000
MIN_IDENTITY_MATCHES = 2
ALLOWED_IDENTIFIERS = {"school_name", "address", "postal_code", "centre_code", "operator_domain"}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "has", "have", "how", "i", "in", "is", "it", "me", "my", "of",
    "on", "or", "our", "s", "school", "that", "the", "their", "there", "this", "to", "we",
    "what", "when", "where", "which", "with", "would", "you", "your", "kind", "much", "preschool",
}
SYNONYM_GROUPS = (
    {"outdoor", "garden", "playground"},
    {"curriculum", "programme", "program", "framework", "approach"},
    {"handson", "experiential", "activitybased"},
    {"fee", "cost", "price", "tuition"},
    {"bilingual", "duallanguage"},
    {"language", "english", "chinese", "mandarin", "malay", "tamil", "bahasa", "bilingual", "trilingual"},
    {"method", "philosophy", "believe", "learnercentred", "inquiry", "playbased"},
)
GENERIC_NAME_TOKENS = {
    "and", "at", "childcare", "child", "care", "centre", "center", "company",
    "kindergarten", "limited", "ltd", "pte", "preschool", "school", "singapore",
}
ADDRESS_NOISE_TOKENS = {"singapore", "level", "unit"}
LANGUAGE_EVIDENCE = {
    "english", "chinese", "mandarin", "malay", "tamil", "bahasa", "bilingual",
    "trilingual", "duallanguage", "language", "languages", "mothertongue",
}
FEE_EVIDENCE = {"fee", "cost", "price", "tuition", "subsidy", "subsidies", "month", "monthly"}
CURRICULUM_EVIDENCE = {
    "curriculum", "montessori", "reggio", "playbased", "inquiry", "literaturebased",
    "activitybased", "constructivism", "pedagogy",
}
ENRICHMENT_EVIDENCE = {
    "enrichment", "robotic", "zumba", "abacus", "music", "art", "drama", "dance",
    "scientist", "fieldtrip",
}
FACILITY_EVIDENCE = {
    "facility", "classroom", "playground", "garden", "indoor", "outdoor", "space", "room",
}


class PilotError(ValueError):
    """Raised when a pilot safety or validation boundary is violated."""


class FetchError(PilotError):
    """A classified webpage failure with an explicit retry policy."""

    def __init__(
        self, code: str, message: str, *, retryable: bool, retry_after_seconds: int | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


def failure_metadata(error: PilotError) -> dict[str, Any]:
    return {
        "failure_code": getattr(error, "code", "fetch_error"),
        "retryable": bool(getattr(error, "retryable", True)),
        "retry_after_seconds": getattr(error, "retry_after_seconds", None),
    }


@dataclass(frozen=True)
class PageContent:
    requested_url: str
    final_url: str
    title: str
    text: str
    retrieved_at: str
    content_hash: str
    identity_text: str | None = None


class _MainTextParser(HTMLParser):
    BLOCKED = {
        "script", "style", "noscript", "svg", "canvas", "template", "nav", "footer",
        "header", "aside", "form", "dialog",
    }
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    NOISY_CONTAINER_RE = re.compile(
        r"(?:^|[-_\s])(cookie|consent|privacy|popup|modal|navigation|navbar|menu|footer|"
        r"social|share|testimonials?|reviews?|related|carousel|breadcrumb)(?:$|[-_\s])",
        re.I,
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self._title_depth = 0
        self._preferred_depth = 0
        self._stack: list[tuple[str, bool, bool]] = []
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.preferred_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {key.lower(): str(value or "") for key, value in attrs}
        marker = " ".join((attributes.get("id", ""), attributes.get("class", ""), attributes.get("role", "")))
        added_block = tag in self.BLOCKED or bool(self.NOISY_CONTAINER_RE.search(marker))
        added_preferred = tag in {"main", "article"}
        if added_block:
            self._blocked_depth += 1
        if added_preferred:
            self._preferred_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag not in self.VOID:
            self._stack.append((tag, added_block, added_preferred))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] != tag:
                continue
            closing = self._stack[index:]
            del self._stack[index:]
            self._blocked_depth = max(0, self._blocked_depth - sum(item[1] for item in closing))
            self._preferred_depth = max(0, self._preferred_depth - sum(item[2] for item in closing))
            break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean:
            return
        if self._title_depth:
            self.title_parts.append(clean)
        if not self._blocked_depth and not self._title_depth:
            self.text_parts.append(clean)
            if self._preferred_depth:
                self.preferred_parts.append(clean)


UI_NOISE = {
    "accept all", "back to top", "close", "close menu", "cookie settings", "enquire now",
    "get directions", "learn more", "manage consent", "menu", "read more", "save & accept",
    "search", "skip to content", "skip to main content", "view all", "view all centres",
}


def _clean_text_parts(parts: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        value = " ".join(part.split()).strip(" |\t\r\n")
        key = value.casefold()
        if not value or key in UI_NOISE or key in seen:
            continue
        if re.fullmatch(r"[❮❯×+\-–—•·|\s]+", value):
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def extract_html(html: str) -> tuple[str, str]:
    parser = _MainTextParser()
    parser.feed(html)
    title = " ".join(parser.title_parts).strip()
    preferred = _clean_text_parts(parser.preferred_parts)
    all_text = _clean_text_parts(parser.text_parts)
    selected = preferred if len(" ".join(preferred).split()) >= 40 else all_text
    text = "\n".join(selected)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title, text


def validate_allowlist(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    approved: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        school_id = str(entry.get("school_id") or "").strip()
        url = str(entry.get("url") or "").strip()
        status = entry.get("review_status")
        if not school_id or not url:
            raise PilotError(f"Allowlist entry {index} requires school_id and url")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise PilotError(f"Allowlist entry {school_id} must use an absolute HTTPS URL")
        key = (school_id, url)
        if key in seen:
            raise PilotError(f"Duplicate allowlist entry: {school_id} {url}")
        seen.add(key)
        if status != "approved":
            continue
        matches = entry.get("identity_matches") or []
        types = {match.get("type") for match in matches if match.get("matched") is True}
        invalid = types - ALLOWED_IDENTIFIERS
        if invalid:
            raise PilotError(f"Unsupported identity identifiers for {school_id}: {sorted(invalid)}")
        if len(types) < MIN_IDENTITY_MATCHES:
            raise PilotError(f"Approved entry {school_id} requires two distinct matched identifiers")
        approved.append(entry)
    return approved


def _normalised_tokens(value: Any) -> set[str]:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return set(TOKEN_RE.findall(text.lower()))


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def webpage_freshness(
    retrieved_at: Any,
    *,
    now: datetime | None = None,
    current_days: int = 30,
    stale_days: int = 90,
) -> str:
    """Classify webpage evidence age without implying that its claims are still correct."""
    retrieved = _parse_timestamp(retrieved_at)
    if retrieved is None:
        return "unknown"
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_days = max(0, (now - retrieved).days)
    if age_days <= current_days:
        return "current"
    if age_days <= stale_days:
        return "aging"
    return "stale"


def refresh_due(retrieved_at: Any, after_days: int, *, now: datetime | None = None) -> bool:
    retrieved = _parse_timestamp(retrieved_at)
    if retrieved is None:
        return True
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return now >= retrieved and (now - retrieved).total_seconds() >= max(0, after_days) * 86400


def _token_similarity(expected: Any, observed: Any, *, ignored: set[str] | None = None) -> float:
    ignored = ignored or set()
    expected_tokens = _normalised_tokens(expected) - ignored
    observed_tokens = _normalised_tokens(observed) - ignored
    if not expected_tokens:
        return 0.0
    return len(expected_tokens & observed_tokens) / len(expected_tokens)


def _name_acronym(value: Any) -> str:
    leading = re.match(r"\s*([A-Z]{3,})\b", str(value))
    if leading:
        return leading.group(1).casefold()
    tokens = [token for token in re.findall(r"[a-z0-9]+", str(value).casefold())
              if token not in GENERIC_NAME_TOKENS and len(token) > 1]
    return "".join(token[0] for token in tokens)


def verify_school_identity(record: dict[str, Any], page: PageContent, url: str) -> dict[str, Any]:
    """Create an auditable allowlist decision from deterministic identifier matches."""
    searchable = f"{page.title}\n{page.identity_text or page.text}"
    text_tokens = _normalised_tokens(searchable)
    centre_code = str(record.get("centre_code") or "").strip()
    postal_code = str(record.get("postal_code") or "").strip()
    school_name = record.get("centre_name_x") or record.get("Name") or record.get("school_name") or ""
    address = record.get("centre_address") or record.get("address") or ""
    raw_expected_url = str(record.get("centre_website") or url).strip()
    if raw_expected_url and "://" not in raw_expected_url:
        raw_expected_url = f"https://{raw_expected_url}"
    expected_domain = urlsplit(raw_expected_url).hostname or ""
    final_domain = urlsplit(page.final_url).hostname or ""

    centre_code_match = bool(centre_code and centre_code.lower() not in {"na", "n/a"} and centre_code.lower() in text_tokens)
    postal_match = bool(re.fullmatch(r"\d{6}", postal_code) and postal_code in searchable)
    name_similarity = _token_similarity(school_name, searchable, ignored=GENERIC_NAME_TOKENS)
    address_without_postal = re.sub(r"\b\d{6}\b", " ", str(address))
    address_similarity = _token_similarity(address_without_postal, searchable, ignored=ADDRESS_NOISE_TOKENS)
    domain_match = expected_domain.lower().removeprefix("www.") == final_domain.lower().removeprefix("www.")

    name_match = name_similarity >= 0.75
    address_match = bool(address_without_postal.strip()) and address_similarity >= 0.75
    matches = [
        {"type": "centre_code", "expected": centre_code, "observed": centre_code if centre_code_match else None,
         "matched": centre_code_match, "similarity": 1.0 if centre_code_match else 0.0},
        {"type": "postal_code", "expected": postal_code, "observed": postal_code if postal_match else None,
         "matched": postal_match, "similarity": 1.0 if postal_match else 0.0},
        {"type": "school_name", "expected": school_name, "observed": page.title,
         "matched": name_match, "similarity": round(name_similarity, 3)},
        {"type": "address", "expected": address, "observed": "matched in page text" if address_match else None,
         "matched": address_match, "similarity": round(address_similarity, 3)},
        {"type": "operator_domain", "expected": expected_domain, "observed": final_domain,
         "matched": domain_match, "similarity": 1.0 if domain_match else 0.0},
    ]
    strong_identity = centre_code_match and (postal_match or name_match or address_match)
    strong_location = postal_match and (name_match or address_match)
    strong_descriptive_identity = name_match and address_match and domain_match
    parsed_candidate = urlsplit(page.final_url)
    root_page = parsed_candidate.path.rstrip("/") in {"", "/index.html", "/index.htm"}
    operator_identity = (
        domain_match and root_page and name_similarity >= 0.5
        and not (centre_code_match or postal_match or address_match)
    )
    unqualified_school_brand = (
        domain_match and root_page and name_similarity >= 0.9 and "@" not in str(school_name)
        and not (centre_code_match or postal_match or address_match)
    )
    expected_acronym = _name_acronym(school_name)
    final_brand = final_domain.lower().removeprefix("www.").split(".", 1)[0]
    official_brand_requires_review = (
        domain_match and root_page and len(expected_acronym) >= 3
        and final_brand.startswith(expected_acronym[:3])
        and name_similarity < 0.5
        and not (centre_code_match or postal_match or address_match)
    )
    if strong_identity or strong_location or strong_descriptive_identity or unqualified_school_brand:
        status = "approved"
        confidence = "high"
        reason = (
            "Exact unqualified school brand on official homepage"
            if unqualified_school_brand and not (strong_identity or strong_location or strong_descriptive_identity)
            else "Strong school identity match"
        )
    elif operator_identity:
        status = "approved_operator"
        confidence = "medium"
        reason = "Official brand homepage without branch-specific location evidence"
    elif official_brand_requires_review:
        status = "pending_review"
        confidence = "medium"
        reason = "Official brand homepage may require rendered branch content"
    elif sum(match["matched"] for match in matches) >= 2:
        status = "pending_review"
        confidence = "medium"
        reason = "Multiple weak matches require review"
    else:
        status = "rejected"
        confidence = "low"
        reason = "Insufficient school-specific identity evidence"
    return {
        "school_id": record.get("school_id"),
        "school_name": school_name,
        "url": url,
        "review_status": status,
        "verification_method": "automated_deterministic",
        "identity_confidence": confidence,
        "reviewed_at": datetime.now(timezone.utc).date().isoformat(),
        "reviewer": "Phase 9 automated verifier",
        "identity_matches": matches,
        "notes": reason,
    }


def automate_allowlist(
    inventory_rows: list[dict[str, Any]],
    catalogue_records: list[dict[str, Any]],
    *,
    fetcher: Callable[[str], PageContent] | None = None,
    limit: int | None = None,
    delay_seconds: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, PageContent]]:
    """Fetch school-specific candidates and produce decisions without manual JSON editing."""
    fetcher = fetcher or fetch_page
    catalogue = {record.get("school_id"): record for record in catalogue_records}
    candidates = [row for row in inventory_rows if row.get("scope") == "school_specific_candidate"]
    if limit is not None:
        candidates = candidates[:max(0, limit)]
    decisions: list[dict[str, Any]] = []
    fetched: dict[str, PageContent] = {}
    last_host: str | None = None
    for row in candidates:
        school_id = row.get("school_id")
        url = row.get("selected_candidate_url")
        record = catalogue.get(school_id)
        if not record or not url:
            continue
        host = urlsplit(url).hostname
        if delay_seconds and host == last_host:
            time.sleep(delay_seconds)
        try:
            page = fetcher(url)
            fetched[url] = page
            decisions.append(verify_school_identity(record, page, url))
        except PilotError as exc:
            decisions.append({
                "school_id": school_id,
                "school_name": row.get("school_name"),
                "url": url,
                "review_status": "fetch_failed",
                "verification_method": "automated_deterministic",
                "identity_confidence": "unknown",
                "reviewed_at": datetime.now(timezone.utc).date().isoformat(),
                "reviewer": "Phase 9 automated verifier",
                "identity_matches": [],
                "notes": str(exc),
                **failure_metadata(exc),
            })
        last_host = host
    return decisions, fetched


def automate_shared_pages(
    inventory_rows: list[dict[str, Any]],
    *,
    fetcher: Callable[[str], PageContent] | None = None,
    limit: int | None = None,
    delay_seconds: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, PageContent]]:
    """Fetch each shared URL once and register it as operator-level evidence."""
    fetcher = fetcher or fetch_page
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in inventory_rows:
        if row.get("scope") == "shared_operator_page_candidate" and row.get("selected_candidate_url"):
            grouped.setdefault(row["selected_candidate_url"], []).append(row)
    groups = list(grouped.items())
    if limit is not None:
        groups = groups[:max(0, limit)]
    decisions: list[dict[str, Any]] = []
    fetched: dict[str, PageContent] = {}
    last_host: str | None = None
    for url, rows in groups:
        host = urlsplit(url).hostname or ""
        if delay_seconds and host == last_host:
            time.sleep(delay_seconds)
        operator_id = "OPERATOR_PAGE:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        try:
            page = fetcher(url)
            fetched[url] = page
            decisions.append({
                "operator_id": operator_id,
                "operator_name": host.removeprefix("www."),
                "url": url,
                "final_url": page.final_url,
                "review_status": "approved_operator",
                "evidence_scope": "operator",
                "verification_method": "shared_catalogue_url",
                "linked_school_ids": sorted(str(row["school_id"]) for row in rows if row.get("school_id")),
                "schools_sharing_url": len(rows),
                "reviewed_at": datetime.now(timezone.utc).date().isoformat(),
                "reviewer": "Phase 9 automated shared-page handler",
                "notes": "Shared page is approved only as operator-level evidence; it is not proof of a branch claim.",
            })
        except PilotError as exc:
            decisions.append({
                "operator_id": operator_id,
                "operator_name": host.removeprefix("www."),
                "url": url,
                "review_status": "fetch_failed",
                "evidence_scope": "operator",
                "verification_method": "shared_catalogue_url",
                "linked_school_ids": sorted(str(row["school_id"]) for row in rows if row.get("school_id")),
                "schools_sharing_url": len(rows),
                "reviewed_at": datetime.now(timezone.utc).date().isoformat(),
                "reviewer": "Phase 9 automated shared-page handler",
                "notes": str(exc),
                **failure_metadata(exc),
            })
        last_host = host
    return decisions, fetched


def _reject_private_host(host: str) -> None:
    if host.lower() == "localhost":
        raise FetchError("unsafe_host", "Local hosts are not fetchable", retryable=False)
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise FetchError("dns_failure", f"Could not resolve host: {host}", retryable=True, retry_after_seconds=3600) from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise FetchError("unsafe_host", f"Non-public address is not fetchable: {address}", retryable=False)


def fetch_page(
    url: str,
    *,
    timeout: float = 12.0,
    opener: Any | None = None,
    check_dns: bool = True,
) -> PageContent:
    """Fetch one allowlisted HTML page after robots and network-safety checks."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise FetchError("invalid_url", "Only absolute HTTPS URLs may be fetched", retryable=False)
    if check_dns:
        _reject_private_host(parts.hostname)
    robots_url = urljoin(url, "/robots.txt")
    robot = RobotFileParser()
    robot.set_url(robots_url)
    try:
        robot.read()
    except HTTPError as exc:
        retryable = exc.code == 429 or exc.code >= 500
        raise FetchError(
            "robots_unavailable", f"Could not verify site policy at {robots_url}",
            retryable=retryable, retry_after_seconds=3600 if retryable else None,
        ) from exc
    except (URLError, OSError) as exc:
        raise FetchError(
            "robots_unavailable", f"Could not verify site policy at {robots_url}",
            retryable=True, retry_after_seconds=3600,
        ) from exc
    if not robot.can_fetch(USER_AGENT, url):
        raise FetchError("robots_disallowed", f"Site policy disallows fetching {url}", retryable=False)

    client = opener or build_opener()
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        response = client.open(request, timeout=timeout)
        final_url = response.geturl()
        final_parts = urlsplit(final_url)
        if final_parts.scheme != "https" or not final_parts.hostname:
            raise FetchError("unsafe_redirect", "Redirected to a non-HTTPS URL", retryable=False)
        if check_dns:
            _reject_private_host(final_parts.hostname)
        content_type = response.headers.get_content_type()
        if content_type != "text/html":
            raise FetchError("unsupported_content", f"Unsupported content type: {content_type}", retryable=False)
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except FetchError:
        raise
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        retry_seconds = int(retry_after) if str(retry_after or "").isdigit() else None
        if exc.code == 404:
            code, retryable, retry_seconds = "not_found", True, 30 * 86400
        elif exc.code == 429:
            code, retryable, retry_seconds = "rate_limited", True, retry_seconds or 3600
        elif exc.code >= 500:
            code, retryable, retry_seconds = "server_error", True, retry_seconds or 3600
        elif exc.code in {401, 403}:
            code, retryable = "access_denied", False
        else:
            code, retryable = "http_error", False
        raise FetchError(
            code, f"Fetch failed for {url}: HTTP {exc.code}", retryable=retryable,
            retry_after_seconds=retry_seconds,
        ) from exc
    except TimeoutError as exc:
        raise FetchError("timeout", f"Fetch timed out for {url}", retryable=True, retry_after_seconds=900) from exc
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        code = "timeout" if isinstance(reason, TimeoutError) else "network_error"
        raise FetchError(code, f"Fetch failed for {url}: {type(reason).__name__}", retryable=True, retry_after_seconds=1800) from exc
    except OSError as exc:
        raise FetchError("network_error", f"Fetch failed for {url}: {type(exc).__name__}", retryable=True, retry_after_seconds=1800) from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise FetchError("response_too_large", f"Page exceeds {MAX_RESPONSE_BYTES} bytes", retryable=False)
    charset = response.headers.get_content_charset() or "utf-8"
    html = body.decode(charset, errors="replace")
    title, text = extract_html(html)
    if not text:
        raise FetchError(
            "javascript_required", "No readable page text was extracted", retryable=False
        )
    return PageContent(
        requested_url=url,
        final_url=final_url,
        title=title,
        text=text,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        content_hash=hashlib.sha256(body).hexdigest(),
    )


def fetch_page_with_browser_fallback(url: str, *, timeout: int = 20) -> PageContent:
    """Render only when the policy-checked ordinary HTML fetch has no readable text."""
    try:
        return fetch_page(url, timeout=timeout)
    except FetchError as exc:
        if exc.code != "javascript_required":
            raise
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:
        raise FetchError(
            "browser_unavailable",
            "JavaScript rendering requires Playwright and an installed Chromium browser",
            retryable=False,
        ) from exc
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                browser_page = browser.new_page(user_agent=USER_AGENT)
                response = browser_page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                final_url = browser_page.url
                parts = urlsplit(final_url)
                if parts.scheme != "https" or not parts.hostname:
                    raise FetchError("unsafe_redirect", "Browser redirected to a non-HTTPS URL", retryable=False)
                _reject_private_host(parts.hostname)
                if response and response.status >= 400:
                    raise FetchError(
                        "browser_http_error", f"Browser fetch failed for {url}: HTTP {response.status}",
                        retryable=response.status >= 500,
                    )
                title = browser_page.title().strip() or final_url
                identity_text = browser_page.locator("body").inner_text()
                browser_page.eval_on_selector_all(
                    "script,style,noscript,svg,canvas,template,nav,header,footer,aside,form,dialog",
                    "elements => elements.forEach(element => element.remove())",
                )
                visible_text = browser_page.locator("body").inner_text()
                seen: set[str] = set()
                lines = []
                for line in visible_text.splitlines():
                    cleaned = re.sub(r"\s+", " ", line).strip()
                    key = cleaned.casefold()
                    if not cleaned or key in seen or key in {"read more", "learn more", "close", "menu"}:
                        continue
                    seen.add(key)
                    lines.append(cleaned)
                text = " ".join(lines)
            finally:
                browser.close()
    except FetchError:
        raise
    except PlaywrightError as exc:
        raise FetchError(
            "browser_render_failed", f"Browser rendering failed for {url}: {type(exc).__name__}",
            retryable=True, retry_after_seconds=1800,
        ) from exc
    if not text:
        raise FetchError("javascript_required", "Browser rendered no readable page text", retryable=False)
    return PageContent(
        requested_url=url, final_url=final_url, title=title, text=text,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        identity_text=identity_text,
    )


def chunk_text(text: str, *, max_words: int = 180, overlap_words: int = 30) -> list[str]:
    if max_words <= 0 or overlap_words < 0 or overlap_words >= max_words:
        raise PilotError("Chunk sizes must satisfy 0 <= overlap_words < max_words")
    words = text.split()
    chunks = []
    step = max_words - overlap_words
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + max_words])
        if chunk:
            chunks.append(chunk)
        if start + max_words >= len(words):
            break
    return chunks


def _normalise_term(term: str) -> str:
    term = term.lower()
    if term == "fees":
        return "fee"
    if term.endswith("ies") and len(term) > 4:
        return term[:-3] + "y"
    if term.endswith("s") and not term.endswith("ss") and len(term) > 4:
        return term[:-1]
    return term


def _search_tokens(text: str) -> list[str]:
    raw = [_normalise_term(token) for token in TOKEN_RE.findall(text.lower())]
    tokens: list[str] = []
    index = 0
    while index < len(raw):
        if index + 1 < len(raw) and f"{raw[index]}{raw[index + 1]}" in {
            "handson", "activitybased", "duallanguage", "literaturebased", "learnercentred",
            "mothertongue", "fieldtrip", "playbased",
        }:
            tokens.append(f"{raw[index]}{raw[index + 1]}")
            index += 2
            continue
        if raw[index] not in STOP_WORDS:
            tokens.append(raw[index])
        index += 1
    return tokens


def _concept_variants(term: str) -> dict[str, float]:
    for group in SYNONYM_GROUPS:
        if term in group:
            return {variant: 1.0 if variant == term else 0.65 for variant in group}
    return {term: 1.0}


def _supports_query_intent(query: str, text: str, tokens: list[str]) -> bool:
    query_tokens = set(_search_tokens(query))
    token_set = set(tokens)
    compact_text = text.casefold()
    specialised_evidence = {
        "swimming": {"swimming", "swim", "pool", "aquatic"},
        "robotics": {"robotics", "robot", "coding"},
    }
    for requested, evidence_terms in specialised_evidence.items():
        if requested in query_tokens and not (token_set & evidence_terms):
            return False
    if "organic" in query_tokens and "organic" not in token_set:
        return False
    if query_tokens & {"language", "languages", "bilingual", "duallanguage"}:
        return bool(token_set & LANGUAGE_EVIDENCE)
    if "outdoor" in query_tokens:
        return bool(token_set & {"outdoor", "garden"})
    if query_tokens & {"fee", "cost", "price", "tuition", "subsidy"}:
        return bool(token_set & FEE_EVIDENCE or re.search(r"(?:\$|sgd)\s*\d", compact_text))
    if "curriculum" in query_tokens:
        return bool(token_set & CURRICULUM_EVIDENCE)
    if query_tokens & {"enrichment", "activity"}:
        return bool(token_set & ENRICHMENT_EVIDENCE)
    if query_tokens & {"facility", "environment"}:
        return bool(token_set & FACILITY_EVIDENCE)
    return True


def _rank_chunks(
    chunks: list[dict[str, Any]], query: str, *, limit: int, min_relevance: float
) -> list[dict[str, Any]]:
    query_terms = list(dict.fromkeys(_search_tokens(query)))
    if not query_terms or not chunks or limit <= 0:
        return []
    document_tokens = [_search_tokens(chunk.get("text", "")) for chunk in chunks]
    lengths = [len(tokens) or 1 for tokens in document_tokens]
    average_length = sum(lengths) / len(lengths)
    concepts = [_concept_variants(term) for term in query_terms]
    document_frequencies = []
    for variants in concepts:
        document_frequencies.append(sum(any(token in variants for token in tokens) for tokens in document_tokens))

    ranked = []
    for chunk, tokens, length in zip(chunks, document_tokens, lengths):
        if not _supports_query_intent(query, chunk.get("text", ""), tokens):
            continue
        term_counts = Counter(tokens)
        bm25 = 0.0
        matched = 0
        exact = 0
        matched_terms: list[str] = []
        for term, variants, frequency in zip(query_terms, concepts, document_frequencies):
            weighted_tf = max((term_counts.get(variant, 0) * weight for variant, weight in variants.items()), default=0.0)
            if weighted_tf <= 0:
                continue
            matched += 1
            exact += int(term_counts.get(term, 0) > 0)
            matched_terms.append(term)
            inverse_frequency = math.log(1 + (len(chunks) - frequency + 0.5) / (frequency + 0.5))
            denominator = weighted_tf + 1.2 * (1 - 0.75 + 0.75 * length / average_length)
            bm25 += inverse_frequency * (weighted_tf * 2.2 / denominator)
        coverage = matched / len(query_terms)
        exact_coverage = exact / len(query_terms)
        phrase = len(query_terms) >= 2 and " ".join(query_terms) in " ".join(tokens)
        relevance = min(1.0, coverage * 0.75 + exact_coverage * 0.2 + (0.15 if phrase else 0.0))
        if relevance < min_relevance:
            continue
        specificity_boost = 0.0
        if "curriculum" in query_terms:
            named_methods = {
                "montessori", "reggio", "playbased", "inquiry", "literaturebased",
                "activitybased", "constructivism",
            }
            specificity_boost = 0.35 * len(set(tokens) & named_methods)
        ranked.append({
            **chunk,
            "score": round(bm25 + (0.5 if phrase else 0.0) + specificity_boost, 4),
            "relevance": round(relevance, 4),
            "matched_query_terms": matched_terms,
            "phrase_match": phrase,
        })
    ranked.sort(key=lambda item: (-item["score"], -item["relevance"], item["chunk_id"]))
    return ranked[:limit]


def ingest_allowlist(
    entries: list[dict[str, Any]],
    *,
    fetcher: Callable[[str], PageContent] = fetch_page,
    delay_seconds: float = 1.0,
) -> dict[str, Any]:
    approved = validate_allowlist(entries)
    pages: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    last_host: str | None = None
    for entry in approved:
        host = urlsplit(entry["url"]).hostname
        if delay_seconds and host == last_host:
            time.sleep(delay_seconds)
        try:
            page = fetcher(entry["url"])
            chunks = [
                {
                    "chunk_id": f"{entry['school_id']}:{page.content_hash[:12]}:{index}",
                    "school_id": entry["school_id"],
                    "text": chunk,
                    "source_url": page.final_url,
                    "title": page.title,
                    "retrieved_at": page.retrieved_at,
                    "content_hash": page.content_hash,
                }
                for index, chunk in enumerate(chunk_text(page.text))
            ]
            pages.append({
                "school_id": entry["school_id"],
                "school_name": entry.get("school_name"),
                "source_url": page.final_url,
                "title": page.title,
                "retrieved_at": page.retrieved_at,
                "content_hash": page.content_hash,
                "identity_matches": entry["identity_matches"],
                "chunks": chunks,
            })
        except PilotError as exc:
            failures.append({"school_id": entry["school_id"], "url": entry["url"], "reason": str(exc)})
        last_host = host
    return {
        "schema_version": 1,
        "purpose": "explanation_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pages": pages,
        "failures": failures,
    }


def ingest_operator_pages(
    decisions: list[dict[str, Any]],
    *,
    fetcher: Callable[[str], PageContent] = fetch_page,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Create a separate operator-level index from approved shared pages."""
    pages: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for decision in decisions:
        if decision.get("review_status") != "approved_operator":
            continue
        try:
            page = fetcher(decision["url"])
            chunks = [
                {
                    "chunk_id": f"{decision['operator_id']}:{page.content_hash[:12]}:{index}",
                    "operator_id": decision["operator_id"],
                    "school_id": None,
                    "linked_school_ids": decision["linked_school_ids"],
                    "evidence_scope": "operator",
                    "text": chunk,
                    "source_url": page.final_url,
                    "title": page.title,
                    "retrieved_at": page.retrieved_at,
                    "content_hash": page.content_hash,
                }
                for index, chunk in enumerate(chunk_text(page.text))
            ]
            pages.append({
                "operator_id": decision["operator_id"],
                "operator_name": decision.get("operator_name"),
                "evidence_scope": "operator",
                "linked_school_ids": decision["linked_school_ids"],
                "source_url": page.final_url,
                "title": page.title,
                "retrieved_at": page.retrieved_at,
                "content_hash": page.content_hash,
                "chunks": chunks,
            })
        except PilotError as exc:
            failures.append({"operator_id": decision["operator_id"], "url": decision["url"], "reason": str(exc)})
    return pages, failures


def retrieve(
    index: dict[str, Any], school_id: str, query: str, *, limit: int = 3, min_relevance: float = 0.25
) -> list[dict[str, Any]]:
    """Return cited BM25-ranked matches from exactly one school."""
    if not school_id:
        raise PilotError("school_id is required for isolated retrieval")
    chunks = []
    for page in index.get("pages", []):
        if page.get("school_id") != school_id:
            continue
        chunks.extend(page.get("chunks", []))
    matches = _rank_chunks(chunks, query, limit=max(0, limit), min_relevance=min_relevance)
    for item in matches:
        item["citation"] = {
            "url": item["source_url"],
            "title": item.get("title") or item["source_url"],
            "retrieved_at": item["retrieved_at"],
            "chunk_id": item["chunk_id"],
        }
    return matches


def retrieve_operator_evidence(
    index: dict[str, Any], school_id: str, query: str, *, limit: int = 3, min_relevance: float = 0.25
) -> list[dict[str, Any]]:
    """Return explicitly labelled operator evidence linked to a school."""
    if not school_id:
        raise PilotError("school_id is required for operator-evidence retrieval")
    chunks = []
    for page in index.get("operator_pages", []):
        if school_id not in page.get("linked_school_ids", []):
            continue
        chunks.extend(page.get("chunks", []))
    matches = _rank_chunks(chunks, query, limit=max(0, limit), min_relevance=min_relevance)
    for item in matches:
        item["claim_boundary"] = "Operator-level information; not verified for this specific branch."
        item["citation"] = {
            "url": item["source_url"],
            "title": item.get("title") or item["source_url"],
            "retrieved_at": item["retrieved_at"],
            "chunk_id": item["chunk_id"],
            "evidence_scope": "operator",
        }
    return matches


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
