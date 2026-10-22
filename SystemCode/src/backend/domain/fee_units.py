"""Helpers for keeping preschool fee calculations on a monthly basis."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


MONTHLY_FEE_SERVICE_TYPES = frozenset({
    "Full Day",
    "Half Day AM",
    "Half Day PM",
    "Flexi Care 1",
    "Flexi Care 1 AM",
    "Flexi Care 1 PM",
    "Flexi Care 2",
    "Flexi Care 3",
})

_NON_MONTHLY_RATE_RE = re.compile(
    r"\b(?:per\s*(?:hour|hr|day|term|session|annum|year)|"
    r"per\s+(?:full|half)\s+day|"
    r"hourly\s+(?:fees?|charges?|rates?)|daily\s+(?:fees?|charges?|rates?)|"
    r"termly\s+(?:fees?|charges?|rates?))\b",
    re.IGNORECASE,
)


def is_monthly_programme_fee(service: Mapping[str, Any]) -> bool:
    """Accept only recurring programme types without an explicit other rate unit.

    The source catalogue has no dedicated unit column. Standard programme rows
    are monthly by convention, while their remarks can identify hourly, daily,
    term, session, or annual amounts. Ambiguous non-monthly rows are excluded.
    """
    if service.get("type_of_service") not in MONTHLY_FEE_SERVICE_TYPES:
        return False
    return not bool(_NON_MONTHLY_RATE_RE.search(str(service.get("remarks") or "")))
