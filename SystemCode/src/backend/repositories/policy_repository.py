from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


class PolicyUnavailableError(LookupError):
    pass


class PolicyConfigurationError(RuntimeError):
    pass


class PolicyRepository:
    """Load and select one non-overlapping policy version for an admission date."""

    def __init__(self, policy_directory: Path):
        self.policy_directory = policy_directory

    def policies(self) -> list[dict[str, Any]]:
        policies = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.policy_directory.glob("*.json"))]
        if not policies:
            raise PolicyConfigurationError("No subsidy policy resources are configured")
        policies.sort(key=lambda item: item["effective_from"])
        previous_end: dt.date | None = None
        for policy in policies:
            start = dt.date.fromisoformat(policy["effective_from"])
            end = dt.date.fromisoformat(policy["effective_to"]) if policy.get("effective_to") else None
            if end and end < start:
                raise PolicyConfigurationError(f"Invalid policy period: {policy['policy_id']}")
            if previous_end is None and policy is not policies[0]:
                raise PolicyConfigurationError("An open-ended policy must be the final version")
            if previous_end and start <= previous_end:
                raise PolicyConfigurationError("Subsidy policy effective periods overlap")
            previous_end = end
        return policies

    def for_date(self, applicable_date: dt.date) -> dict[str, Any]:
        matches = []
        for policy in self.policies():
            start = dt.date.fromisoformat(policy["effective_from"])
            end = dt.date.fromisoformat(policy["effective_to"]) if policy.get("effective_to") else None
            if start <= applicable_date and (end is None or applicable_date <= end):
                matches.append(policy)
        if len(matches) != 1:
            raise PolicyUnavailableError(f"No single subsidy policy applies on {applicable_date.isoformat()}")
        return matches[0]
