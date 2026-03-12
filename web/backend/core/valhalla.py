"""
Valhalla routing — used for motorcycle/offroad profiles not available in OSRM.
Public instance: https://valhalla1.openstreetmap.de
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

VALHALLA_BASE = "https://valhalla1.openstreetmap.de"

RoutePoint = Tuple[float, float]  # (longitude, latitude)


def _decode_polyline6(encoded: str) -> List[Tuple[float, float]]:
    """Decode a Valhalla precision-6 encoded polyline → [(lat, lon), ...]."""
    coords: List[Tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)
    while index < length:
        result, shift = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat += (~(result >> 1) if result & 1 else result >> 1)

        result, shift = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lng += (~(result >> 1) if result & 1 else result >> 1)

        coords.append((lat / 1e6, lng / 1e6))
    return coords


def get_valhalla_route(
    waypoints: List[Tuple[float, float]],
    profile: str = "motorcycle_offroad",
) -> Optional[List[RoutePoint]]:
    """
    Route through waypoints via Valhalla.

    waypoints: [(lat, lon), ...]
    Returns: [(lon, lat), ...] — same convention as OSRM helpers, or None on failure.
    """
    locations = [{"lon": lon, "lat": lat} for lat, lon in waypoints]

    # Motorcycle profile: heavily prefer small roads and trails, avoid highways
    payload = {
        "locations": locations,
        "costing": "motorcycle",
        "costing_options": {
            "motorcycle": {
                "use_highways": 0.05,   # 0 = avoid completely, 1 = prefer
                "use_trails": 0.9,      # 0 = avoid, 1 = strongly prefer
                "use_ferry": 0.2,
            }
        },
        "units": "km",
    }

    try:
        r = requests.post(
            f"{VALHALLA_BASE}/route",
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        shape = data["trip"]["legs"][0]["shape"]
        decoded = _decode_polyline6(shape)  # [(lat, lon), ...]
        return [(lon, lat) for lat, lon in decoded]   # [(lon, lat), ...]

    except requests.exceptions.ConnectionError:
        logger.warning("Valhalla connection error")
        return None
    except requests.exceptions.Timeout:
        logger.warning("Valhalla timeout")
        return None
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        logger.warning(f"Valhalla HTTP {code}: {e.response.text[:200] if e.response is not None else ''}")
        return None
    except Exception as e:
        logger.error(f"Valhalla unexpected error: {e}")
        return None
