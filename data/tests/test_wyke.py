"""Pure tests for `laai_wyke` (NC451 recovery). The source-file tests skip when the
MDB shapefile or the IEC NC station PDF is missing. No DB, no network."""

from __future__ import annotations

import re

import pytest

import laai_wyke as lw


# --- NC451-herwinning: wyknommer -> shapefile WardID kartering -----------------------


def test_nc451_wyk_id_versameling_collects_by_ward_number():
    stasie_rye = [
        {"muni_kode": "NC451", "wyk_id": "34501001"},
        {"muni_kode": "NC451", "wyk_id": "34501001"},  # duplicate station, same ward
        {"muni_kode": "NC451", "wyk_id": "34501002"},
        {"muni_kode": "WC011", "wyk_id": "10101003"},  # different muni, ignored
    ]
    resultaat = lw.nc451_wyk_id_versameling(stasie_rye)
    assert resultaat == {1: "34501001", 2: "34501002"}


class _StubVorm:
    def __init__(self, naam):
        self.naam = naam


def test_bou_nc451_wyk_rye_maps_cleanly(monkeypatch):
    monkeypatch.setattr(lw.geo, "na_ewkt_4326", lambda vorm, epsg: f"SRID=4326;{vorm.naam}")

    nc451_wyk_ids = {1: "34501001", 2: "34501002"}
    vorm_rekord_pare = [
        (_StubVorm("vorm1"), {"CAT_B": "NC451", "WardNo": 1, "WardID": "NC451_1"}),
        (_StubVorm("vorm2"), {"CAT_B": "NC451", "WardNo": 2, "WardID": "NC451_2"}),
        (_StubVorm("ander"), {"CAT_B": "WC011", "WardNo": 1, "WardID": "10101001"}),
    ]

    rye, gapings = lw.bou_nc451_wyk_rye(nc451_wyk_ids, vorm_rekord_pare)

    assert gapings == []
    assert rye == [
        {"wyk_id": "34501001", "wyk_nr": 1, "muni_kode": "NC451", "geom": "SRID=4326;vorm1"},
        {"wyk_id": "34501002", "wyk_nr": 2, "muni_kode": "NC451", "geom": "SRID=4326;vorm2"},
    ]


def test_bou_nc451_wyk_rye_reports_gap_when_ward_number_missing_from_shapefile(monkeypatch):
    monkeypatch.setattr(lw.geo, "na_ewkt_4326", lambda vorm, epsg: f"SRID=4326;{vorm.naam}")
    nc451_wyk_ids = {1: "34501001", 3: "34501003"}
    vorm_rekord_pare = [
        (_StubVorm("vorm1"), {"CAT_B": "NC451", "WardNo": 1, "WardID": "NC451_1"}),
        # geen WardNo 3 in die shapefile nie
    ]

    rye, gapings = lw.bou_nc451_wyk_rye(nc451_wyk_ids, vorm_rekord_pare)

    assert len(rye) == 1
    assert rye[0]["wyk_id"] == "34501001"
    assert len(gapings) == 1
    assert "wyk 3" in gapings[0]


def test_bou_nc451_wyk_rye_reports_gap_when_ward_number_ambiguous():
    nc451_wyk_ids = {1: "34501001"}
    vorm_rekord_pare = [
        (_StubVorm("a"), {"CAT_B": "NC451", "WardNo": 1, "WardID": "NC451_1"}),
        (_StubVorm("b"), {"CAT_B": "NC451", "WardNo": 1, "WardID": "NC451_1_dup"}),
    ]

    rye, gapings = lw.bou_nc451_wyk_rye(nc451_wyk_ids, vorm_rekord_pare)

    assert rye == []
    assert len(gapings) == 1
    assert "2 passings" in gapings[0]


def test_bou_nc451_wyk_rye_reports_gap_when_shapefile_ward_has_no_station_ward_id(monkeypatch):
    monkeypatch.setattr(lw.geo, "na_ewkt_4326", lambda vorm, epsg: f"SRID=4326;{vorm.naam}")
    nc451_wyk_ids = {1: "34501001"}
    vorm_rekord_pare = [
        (_StubVorm("vorm1"), {"CAT_B": "NC451", "WardNo": 1, "WardID": "NC451_1"}),
        (_StubVorm("vorm2"), {"CAT_B": "NC451", "WardNo": 2, "WardID": "NC451_2"}),
    ]

    rye, gapings = lw.bou_nc451_wyk_rye(nc451_wyk_ids, vorm_rekord_pare)

    assert [r["wyk_id"] for r in rye] == ["34501001"]
    assert len(gapings) == 1
    assert "shapefile-wyk 2" in gapings[0]


def test_vind_duplikaat_wyk_ids():
    rye = [{"wyk_id": "1"}, {"wyk_id": "2"}, {"wyk_id": "1"}]
    assert lw.vind_duplikaat_wyk_ids(rye) == ["1"]
    assert lw.vind_duplikaat_wyk_ids(rye[:2]) == []


@pytest.mark.skipif(not lw.BRON_NC_STASIES_PDF.exists(), reason="NC-stasie-PDF nie gevind nie")
def test_lees_nc451_wyk_ids_uit_regte_nc_pdf():
    wyk_ids = lw.lees_nc451_wyk_ids()
    assert sorted(wyk_ids) == list(range(1, 16))
    for wyk_nr, wyk_id in wyk_ids.items():
        assert re.fullmatch(r"\d{8}", wyk_id)
        assert int(wyk_id[-3:]) == wyk_nr
    assert len({wid[:5] for wid in wyk_ids.values()}) == 1  # one municipality prefix


@pytest.mark.skipif(
    not (lw.BRON_ZIP.exists() and lw.BRON_NC_STASIES_PDF.exists()),
    reason="MDB-shapefile of NC-stasie-PDF nie gevind nie",
)
def test_nc451_herwinning_teen_regte_shapefile_is_volledig(monkeypatch):
    # Skip the geometry conversion (slow, and covered elsewhere) — only the mapping matters.
    monkeypatch.setattr(lw.geo, "na_ewkt_4326", lambda vorm, epsg: "SRID=4326;stub")
    lw.pak_uit()
    vorm_rekord_pare = lw.lees_vorm_rekord_pare()
    nc451_rekords = [r for _, r in vorm_rekord_pare if r["CAT_B"] == "NC451"]
    assert len(nc451_rekords) == 15

    rye, gapings = lw.bou_nc451_wyk_rye(lw.lees_nc451_wyk_ids(), vorm_rekord_pare)
    assert gapings == []
    assert len(rye) == 15
