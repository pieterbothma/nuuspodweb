import re

import pytest
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPolygon

from lib import geo


def _kaapstad_3857_vierkant():
    """A small square in EPSG:3857 centred near Cape Town (~18.4, -33.9)."""
    naar_3857 = Transformer.from_crs(4326, 3857, always_xy=True)
    sentrum_x, sentrum_y = naar_3857.transform(18.4, -33.9)
    kant = 500.0  # metres
    return Polygon(
        [
            (sentrum_x - kant, sentrum_y - kant),
            (sentrum_x + kant, sentrum_y - kant),
            (sentrum_x + kant, sentrum_y + kant),
            (sentrum_x - kant, sentrum_y + kant),
            (sentrum_x - kant, sentrum_y - kant),
        ]
    )


def test_na_ewkt_4326_reprojects_shapely_polygon():
    vierkant = _kaapstad_3857_vierkant()
    ewkt = geo.na_ewkt_4326(vierkant, 3857)

    assert ewkt.startswith("SRID=4326;MULTIPOLYGON")

    koordinate = re.findall(r"-?\d+\.\d+ -?\d+\.\d+", ewkt)
    assert koordinate, "verwag ten minste een koördinaatpaar in die WKT"
    lengtegrade = [float(p.split()[0]) for p in koordinate]
    breedtegrade = [float(p.split()[1]) for p in koordinate]

    assert all(abs(lon - 18.4) < 0.1 for lon in lengtegrade)
    assert all(abs(lat - (-33.9)) < 0.1 for lat in breedtegrade)


def test_na_ewkt_4326_no_reprojection_needed():
    vierkant = Polygon([(18.3, -34.0), (18.5, -34.0), (18.5, -33.8), (18.3, -33.8)])
    ewkt = geo.na_ewkt_4326(vierkant, 4326)
    assert ewkt.startswith("SRID=4326;MULTIPOLYGON")


def test_na_ewkt_4326_accepts_multipolygon_input():
    a = Polygon([(18.3, -34.0), (18.31, -34.0), (18.31, -33.99), (18.3, -33.99)])
    b = Polygon([(18.4, -34.0), (18.41, -34.0), (18.41, -33.99), (18.4, -33.99)])
    multi = MultiPolygon([a, b])
    ewkt = geo.na_ewkt_4326(multi, 4326)
    assert ewkt.startswith("SRID=4326;MULTIPOLYGON")


def test_na_ewkt_4326_rounds_to_six_decimals():
    vierkant = Polygon(
        [
            (18.123456789, -34.123456789),
            (18.223456789, -34.123456789),
            (18.223456789, -34.023456789),
            (18.123456789, -34.023456789),
        ]
    )
    ewkt = geo.na_ewkt_4326(vierkant, 4326)
    for getal in re.findall(r"-?\d+\.(\d+)", ewkt):
        assert len(getal) <= 6


def test_na_ewkt_4326_fixes_invalid_bowtie_geometry():
    # Self-intersecting "bowtie" polygon — invalid until make_valid runs.
    bowtie = Polygon([(18.0, -34.0), (18.1, -33.9), (18.0, -33.9), (18.1, -34.0), (18.0, -34.0)])
    assert not bowtie.is_valid
    ewkt = geo.na_ewkt_4326(bowtie, 4326)
    assert ewkt.startswith("SRID=4326;MULTIPOLYGON")


def test_na_ewkt_4326_rejects_non_polygonal_geometry():
    from shapely.geometry import LineString

    lyn = LineString([(18.0, -34.0), (18.1, -33.9)])
    with pytest.raises(ValueError):
        geo.na_ewkt_4326(lyn, 4326)


def test_na_ewkt_4326_raises_on_sliver_that_vanishes_when_snapped():
    # A valid square with ~1e-14 area at (18, -34): far smaller than the
    # 6-decimal (~1e-6 degree) output grid, so it must collapse to nothing
    # rather than silently serialise as a degenerate zero-area MultiPolygon.
    sny = 1e-7
    fyn_vierkantjie = Polygon(
        [
            (18.0, -34.0),
            (18.0 + sny, -34.0),
            (18.0 + sny, -34.0 + sny),
            (18.0, -34.0 + sny),
        ]
    )
    with pytest.raises(geo.LeeGeometrieFout):
        geo.na_ewkt_4326(fyn_vierkantjie, 4326)


def test_na_ewkt_4326_kaapstad_reprojection_still_reparses_valid():
    from shapely import from_wkt

    ewkt = geo.na_ewkt_4326(_kaapstad_3857_vierkant(), 3857)
    wkt = ewkt.removeprefix("SRID=4326;")
    geom = from_wkt(wkt)
    assert geom.is_valid
    assert not geom.is_empty


def test_na_ewkt_4326_result_always_reparses_valid_and_nonempty():
    from shapely import from_wkt

    gevalle = [
        (Polygon([(18.3, -34.0), (18.5, -34.0), (18.5, -33.8), (18.3, -33.8)]), 4326),
        (
            Polygon(
                [(18.0, -34.0), (18.1, -33.9), (18.0, -33.9), (18.1, -34.0), (18.0, -34.0)]
            ),
            4326,
        ),  # bowtie
    ]
    for vorm, bron_epsg in gevalle:
        ewkt = geo.na_ewkt_4326(vorm, bron_epsg)
        wkt = ewkt.removeprefix("SRID=4326;")
        geom = from_wkt(wkt)
        assert geom.is_valid
        assert not geom.is_empty
