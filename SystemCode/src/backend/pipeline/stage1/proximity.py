"""Postal-code geocoding and preschool proximity filtering."""
import json
import math
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CENTRE_CODE_PATTERN = re.compile(r"<th>CENTRE_CODE</th>\s*<td>(.*?)</td>", re.I)
_token_lock = threading.Lock()
_cached_token = None
_token_expiry = 0.0

def _authenticate_onemap():
    email = os.getenv("ONEMAP_EMAIL")
    password = os.getenv("ONEMAP_PASSWORD")
    if not email or not password:
        static_token = os.getenv("ONEMAP_TOKEN")
        if static_token:
            return static_token, float("inf")
        raise RuntimeError(
            "The 1 km filter requires ONEMAP_EMAIL and ONEMAP_PASSWORD in the PoC .env file"
        )
    body = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = Request(
        "https://www.onemap.gov.sg/api/auth/post/getToken",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
    token = payload.get("access_token")
    expiry = payload.get("expiry_timestamp")
    if not token or not expiry:
        raise RuntimeError("OneMap authentication did not return a token and expiry")
    return token, float(expiry)

def get_onemap_token(force_refresh=False):
    """Return a cached token, refreshing it five minutes before expiry."""
    global _cached_token, _token_expiry
    with _token_lock:
        if not force_refresh and _cached_token and time.time() < _token_expiry - 300:
            return _cached_token
        _cached_token, _token_expiry = _authenticate_onemap()
        return _cached_token

def _search_onemap(postal_code, token):
    query = urlencode({"searchVal": postal_code, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1})
    request = Request(f"https://www.onemap.gov.sg/api/common/elastic/search?{query}", headers={"Authorization": token, "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.load(response)

def geocode_postal_code(postal_code):
    payload = _search_onemap(postal_code, get_onemap_token())
    if payload.get("error") and "token" in payload["error"].lower():
        payload = _search_onemap(postal_code, get_onemap_token(force_refresh=True))
    if payload.get("error"):
        raise RuntimeError(f"OneMap could not geocode the postal code: {payload['error']}")
    matches = [item for item in payload.get("results", []) if item.get("POSTAL") == postal_code]
    if not matches:
        raise ValueError(f"Postal code {postal_code} was not found by OneMap")
    return {"latitude": float(matches[0]["LATITUDE"]), "longitude": float(matches[0]["LONGITUDE"])}

def _haversine_km(first, second):
    radius = 6371.0088
    lat1, lat2 = math.radians(first["latitude"]), math.radians(second["latitude"])
    dlat = lat2 - lat1
    dlon = math.radians(second["longitude"] - first["longitude"])
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))

def load_locations(path):
    geojson = json.loads(Path(path).read_text(encoding="utf-8"))
    locations = {}
    for feature in geojson.get("features", []):
        match = CENTRE_CODE_PATTERN.search(feature.get("properties", {}).get("Description", ""))
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if match and len(coordinates) >= 2:
            locations[match.group(1).strip()] = {"latitude": float(coordinates[1]), "longitude": float(coordinates[0])}
    return locations

def _point_in_ring(longitude, latitude, ring):
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[:2]
        x2, y2 = current[:2]
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses and longitude < (x2 - x1) * (latitude - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside

def _point_in_polygon(longitude, latitude, polygon):
    return bool(polygon and _point_in_ring(longitude, latitude, polygon[0])) and not any(
        _point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
    )

def planning_area_for_point(origin, path):
    """Return the URA planning-area name containing a WGS84 point."""
    geojson = json.loads(Path(path).read_text(encoding="utf-8"))
    longitude, latitude = origin["longitude"], origin["latitude"]
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        polygons = geometry.get("coordinates", [])
        if geometry.get("type") == "Polygon":
            polygons = [polygons]
        if any(_point_in_polygon(longitude, latitude, polygon) for polygon in polygons):
            town = feature.get("properties", {}).get("PLN_AREA_N")
            if town:
                return town
    raise ValueError("The postal-code coordinates are outside the planning-area dataset")

def filter_within_radius(centres, origin, locations, radius_km=1.0):
    nearby = []
    for centre in centres:
        location = locations.get(centre.get("centre_code"))
        if location:
            distance = _haversine_km(origin, location)
            if distance <= radius_km:
                nearby.append({**centre, "distance_km": round(distance, 3)})
    return sorted(nearby, key=lambda centre: centre["distance_km"])
