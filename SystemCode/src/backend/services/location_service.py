from __future__ import annotations

from pathlib import Path
from typing import Any

from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from stage1.proximity import geocode_postal_code, get_driving_route
from stage3.locations import attach_locations, load_preschool_locations
from stage3.optimizer import calculate_home_to_preschool, haversine_km


class LocationService:
    def __init__(self, schools: SchoolRepository, location_file: Path):
        self.schools = schools
        self.location_file = location_file
        self._locations = None

    def _school_locations(self):
        if self._locations is None:
            self._locations = load_preschool_locations(self.location_file)
        return self._locations

    def attach_distances(self, school_records: list[dict[str, Any]], postal_code: str) -> list[dict[str, Any]]:
        home = geocode_postal_code(postal_code)
        locations = self._school_locations()
        return [
            {**school, "distance_km": round(haversine_km(home, locations[school["centre_code"]]), 3)
             if school.get("centre_code") in locations else None}
            for school in school_records
        ]

    def distances(self, school_ids: list[str], postal_code: str) -> list[dict[str, Any]]:
        records = self.attach_distances(self.schools.get_many(school_ids), postal_code)
        return [{"school_id": item["school_id"], "distance_km": item["distance_km"]}
                for item in records if item.get("distance_km") is not None]

    def route(self, school_id: str, postal_code: str) -> dict[str, Any]:
        selected = self.schools.get(school_id)
        located = attach_locations([selected], self._school_locations())
        home_coordinates = geocode_postal_code(postal_code)
        home = {"type": "home", "name": "Home", **home_coordinates}
        fallback = calculate_home_to_preschool(home, located[0])
        try:
            driving = get_driving_route(home, located[0])
        except (OSError, RuntimeError, ValueError):
            return fallback
        travel_distance = driving["travel_distance_km"]
        fallback["schedule"][1]["leg_distance_km"] = travel_distance
        fallback["schedule"][1]["cumulative_distance_km"] = travel_distance
        return {
            **fallback,
            **driving,
            "total_distance_km": travel_distance,
            "distance_method": driving["route_method"],
        }
