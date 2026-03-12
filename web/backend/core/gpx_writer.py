"""
GPX output generation — waypoints-only and enhanced-track modes.
Ported from main_gui_enhanced.py, GUI-free.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import gpxpy
import gpxpy.gpx
from shapely.geometry import Point

from .place_types import PLACE_TYPE_CONFIG, make_waypoint_name

RoutePoint = Tuple[float, float]  # (lon, lat)


def _garmin_symbol(place_type: str) -> str:
    return PLACE_TYPE_CONFIG.get(place_type, {}).get("garmin_symbol", "Flag, Blue")


def _append_custom_waypoints(gpx_out, custom_waypoints: Optional[List[dict]]) -> None:
    """Append custom user-placed waypoints to a GPX object."""
    if not custom_waypoints:
        return
    for cw in custom_waypoints:
        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=float(cw["lat"]),
            longitude=float(cw["lon"]),
            name=cw.get("name", "Waypoint"),
            symbol="Flag, Blue",
        )
        gpx_out.waypoints.append(wpt)


def build_waypoints_only_gpx(
    places: List[dict],
    custom_waypoints: Optional[List[dict]] = None,
) -> str:
    """Return GPX XML string with only waypoints (no original track)."""
    gpx_out = gpxpy.gpx.GPX()
    gpx_out.name = "Places Found Along Route"
    gpx_out.description = "Places found along route within specified distances"

    # Number each type independently
    counters: Dict[str, int] = {}
    for place in sorted(places, key=lambda p: p.get("route_position", 0)):
        pt = place["place_type"]
        counters[pt] = counters.get(pt, 0) + 1
        cfg = PLACE_TYPE_CONFIG.get(pt, {})

        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=place["lat"],
            longitude=place["lon"],
            name=make_waypoint_name(place, counters[pt]),
            description=(
                f"{cfg.get('name', 'Place')}: {place['base_name']} "
                f"- Distance from route: {place['distance_km']} km"
            ),
            symbol=_garmin_symbol(pt),
        )
        gpx_out.waypoints.append(wpt)

    _append_custom_waypoints(gpx_out, custom_waypoints)
    return gpx_out.to_xml()


def build_track_with_waypoints_gpx(
    original_gpx,
    route_points: List[RoutePoint],
    places: List[dict],
    custom_waypoints: Optional[List[dict]] = None,
) -> str:
    """Return GPX XML string with the original track plus waypoints, no route deviations."""
    gpx_out = gpxpy.gpx.GPX()
    gpx_out.name = "Route with Places"
    gpx_out.description = "Original route with selected places as waypoints"

    track = gpxpy.gpx.GPXTrack()
    track.name = "Original Route"
    segment = gpxpy.gpx.GPXTrackSegment()
    for lon, lat in route_points:
        segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
    track.segments.append(segment)
    gpx_out.tracks.append(track)

    counters: Dict[str, int] = {}
    for place in sorted(places, key=lambda p: p.get("route_position", 0)):
        pt = place["place_type"]
        counters[pt] = counters.get(pt, 0) + 1
        cfg = PLACE_TYPE_CONFIG.get(pt, {})
        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=place["lat"],
            longitude=place["lon"],
            name=make_waypoint_name(place, counters[pt]),
            description=(
                f"{cfg.get('name', 'Place')}: {place['base_name']} "
                f"- Distance from route: {place['distance_km']} km"
            ),
            symbol=_garmin_symbol(pt),
        )
        gpx_out.waypoints.append(wpt)

    _append_custom_waypoints(gpx_out, custom_waypoints)
    return gpx_out.to_xml()


def build_enhanced_track_gpx(
    original_gpx,
    route_points: List[RoutePoint],
    places: List[dict],
    road_routes: Dict[str, List[RoutePoint]],
    custom_waypoints: Optional[List[dict]] = None,
) -> str:
    """
    Return GPX XML string with the original track plus deviation legs to each place.
    Also adds waypoints for convenience.
    """
    from geopy.distance import geodesic

    gpx_out = gpxpy.gpx.GPX()
    gpx_out.name = "Enhanced Route with Places"
    gpx_out.description = "Original route with deviations inserted at correct positions"

    track = gpxpy.gpx.GPXTrack()
    track.name = "Enhanced Route with Deviations"
    segment = gpxpy.gpx.GPXTrackSegment()

    if route_points and places:
        # Find insertion points
        insertions = []
        for place in places:
            pid = place["id"]
            if pid not in road_routes:
                continue
            road = road_routes[pid]
            if not road or len(road) < 2:
                continue

            route_start = road[0]  # (lon, lat)
            best_idx, best_dist = 0, float("inf")
            for i, (lon, lat) in enumerate(route_points):
                d = geodesic((lat, lon), (route_start[1], route_start[0])).km
                if d < best_dist:
                    best_dist = d
                    best_idx = i

            insertions.append({"index": best_idx, "place": place, "road": road})

        insertions.sort(key=lambda x: x["index"])

        current_ins = 0
        for i, (lon, lat) in enumerate(route_points):
            segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))

            while current_ins < len(insertions) and insertions[current_ins]["index"] == i:
                dev = insertions[current_ins]
                road = dev["road"]
                place = dev["place"]

                # Out to place
                for rlon, rlat in road:
                    segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=rlat, longitude=rlon))
                segment.points.append(
                    gpxpy.gpx.GPXTrackPoint(latitude=place["lat"], longitude=place["lon"])
                )
                # Return back
                for rlon, rlat in reversed(road):
                    segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=rlat, longitude=rlon))

                current_ins += 1

    else:
        # No places, just copy original track
        for lon, lat in route_points:
            segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))

    track.segments.append(segment)
    gpx_out.tracks.append(track)

    # Add waypoints too
    counters: Dict[str, int] = {}
    for place in sorted(places, key=lambda p: p.get("route_position", 0)):
        pt = place["place_type"]
        counters[pt] = counters.get(pt, 0) + 1
        cfg = PLACE_TYPE_CONFIG.get(pt, {})

        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=place["lat"],
            longitude=place["lon"],
            name=make_waypoint_name(place, counters[pt]),
            description=(
                f"{cfg.get('name', 'Place')}: {place['base_name']} "
                f"- Distance from route: {place['distance_km']} km"
            ),
            symbol=_garmin_symbol(pt),
        )
        gpx_out.waypoints.append(wpt)

    _append_custom_waypoints(gpx_out, custom_waypoints)
    return gpx_out.to_xml()
