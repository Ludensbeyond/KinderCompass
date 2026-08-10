"""Load preschool coordinates from the ECDA location GeoJSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CENTRE_CODE_PATTERN = re.compile(
    r"<th>CENTRE_CODE</th>\s*<td>(.*?)</td>", re.IGNORECASE
)


def load_preschool_locations(path: str | Path) -> dict[str, dict[str, Any]]:
    """Return ECDA preschool locations keyed by centre code."""
    source = Path(path)
    try:
        geojson = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Preschool location file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Preschool location file is not valid JSON: {source}") from exc

    locations = {}
    for feature in geojson.get("features", []):
        description = feature.get("properties", {}).get("Description", "")
        match = CENTRE_CODE_PATTERN.search(description)
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if not match or len(coordinates) < 2:
            continue
        longitude, latitude = coordinates[:2]
        locations[match.group(1).strip()] = {
            "latitude": float(latitude),
            "longitude": float(longitude),
        }
    return locations


def attach_locations(
    schools: list[dict[str, Any]], locations: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Copy coordinate data onto selected Stage 2 preschool records."""
    enriched = []
    missing = []
    for school in schools:
        code = school.get("centre_code")
        location = locations.get(code)
        if location is None:
            missing.append(str(code or "<unknown>"))
            continue
        enriched.append({**school, **location, "type": "preschool"})
    if missing:
        raise ValueError(
            "No ECDA coordinates found for centre code(s): " + ", ".join(missing)
        )
    return enriched
