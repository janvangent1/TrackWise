"""
GPX file parsing — extracts route points from GPX tracks or routes.
Pure logic, no GUI dependencies.
"""

from __future__ import annotations

import io
from typing import List, Tuple

import gpxpy
from geopy.distance import geodesic


RoutePoint = Tuple[float, float]  # (longitude, latitude)


def parse_gpx(content: bytes) -> Tuple[List[RoutePoint], object]:
    """
    Parse GPX bytes and return (route_points, gpx_object).

    route_points: list of (lon, lat) tuples — same format as original app.
    gpx_object:   raw gpxpy.GPX for downstream GPX generation.

    Raises ValueError if no track/route points are found.
    """
    gpx = gpxpy.parse(io.BytesIO(content))

    points: List[RoutePoint] = []

    # Try tracks first
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                points.append((pt.longitude, pt.latitude))

    # Fall back to routes
    if not points:
        for route in gpx.routes:
            for pt in route.points:
                points.append((pt.longitude, pt.latitude))

    if not points:
        raise ValueError("No track or route points found in GPX file.")

    return points, gpx


def calculate_total_distance_km(points: List[RoutePoint]) -> float:
    """Calculate total route distance in km."""
    total = 0.0
    for i in range(1, len(points)):
        pt1 = (points[i - 1][1], points[i - 1][0])  # (lat, lon)
        pt2 = (points[i][1], points[i][0])
        total += geodesic(pt1, pt2).km
    return total
