"""Default home-distance rules for school search and ranking."""

from __future__ import annotations

DEFAULT_HOME_RADIUS_KM = 5.0
NEAR_HOME_RADIUS_KM = 1.0


def distance_opt_out(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    phrases = (
        "anywhere in singapore",
        "anywhere in sg",
        "island wide",
        "island-wide",
        "whole island",
        "no distance limit",
        "any distance",
        "ignore distance",
        "distance does not matter",
        "distance doesn't matter",
    )
    return any(phrase in lowered for phrase in phrases)


def effective_search_radius_km(profile: dict | None, home_postal_code: str | None = None) -> float | None:
    """Return the radius to use for search/ranking, or None when location filtering is off."""
    if not home_postal_code or len(str(home_postal_code)) != 6 or not str(home_postal_code).isdigit():
        return None
    if profile and profile.get("skip_default_distance"):
        return None
    hard = (profile or {}).get("hard_constraints") or {}
    explicit = hard.get("max_distance_km")
    if explicit is not None:
        value = float(explicit)
        return value if value > 0 else None
    return DEFAULT_HOME_RADIUS_KM
