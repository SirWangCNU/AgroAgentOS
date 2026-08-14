"""Geometry helpers for drawn farm fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyproj import Geod
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from app.exceptions import AppException


MU_IN_SQUARE_METERS = 666.6667
OVERLAP_TOLERANCE_SQUARE_METERS = 1.0
_GEOD = Geod(ellps="WGS84")


@dataclass(frozen=True)
class FieldGeometry:
    normalized: dict[str, Any]
    shape: Polygon
    area_square_meters: float
    area_mu: float
    latitude: float
    longitude: float


def _invalid(detail: str) -> AppException:
    return AppException(
        "地块边界无效",
        code="FIELD_BOUNDARY_INVALID",
        status_code=422,
        detail=detail,
    )


def normalize_boundary(boundary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(boundary, dict):
        raise _invalid("boundary must be a GeoJSON Polygon object")
    if boundary.get("type") != "Polygon":
        raise _invalid("only GeoJSON Polygon is supported")

    coordinates = boundary.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 1:
        raise _invalid("only a single outer ring is supported")

    ring = coordinates[0]
    if not isinstance(ring, list) or len(ring) < 3:
        raise _invalid("outer ring needs at least three vertices")

    normalized_ring: list[list[float]] = []
    for point in ring:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise _invalid("each vertex must be [longitude, latitude]")
        lon, lat = point
        try:
            lon_value = float(lon)
            lat_value = float(lat)
        except (TypeError, ValueError) as exc:
            raise _invalid("coordinates must be numeric") from exc
        if not -180 <= lon_value <= 180 or not -90 <= lat_value <= 90:
            raise _invalid("coordinates are outside valid longitude/latitude ranges")
        normalized_ring.append([lon_value, lat_value])

    if normalized_ring[0] != normalized_ring[-1]:
        normalized_ring.append(normalized_ring[0])
    if len(normalized_ring) < 4:
        raise _invalid("closed ring needs at least four points")

    return {"type": "Polygon", "coordinates": [normalized_ring]}


def analyze_boundary(boundary: dict[str, Any]) -> FieldGeometry:
    normalized = normalize_boundary(boundary)
    shape = Polygon(normalized["coordinates"][0])
    if shape.is_empty or not shape.is_valid:
        raise _invalid("polygon is empty or self-intersecting")

    area_square_meters, _ = _GEOD.geometry_area_perimeter(shape)
    area_square_meters = abs(area_square_meters)
    if area_square_meters <= 0:
        raise _invalid("polygon area must be greater than zero")

    representative = shape.representative_point()
    return FieldGeometry(
        normalized=normalized,
        shape=shape,
        area_square_meters=area_square_meters,
        area_mu=round(area_square_meters / MU_IN_SQUARE_METERS, 4),
        latitude=float(representative.y),
        longitude=float(representative.x),
    )


def intersection_area_square_meters(left: BaseGeometry, right: BaseGeometry) -> float:
    intersection = left.intersection(right)
    if intersection.is_empty or intersection.area == 0:
        return 0.0
    area_square_meters, _ = _GEOD.geometry_area_perimeter(intersection)
    return abs(area_square_meters)
