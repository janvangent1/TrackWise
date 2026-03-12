"""
Main search orchestrator — ties GPX parsing, Overpass queries, OSRM routing together.
Yields progress events as dicts so callers (SSE, CLI, tests) can consume them.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from typing import Callable, Dict, Generator, List, Optional, Tuple

from geopy.distance import geodesic
from shapely.geometry import LineString, Point

from .gpx_parser import RoutePoint, calculate_total_distance_km
from .osrm import get_road_route
from .overpass import collect_all_types_from_segment
from .place_types import PLACE_TYPE_CONFIG

logger = logging.getLogger(__name__)

CHUNK_KM = 50
OVERPASS_PAUSE = 5.0   # seconds between sequential Overpass requests (polite usage)
MAX_OSRM_WORKERS = 2   # public router.project-osrm.org rate-limits parallel requests


# ---------------------------------------------------------------------------
# Route segmentation
# ---------------------------------------------------------------------------

def split_line_by_distance(line: LineString, max_km: float) -> List[LineString]:
    """Split a LineString into segments of at most max_km each."""
    segments: List[LineString] = []
    coords = list(line.coords)
    current_chunk = [coords[0]]
    dist_accum = 0.0

    for i in range(1, len(coords)):
        pt1 = (coords[i - 1][1], coords[i - 1][0])
        pt2 = (coords[i][1], coords[i][0])
        seg_dist = geodesic(pt1, pt2).km

        if dist_accum + seg_dist > max_km and len(current_chunk) > 1:
            segments.append(LineString(current_chunk))
            current_chunk = [coords[i - 1], coords[i]]
            dist_accum = seg_dist
        else:
            current_chunk.append(coords[i])
            dist_accum += seg_dist

    if len(current_chunk) > 1:
        segments.append(LineString(current_chunk))
    elif segments and len(current_chunk) == 1:
        # Merge single trailing point into last segment
        last_coords = list(segments[-1].coords) + current_chunk
        segments[-1] = LineString(last_coords)

    # Fallback: if no segments produced (very short route), return whole line
    if not segments:
        segments = [line]

    return segments


# ---------------------------------------------------------------------------
# Deduplication (ported from original)
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    common = {"the", "de", "la", "le", "du", "des", "station", "service", "gas", "petrol"}
    words = name.lower().strip().split()
    filtered = [w for w in words if w not in common]
    return " ".join(filtered) if filtered else name.lower().strip()


def _names_similar(n1: str, n2: str, strict: bool = False) -> bool:
    if not n1 or not n2:
        return False
    a = _normalize_name(n1) if not strict else n1.lower().strip()
    b = _normalize_name(n2) if not strict else n2.lower().strip()
    if a == b:
        return True
    if not strict and min(len(a), len(b)) >= 4:
        return a in b or b in a
    if strict and len(a) >= 4 and len(b) >= 4:
        return a in b or b in a
    return False


def remove_duplicates(places: List[dict]) -> List[dict]:
    """Remove places that are very close and have similar names."""
    deduped: List[dict] = []
    for place in places:
        is_dup = False
        for existing in deduped:
            if place["place_type"] != existing["place_type"]:
                continue
            dist = geodesic(
                (place["lat"], place["lon"]),
                (existing["lat"], existing["lon"]),
            ).km
            if dist <= 0.05 and _names_similar(place["base_name"], existing["base_name"]):
                is_dup = True
                break
            if dist <= 0.2 and _names_similar(place["base_name"], existing["base_name"], strict=True):
                is_dup = True
                break
        if not is_dup:
            deduped.append(place)
    return deduped


# ---------------------------------------------------------------------------
# Search config
# ---------------------------------------------------------------------------

class SearchConfig:
    """Per-search parameters passed in from the API."""

    def __init__(self, place_types: Dict[str, float]):
        """
        place_types: {place_type: distance_km}
        e.g. {"petrol": 5.0, "cafe": 0.1}
        """
        for pt in place_types:
            if pt not in PLACE_TYPE_CONFIG:
                raise ValueError(f"Unknown place type: {pt!r}")
        self.place_types = place_types


# ---------------------------------------------------------------------------
# Main search function (yields progress events)
# ---------------------------------------------------------------------------

def run_search(
    route_points: List[RoutePoint],
    config: SearchConfig,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Generator[dict, None, None]:
    """
    Generator that yields progress/result dicts.

    Event types:
      {"type": "progress", "message": str, "percent": float}
      {"type": "result",   "places": [...], "road_routes": {...}, "route_points": [...], "total_km": float}
      {"type": "error",    "message": str}
      {"type": "cancelled"}
    """
    def _cancelled() -> bool:
        return cancel_check() if cancel_check else False

    try:
        total_km = calculate_total_distance_km(route_points)
        yield {"type": "progress", "message": f"Route loaded: {total_km:.1f} km, {len(route_points)} points", "percent": 2}

        route_line = LineString(route_points)
        segments = split_line_by_distance(route_line, CHUNK_KM)
        yield {"type": "progress", "message": f"Split into {len(segments)} search segments", "percent": 5}

        all_places_raw: Dict[tuple, dict] = {}
        place_types = list(config.place_types.items())
        n_types = len(place_types)

        # Build the type-job descriptor list (shared across all segments)
        type_job_list = [
            {
                "place_type": place_type,
                "pt_config": PLACE_TYPE_CONFIG[place_type],
                "buffer_deg": distance_km / 111.0,
                "buffer_km": distance_km,
                "on_route_only": PLACE_TYPE_CONFIG[place_type].get("on_route_only", False),
            }
            for place_type, distance_km in place_types
        ]
        places_per_type: Dict[str, Dict[tuple, dict]] = {pt: {} for pt, _ in place_types}

        total_segs = len(segments)
        yield {
            "type": "progress",
            "message": (
                f"Querying Overpass: {total_segs} segment(s), "
                f"all {n_types} type(s) per request (around filter)…"
            ),
            "percent": 5,
        }

        # Sequential requests — the public Overpass server does not like parallel
        # queries from the same IP.  A {OVERPASS_PAUSE}s pause between requests is polite.
        for seg_idx, seg in enumerate(segments):
            if _cancelled():
                yield {"type": "cancelled"}
                return

            if seg_idx > 0:
                yield {
                    "type": "progress",
                    "message": f"  Waiting {OVERPASS_PAUSE:.0f}s before next segment…",
                    "percent": 5 + (seg_idx / total_segs) * 60,
                }
                time.sleep(OVERPASS_PAUSE)

            yield {
                "type": "progress",
                "message": f"  Querying Overpass for segment {seg_idx+1}/{total_segs}… (may take up to 45s)",
                "percent": 5 + (seg_idx / total_segs) * 60,
            }

            try:
                seg_results = collect_all_types_from_segment(seg, type_job_list, cancel_check)
                for pt, places in seg_results.items():
                    places_per_type[pt].update(places)
                counts = {pt: len(v) for pt, v in places_per_type.items() if v}
                logger.info(f"Segment {seg_idx+1}/{total_segs} done — totals: {counts}")
            except Exception as e:
                logger.error(f"Segment {seg_idx+1} error: {e}")

            counts_str = ", ".join(
                f"{PLACE_TYPE_CONFIG[pt]['emoji']} {len(v)}"
                for pt, v in places_per_type.items() if v
            )
            yield {
                "type": "progress",
                "message": (
                    f"  [{seg_idx+1}/{total_segs}] segment done"
                    + (f" — {counts_str}" if counts_str else "")
                ),
                "percent": 5 + ((seg_idx + 1) / total_segs) * 60,
            }

        for place_type, places_for_type in places_per_type.items():
            all_places_raw.update(places_for_type)
            pt_config = PLACE_TYPE_CONFIG[place_type]
            yield {
                "type": "progress",
                "message": f"Found {len(places_for_type)} {pt_config['name']}s",
                "percent": 65,
            }

        if _cancelled():
            yield {"type": "cancelled"}
            return

        yield {"type": "progress", "message": f"Deduplicating {len(all_places_raw)} raw places...", "percent": 67}
        deduped = remove_duplicates(list(all_places_raw.values()))
        yield {
            "type": "progress",
            "message": f"After deduplication: {len(deduped)} places ({len(all_places_raw) - len(deduped)} removed)",
            "percent": 70,
        }

        # ---- Distance calculation ----
        enhanced_places: List[dict] = []
        for i, place in enumerate(deduped):
            if _cancelled():
                yield {"type": "cancelled"}
                return

            place_point = Point(place["lon"], place["lat"])
            route_position = route_line.project(place_point)
            nearest = route_line.interpolate(route_position)
            dist_km = geodesic(
                (place["lat"], place["lon"]),
                (nearest.y, nearest.x),
            ).km

            pt_config = PLACE_TYPE_CONFIG[place["place_type"]]
            enhanced_places.append({
                "id": f"{place['place_type']}_{i}",
                "base_name": place["base_name"],
                "name": f"{pt_config['emoji']} {place['base_name']} ({dist_km:.1f}km)",
                "lat": place["lat"],
                "lon": place["lon"],
                "distance_km": round(dist_km, 3),
                "route_position": route_position,
                "place_type": place["place_type"],
                "color": pt_config["color"],
                "emoji": pt_config["emoji"],
                "type_label": pt_config["name"],
                "included": True,
            })

            if (i + 1) % 10 == 0 or (i + 1) == len(deduped):
                yield {
                    "type": "progress",
                    "message": f"Calculated distances: {i+1}/{len(deduped)}",
                    "percent": 70 + (i + 1) / len(deduped) * 15,
                }

        # Sort each type by route position
        enhanced_places.sort(key=lambda p: p["route_position"])

        # ---- Road routing (parallel) ----
        # Pre-compute nearest route point for each place that needs routing
        routing_jobs = []  # (place_id, start_lat, start_lon, end_lat, end_lon)
        for place in enhanced_places:
            if place["distance_km"] < 0.2:
                continue  # On track — no detour needed
            place_point = Point(place["lon"], place["lat"])
            nearest = route_line.interpolate(route_line.project(place_point))
            routing_jobs.append((
                place["id"],
                float(nearest.y), float(nearest.x),
                place["lat"], place["lon"],
            ))

        n_jobs = len(routing_jobs)
        yield {
            "type": "progress",
            "message": f"Calculating road routes for {n_jobs} places ({MAX_OSRM_WORKERS} parallel)...",
            "percent": 85,
        }

        road_routes: Dict[str, List] = {}

        def _fetch_route(job):
            pid, s_lat, s_lon, e_lat, e_lon = job
            route = get_road_route(s_lat, s_lon, e_lat, e_lon)
            return pid, route, s_lat, s_lon, e_lat, e_lon

        with ThreadPoolExecutor(max_workers=MAX_OSRM_WORKERS) as executor:
            future_to_job = {executor.submit(_fetch_route, job): job for job in routing_jobs}
            pending = set(future_to_job.keys())
            completed = 0

            while pending:
                if _cancelled():
                    yield {"type": "cancelled"}
                    return

                done, pending = wait(pending, timeout=3.0, return_when=FIRST_COMPLETED)

                for future in done:
                    completed += 1
                    try:
                        pid, route, s_lat, s_lon, e_lat, e_lon = future.result()
                        if route and len(route) > 1:
                            road_routes[pid] = route
                        else:
                            # OSRM unavailable — straight-line fallback so map always shows a line
                            road_routes[pid] = [[s_lon, s_lat], [e_lon, e_lat]]
                    except Exception as e:
                        logger.warning(f"Road route fetch error: {e}")

                still_running = len(pending)
                suffix = f" ({still_running} in progress…)" if still_running else ""
                yield {
                    "type": "progress",
                    "message": f"Road routes: {completed}/{n_jobs} done ({len(road_routes)} found){suffix}",
                    "percent": 85 + completed / max(n_jobs, 1) * 13,
                }

        yield {"type": "progress", "message": "Search complete!", "percent": 99}

        # Emit summary counts
        counts = {}
        for p in enhanced_places:
            counts[p["place_type"]] = counts.get(p["place_type"], 0) + 1
        summary_parts = [f"{PLACE_TYPE_CONFIG[t]['emoji']} {n}" for t, n in counts.items()]
        yield {
            "type": "progress",
            "message": "Found: " + ", ".join(summary_parts) if summary_parts else "No places found.",
            "percent": 100,
        }

        yield {
            "type": "result",
            "places": enhanced_places,
            "road_routes": road_routes,
            "route_points": route_points,
            "total_km": total_km,
        }

    except Exception as e:
        logger.exception("Search failed")
        yield {"type": "error", "message": str(e)}
