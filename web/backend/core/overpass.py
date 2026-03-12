"""
Overpass API queries — find OSM POIs along route segments.

Uses the Overpass `around` filter with route waypoints instead of bounding boxes.
This scans only the route corridor, not a large rectangle, which is far more
efficient on the public Overpass server and avoids 504 timeouts.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

import requests
from shapely.geometry import LineString, Point

logger = logging.getLogger(__name__)

# Public Overpass mirrors — tried in order on retry
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
MAX_RETRIES = 1   # 1 retry = 2 attempts max; worst case 45s + 6s + 45s = ~96s
# Minimum pause between consecutive HTTP requests to the same server (seconds).
# Sequential queries — no parallel requests — so this is a simple sleep.
REQUEST_PAUSE = 3.0


def _send_query(
    query: str,
    label: str,
    retry_count: int = 0,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict:
    """Send a single Overpass QL query, with simple retry on failure."""
    if cancel_check and cancel_check():
        return {}

    if retry_count > 0:
        delay = REQUEST_PAUSE * (2 ** retry_count)
        logger.info(f"[{label}] waiting {delay:.0f}s before retry {retry_count}…")
        time.sleep(delay)
        if cancel_check and cancel_check():
            return {}

    url = OVERPASS_MIRRORS[retry_count % len(OVERPASS_MIRRORS)]
    logger.info(f"[{label}] → {url.split('/')[2]}")

    try:
        response = requests.post(url, data={"data": query}, timeout=45)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        logger.warning(f"[{label}] connection error")
    except requests.exceptions.Timeout:
        logger.warning(f"[{label}] request timed out (45s)")
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        logger.warning(f"[{label}] HTTP {code}")
    except ValueError:
        logger.warning(f"[{label}] empty/invalid JSON response")
    except Exception as e:
        logger.error(f"[{label}] unexpected error: {e}")

    if retry_count < MAX_RETRIES:
        return _send_query(query, label, retry_count + 1, cancel_check)
    return {}


def _decimate_coords(segment: LineString, max_points: int = 150) -> List[Tuple[float, float]]:
    """
    Return a decimated list of (lat, lon) pairs from the segment.
    The Overpass `around` filter uses these as the linestring waypoints.
    Fewer points = shorter query string; 150 points per 50km segment ≈ 1 per 333m.
    """
    coords = list(segment.coords)  # (lon, lat)
    n = len(coords)
    if n <= max_points:
        pts = coords
    else:
        step = n / max_points
        pts = [coords[int(i * step)] for i in range(max_points)]
        if pts[-1] != coords[-1]:
            pts.append(coords[-1])
    # Convert to lat,lon order required by Overpass
    return [(c[1], c[0]) for c in pts]


def collect_all_types_from_segment(
    segment: LineString,
    type_jobs: List[dict],
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, Dict[tuple, dict]]:
    """
    Query ALL active place types in a single Overpass request for one segment.

    Uses `around` with route waypoints instead of a bounding box, so Overpass
    only scans the actual route corridor.  Each type gets its own radius.

    type_jobs: list of dicts, each with:
        place_type, pt_config, buffer_deg, buffer_km, on_route_only

    Returns: {place_type: {(lat, lon, type): place_dict}}
    """
    if not type_jobs:
        return {}

    waypoints = _decimate_coords(segment)
    coord_str = ",".join(f"{lat:.6f},{lon:.6f}" for lat, lon in waypoints)

    # One clause per type, each with its own radius in metres
    filter_parts = "\n".join(
        f"  {j['pt_config']['query']}(around:{int(j['buffer_km'] * 1000)},{coord_str});"
        for j in type_jobs
    )
    # timeout:60 — tell the server to allow 60s; maxsize limits memory usage
    query = f"[out:json][timeout:60][maxsize:134217728];\n(\n{filter_parts}\n);\nout center tags;\n"

    label = "+".join(j["place_type"] for j in type_jobs)
    logger.info(
        f"[{label}] Overpass around query — {len(waypoints)} waypoints, "
        f"{len(type_jobs)} types, radii: "
        + ", ".join(f"{j['place_type']}={int(j['buffer_km']*1000)}m" for j in type_jobs)
    )

    data = _send_query(query, label, cancel_check=cancel_check)
    n_elements = len(data.get("elements", []))
    logger.info(f"[{label}] received {n_elements} elements")

    results: Dict[str, Dict[tuple, dict]] = {j["place_type"]: {} for j in type_jobs}

    for element in data.get("elements", []):
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            center = element.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue

        tags = element.get("tags", {})
        pt = Point(lon, lat)

        for job in type_jobs:
            place_type = job["place_type"]
            pt_config = job["pt_config"]

            if tags.get(pt_config.get("tag_key", "")) not in pt_config.get("tag_values", []):
                continue

            # Precise Shapely distance check (more accurate than the around pre-filter)
            dist_km = segment.distance(pt) * 111.0
            if dist_km > job["buffer_km"]:
                continue

            key = (lat, lon, place_type)
            if key not in results[place_type]:
                base_name = tags.get("name", f"Unnamed {pt_config.get('name', 'Place')}")
                results[place_type][key] = {
                    "base_name": base_name,
                    "lat": lat,
                    "lon": lon,
                    "place_type": place_type,
                    "config": pt_config,
                }
            break  # each element belongs to at most one type

    return results
