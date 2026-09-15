"""Geometry helpers: pyshp/shapely shapes -> EWKT in SRID 4326."""

from __future__ import annotations

from typing import Any

import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

_POLIGONALE_TIPES = ("Polygon", "MultiPolygon")


def _na_shapely(vorm: Any) -> BaseGeometry:
    if isinstance(vorm, BaseGeometry):
        return vorm
    if hasattr(vorm, "__geo_interface__"):
        # pyshp shapes (and anything else exposing the geo interface).
        return shapely_shape(vorm.__geo_interface__)
    raise TypeError(f"onbekende geometrietipe: {type(vorm)!r}")


def _poligonale_multipolygon(geom: BaseGeometry) -> MultiPolygon:
    geom = shapely.make_valid(geom)

    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom
    if geom.geom_type == "GeometryCollection":
        poligone = []
        for deel in geom.geoms:
            if deel.geom_type == "Polygon":
                poligone.append(deel)
            elif deel.geom_type == "MultiPolygon":
                poligone.extend(deel.geoms)
        if not poligone:
            raise ValueError("geen poligonale dele in geometrie nie")
        return MultiPolygon(poligone)

    raise ValueError(f"geen poligonale geometrie nie: {geom.geom_type}")


def na_ewkt_4326(shape: Any, bron_epsg: int) -> str:
    """Convert a pyshp or shapely geometry to EWKT MultiPolygon in SRID 4326.

    Reprojects from bron_epsg when it isn't already 4326, repairs invalid
    geometry with shapely.make_valid (keeping only polygonal parts), and
    rounds coordinates to 6 decimals.
    """
    geom = _na_shapely(shape)

    if geom.geom_type not in _POLIGONALE_TIPES and geom.geom_type != "GeometryCollection":
        # make_valid on a non-polygonal input can't rescue it into a polygon.
        raise ValueError(f"geen poligonale geometrie nie: {geom.geom_type}")

    if bron_epsg != 4326:
        vertaler = Transformer.from_crs(bron_epsg, 4326, always_xy=True)
        geom = shapely_transform(vertaler.transform, geom)

    multi = _poligonale_multipolygon(geom)
    wkt = shapely.to_wkt(multi, rounding_precision=6)
    return f"SRID=4326;{wkt}"
