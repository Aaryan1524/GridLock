"""Closest-point distance between project geometries (handoff section 11, invariant I-4).

Nearest points are found in the configured projected CRS, where planar geometry is sound; the
reported distance is the geodesic (WGS84 ellipsoid) distance between those two points. Straight
lines drawn between endpoints are treated as straight in the projected CRS; they are approximations
either way and are labelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import shapely
from pyproj import Geod, Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, transform

from gridlock.models.domain import Point

GEOD = Geod(ellps="WGS84")
WGS84 = "EPSG:4326"


class Projector:
    def __init__(self, crs: str) -> None:
        self._forward = Transformer.from_crs(WGS84, crs, always_xy=True)
        self._inverse = Transformer.from_crs(crs, WGS84, always_xy=True)

    def project(self, geojson: dict[str, Any]) -> BaseGeometry:
        return transform(self._forward.transform, shape(geojson))

    def to_point(self, x: float, y: float, decimals: int) -> Point:
        lon, lat = self._inverse.transform(x, y)
        return Point(lat=round(lat, decimals), lon=round(lon, decimals))


@dataclass(frozen=True)
class Measurement:
    distance_km: float
    closest_points: tuple[Point, Point]
    touching: bool


def geodesic_km(a: Point, b: Point) -> float:
    _, _, metres = GEOD.inv(a.lon, a.lat, b.lon, b.lat)
    return metres / 1000


def measure(a: BaseGeometry, b: BaseGeometry, projector: Projector, distance_decimals: int, coordinate_decimals: int) -> Measurement:
    """Closest points and distance between two projected geometries; symmetric and deterministic."""
    if a.intersects(b):
        # Any shared coordinate is a valid contact point; take the smallest so the choice is reproducible.
        x, y = min(map(tuple, shapely.get_coordinates(a.intersection(b)).tolist()))
        point = projector.to_point(x, y, coordinate_decimals)
        return Measurement(0.0, (point, point), True)
    near_a, near_b = nearest_points(a, b)
    point_a = projector.to_point(near_a.x, near_a.y, coordinate_decimals)
    point_b = projector.to_point(near_b.x, near_b.y, coordinate_decimals)
    return Measurement(round(geodesic_km(point_a, point_b), distance_decimals), (point_a, point_b), False)


def bounding_gap_m(a: BaseGeometry, b: BaseGeometry) -> float:
    """Planar gap between two geometries' bounding boxes; a cheap lower bound on their distance."""
    a_west, a_south, a_east, a_north = a.bounds
    b_west, b_south, b_east, b_north = b.bounds
    dx = max(0.0, b_west - a_east, a_west - b_east)
    dy = max(0.0, b_south - a_north, a_south - b_north)
    return (dx * dx + dy * dy) ** 0.5
