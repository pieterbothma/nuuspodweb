"""Geometry helpers: pyshp/shapely shapes -> EWKT in SRID 4326."""

from __future__ import annotations

from typing import Any

import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

_POLIGONALE_TIPES = ("Polygon", "MultiPolygon")

# Degrees — matches the 6-decimal output rounding (~0.11m at the equator).
_ROOSTER_GROOTTE = 1e-6


class LeeGeometrieFout(ValueError):
    """Raised when a geometry becomes empty once snapped to the output grid.

    Typically a sliver polygon smaller than 6-decimal-degree precision
    collapses to nothing during snapping. Loaders should catch this, skip
    the feature, and count it in their run report.
    """


def _na_shapely(vorm: Any) -> BaseGeometry:
    if isinstance(vorm, BaseGeometry):
        return vorm
    if hasattr(vorm, "__geo_interface__"):
        # pyshp shapes (and anything else exposing the geo interface).
        return shapely_shape(vorm.__geo_interface__)
    raise TypeError(f"onbekende geometrietipe: {type(vorm)!r}")


def _ekstraheer_poligone(geom: BaseGeometry) -> MultiPolygon:
    """Pull the polygonal parts out of geom as a MultiPolygon (maybe empty)."""
    if geom.is_empty:
        return MultiPolygon()
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom
    if geom.geom_type == "GeometryCollection":
        poligone = []
        for deel in geom.geoms:
            if deel.is_empty:
                continue
            if deel.geom_type == "Polygon":
                poligone.append(deel)
            elif deel.geom_type == "MultiPolygon":
                poligone.extend(p for p in deel.geoms if not p.is_empty)
        return MultiPolygon(poligone)

    raise ValueError(f"geen poligonale geometrie nie: {geom.geom_type}")


def na_ewkt_4326(shape: Any, bron_epsg: int) -> str:
    """Convert a pyshp or shapely geometry to EWKT MultiPolygon in SRID 4326.

    Reprojects from bron_epsg when it isn't already 4326, then — in this
    order, so output rounding can never silently produce invalid or
    degenerate geometry — repairs validity with shapely.make_valid (GEOS's
    precision-reduction step below requires valid input, e.g. a self-
    intersecting "bowtie" polygon would otherwise raise a TopologyException),
    snaps coordinates to the 6-decimal output grid with shapely.set_precision
    (topology-aware — this can itself introduce collapses/self-intersections
    at the new precision), repairs validity again, and keeps only the
    polygonal parts. Raises LeeGeometrieFout if nothing polygonal survives
    (e.g. a sliver smaller than the grid).
    """
    geom = _na_shapely(shape)

    if geom.geom_type not in _POLIGONALE_TIPES and geom.geom_type != "GeometryCollection":
        # make_valid/set_precision on non-polygonal input can't rescue a polygon.
        raise ValueError(f"geen poligonale geometrie nie: {geom.geom_type}")

    if bron_epsg != 4326:
        vertaler = Transformer.from_crs(bron_epsg, 4326, always_xy=True)
        geom = shapely_transform(vertaler.transform, geom)

    geom = shapely.make_valid(geom)
    geom = shapely.set_precision(geom, grid_size=_ROOSTER_GROOTTE)
    geom = shapely.make_valid(geom)
    multi = _ekstraheer_poligone(geom)

    if multi.is_empty:
        raise LeeGeometrieFout("geometrie is leeg ná afronding na die uitsetrooster")

    wkt = shapely.to_wkt(multi, rounding_precision=6)
    return f"SRID=4326;{wkt}"
