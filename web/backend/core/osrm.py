"""
OSRM road routing — find actual road path from route to POI.
Extracted from main_gui_enhanced.py, GUI-free.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

OSRM_URL = "http://router.project-osrm.org/route/v1/driving"


RoutePoint = Tuple[float, float]  # (longitude, latitude)


def get_road_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> Optional[List[RoutePoint]]:
    """
    Get road-following route between two points via OSRM.

    Returns list of (lon, lat) tuples, or None on failure.
    """
    url = (
        f"{OSRM_URL}/{start_lon},{start_lat};{end_lon},{end_lat}"
        "?overview=full&geometries=geojson"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        routes = data.get("routes", [])
        if not routes:
            logger.debug(f"OSRM: no routes from ({start_lat},{start_lon}) to ({end_lat},{end_lon})")
            return None

        geometry = routes[0].get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            return None

        # GeoJSON coords are [lon, lat]
        return [(coord[0], coord[1]) for coord in coordinates]

    except requests.exceptions.ConnectionError:
        logger.warning("OSRM connection error")
        return None
    except requests.exceptions.Timeout:
        logger.warning("OSRM timeout")
        return None
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        logger.warning(f"OSRM HTTP {code}")
        return None
    except Exception as e:
        logger.error(f"OSRM unexpected error: {e}")
        return None
