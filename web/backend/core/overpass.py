"""
Overpass API queries — find OSM POIs along route segments.
Extracted from main_gui_enhanced.py, all GUI references removed.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional

import requests
from shapely.geometry import LineString, Point

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds


def query_overpass_for_segment(
    segment: LineString,
    buffer_deg: float,
    query_filter: str,
    place_type: str,
    on_route_only: bool = False,
    cancel_check: Optional[Callable[[], bool]] = None,
    retry_count: int = 0,
    is_rate_limit_retry: bool = False,
) -> Dict:
    """
    Query Overpass API for POIs within a buffered route segment.

    Returns raw Overpass JSON dict (may be empty on error).
    cancel_check: callable returning True if processing should stop.
    """
    if cancel_check and cancel_check():
        return {}

    buffer_poly = segment.buffer(buffer_deg)
    minx, miny, maxx, maxy = buffer_poly.bounds

    query = f"""
[out:json];
{query_filter}({miny},{minx},{maxy},{maxx});
out center;
"""

    # Delay logic
    if retry_count > 0:
        if is_rate_limit_retry:
            delay = BASE_DELAY * (2 ** (retry_count + 1))
        else:
            delay = BASE_DELAY * (2 ** retry_count)
        logger.info(f"Waiting {delay}s before retry {retry_count} for {place_type}...")
        time.sleep(delay)
    else:
        time.sleep(0.5)  # gentle on API

    if cancel_check and cancel_check():
        return {}

    try:
        response = requests.post(
            OVERPASS_URL, data={"data": query}, timeout=60
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        logger.warning(f"[{place_type}] Overpass connection error")
        return {}

    except requests.exceptions.Timeout:
        logger.warning(f"[{place_type}] Overpass timeout")
        if retry_count < MAX_RETRIES:
            return query_overpass_for_segment(
                segment, buffer_deg, query_filter, place_type,
                on_route_only, cancel_check, retry_count + 1
            )
        return {}

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 429:
            logger.warning(f"[{place_type}] Overpass rate limited (429)")
            if retry_count < MAX_RETRIES:
                return query_overpass_for_segment(
                    segment, buffer_deg, query_filter, place_type,
                    on_route_only, cancel_check, retry_count + 1,
                    is_rate_limit_retry=True,
                )
        elif code == 504:
            logger.warning(f"[{place_type}] Overpass gateway timeout (504)")
            if retry_count < MAX_RETRIES:
                return query_overpass_for_segment(
                    segment, buffer_deg, query_filter, place_type,
                    on_route_only, cancel_check, retry_count + 1
                )
        else:
            logger.warning(f"[{place_type}] Overpass HTTP {code}")
        return {}

    except Exception as e:
        logger.error(f"[{place_type}] Unexpected Overpass error: {e}")
        return {}


def collect_places_from_segment(
    segment: LineString,
    buffer_deg: float,
    query_filter: str,
    place_type: str,
    config: dict,
    on_route_only: bool = False,
    buffer_km: float = 0.1,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[tuple, dict]:
    """
    Query Overpass for a segment and return dict of raw places keyed by (lat, lon, type).
    """
    data = query_overpass_for_segment(
        segment, buffer_deg, query_filter, place_type,
        on_route_only, cancel_check
    )

    places: Dict[tuple, dict] = {}

    for element in data.get("elements", []):
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            # Handle way/relation with center
            center = element.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")
        if lat is None or lon is None:
            continue

        pt = Point(lon, lat)
        key = (lat, lon, place_type)

        if on_route_only:
            dist_deg = segment.distance(pt)
            dist_km = dist_deg * 111.0
            if dist_km > buffer_km:
                continue
        else:
            seg_buffer = segment.buffer(buffer_deg)
            if not seg_buffer.contains(pt):
                continue

        if key not in places:
            base_name = element.get("tags", {}).get(
                "name", f"Unnamed {config.get('name', 'Place')}"
            )
            places[key] = {
                "base_name": base_name,
                "lat": lat,
                "lon": lon,
                "place_type": place_type,
                "config": config,
            }

    return places
