"""
Main search orchestrator — ties GPX parsing, Overpass queries, OSRM routing together.
Yields progress events as dicts so callers (SSE, CLI, tests) can consume them.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Generator, List, Optional, Tuple

from geopy.distance import geodesic
from shapely.geometry import LineString, Point

from .gpx_parser import RoutePoint, calculate_total_distance_km
from .osrm import get_road_route
from .overpass import collect_places_from_segment
from .place_types import PLACE_TYPE_CONFIG

logger = logging.getLogger(__name__)

CHUNK_KM = 50
MAX_OVERPASS_WORKERS = 2


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

        for type_idx, (place_type, distance_km) in enumerate(place_types):
            if _cancelled():
                yield {"type": "cancelled"}
                return

            pt_config = PLACE_TYPE_CONFIG[place_type]
            buffer_deg = distance_km / 111.0
            on_route_only = pt_config.get("on_route_only", False)
            query_filter = pt_config["query"]

            base_pct = 5 + (type_idx / n_types) * 60
            yield {
                "type": "progress",
                "message": f"Searching for {pt_config['name']}s within {distance_km} km...",
                "percent": base_pct,
            }

            places_for_type: Dict[tuple, dict] = {}

            with ThreadPoolExecutor(max_workers=MAX_OVERPASS_WORKERS) as executor:
                future_to_idx = {
                    executor.submit(
                        collect_places_from_segment,
                        seg, buffer_deg, query_filter, place_type,
                        pt_config, on_route_only, distance_km, cancel_check,
                    ): i
                    for i, seg in enumerate(segments)
                }

                completed = 0
                for future in as_completed(future_to_idx):
                    if _cancelled():
                        yield {"type": "cancelled"}
                        return

                    completed += 1
                    try:
                        seg_places = future.result()
                        new_count = sum(1 for k in seg_places if k not in places_for_type)
                        places_for_type.update(seg_places)
                        if completed % 5 == 0 or completed == len(segments):
                            yield {
                                "type": "progress",
                                "message": (
                                    f"  [{completed}/{len(segments)}] segments done, "
                                    f"{len(places_for_type)} {pt_config['name']}s found so far"
                                ),
                                "percent": base_pct + (completed / len(segments)) * (60 / n_types),
                            }
                    except Exception as e:
                        logger.error(f"Segment query error for {place_type}: {e}")

            all_places_raw.update(places_for_type)
            yield {
                "type": "progress",
                "message": f"Found {len(places_for_type)} {pt_config['name']}s",
                "percent": base_pct + (60 / n_types),
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

        # ---- Road routing ----
        yield {"type": "progress", "message": f"Calculating road routes for {len(enhanced_places)} places...", "percent": 85}

        road_routes: Dict[str, List] = {}
        for i, place in enumerate(enhanced_places):
            if _cancelled():
                yield {"type": "cancelled"}
                return

            if place["distance_km"] < 0.2:
                continue  # Too close to track, skip

            place_point = Point(place["lon"], place["lat"])
            nearest = route_line.interpolate(route_line.project(place_point))

            route = get_road_route(
                float(nearest.y), float(nearest.x),
                place["lat"], place["lon"],
            )

            if route and len(route) > 1:
                road_routes[place["id"]] = route

            if (i + 1) % 5 == 0 or (i + 1) == len(enhanced_places):
                yield {
                    "type": "progress",
                    "message": f"Road routes: {i+1}/{len(enhanced_places)} ({len(road_routes)} found)",
                    "percent": 85 + (i + 1) / len(enhanced_places) * 13,
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
