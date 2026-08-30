"""Home-to-preschool distance calculation for Stage 3."""

from __future__ import annotations

import math
from typing import Any


def haversine_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Calculate great-circle distance between two latitude/longitude points."""
    earth_radius_km = 6371.0088
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    delta_lat = lat2 - lat1
    delta_lon = math.radians(b["longitude"] - a["longitude"])
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(value))


def calculate_home_to_preschool(
    home: dict[str, Any], preschool: dict[str, Any]
) -> dict[str, Any]:
    """Return the straight-line distance and two-point trip schedule."""
    distance = haversine_km(home, preschool)
    schedule = [
        {
            "order": 0,
            "type": "home",
            "name": home["name"],
            "centre_code": None,
            "latitude": home["latitude"],
            "longitude": home["longitude"],
            "leg_distance_km": 0.0,
            "cumulative_distance_km": 0.0,
        },
        {
            "order": 1,
            "type": "preschool",
            "name": preschool["name"],
            "centre_code": preschool.get("centre_code"),
            "latitude": preschool["latitude"],
            "longitude": preschool["longitude"],
            "leg_distance_km": round(distance, 3),
            "cumulative_distance_km": round(distance, 3),
        },
    ]
    return {
        "distance_method": "haversine_straight_line",
        "total_distance_km": round(distance, 3),
        "travel_distance_km": round(distance, 3),
        "travel_duration_minutes": None,
        "travel_mode": "unavailable",
        "route_method": "haversine_straight_line",
        "route_coordinates": [
            {"latitude": home["latitude"], "longitude": home["longitude"]},
            {"latitude": preschool["latitude"], "longitude": preschool["longitude"]},
        ],
        "estimated": True,
        "fallback_reason": "OneMap driving route unavailable; showing straight-line distance.",
        "schedule": schedule,
    }
