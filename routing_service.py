"""Reverse geocoding and road routing helpers for ReliefRoutes AI."""
import math
import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
HEADERS = {"User-Agent": "ReliefRoutesAI/1.0 (disaster-relief-planning-demo)"}


def reverse_geocode(latitude, longitude):
    """Return a human-readable place label, or a coordinate fallback."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"format": "jsonv2", "lat": latitude, "lon": longitude, "zoom": 16},
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        address = data.get("address", {})
        parts = [
            address.get("suburb") or address.get("neighbourhood") or address.get("village")
            or address.get("town") or address.get("city_district"),
            address.get("city") or address.get("town") or address.get("county"),
            address.get("state"),
        ]
        label = ", ".join(dict.fromkeys(part for part in parts if part))
        return label or data.get("display_name") or f"{latitude:.5f}, {longitude:.5f}"
    except (requests.RequestException, ValueError, KeyError):
        return f"Selected map point ({latitude:.5f}, {longitude:.5f})"



def forward_geocode(query):
    """Convert a typed place/address into (latitude, longitude, display name)."""
    query = (query or "").strip()
    if not query:
        return None
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1},
            headers=HEADERS,
            timeout=12,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None
        result = results[0]
        return float(result["lat"]), float(result["lon"]), result.get("display_name", query)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def get_road_route(start_lat, start_lon, end_lat, end_lon):
    """Return OSRM driving route geometry, distance km and duration minutes."""
    url = f"{OSRM_URL}/{start_lon},{start_lat};{end_lon},{end_lat}"
    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok" or not payload.get("routes"):
            return None
        route = payload["routes"][0]
        # GeoJSON coordinates are [longitude, latitude]; Folium expects [latitude, longitude].
        points = [[lat, lon] for lon, lat in route["geometry"]["coordinates"]]
        return {
            "points": points,
            "distance_km": route["distance"] / 1000,
            "duration_min": route["duration"] / 60,
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))
