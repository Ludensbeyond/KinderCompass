"""Outbound parent-mention search links. These are searches, not verified listings."""

from __future__ import annotations

from urllib.parse import quote_plus
from typing import Any


def _six_digit_postal(value: Any) -> str | None:
    if value in (None, "", "na"):
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits if len(digits) == 6 else None


def mention_search_query(name: str, postal_code: Any = None) -> str:
    parts = [str(name or "").strip()]
    postal = _six_digit_postal(postal_code)
    if postal:
        parts.append(postal)
    parts.append("Singapore")
    return " ".join(item for item in parts if item)


def parent_mention_links(name: str, postal_code: Any = None) -> dict[str, str]:
    """Build Google Maps, Google, and Reddit search URLs for a preschool name."""
    query = mention_search_query(name, postal_code)
    encoded = quote_plus(query)
    reviews = quote_plus(f"{query} reviews")
    return {
        "query": query,
        "google_maps": f"https://www.google.com/maps/search/?api=1&query={encoded}",
        "google_search": f"https://www.google.com/search?q={reviews}",
        "reddit": f"https://www.reddit.com/search/?q={encoded}",
    }
