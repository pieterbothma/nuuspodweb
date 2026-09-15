"""Pure tests for `laai_plekke` — reads the real Subplace .dbf only, no DB, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

import laai_plekke as lp
from lib import teks

BRON_ZIP = Path(__file__).parent.parent / "bron" / "plekke" / "Subplace.zip"

pytestmark = pytest.mark.skipif(not BRON_ZIP.exists(), reason=f"bronlêer nie gevind nie: {BRON_ZIP}")


@pytest.fixture(scope="module")
def sp_rekords() -> list[dict]:
    lp.pak_uit()
    return [rekord for _, rekord in lp.lees_vorm_rekord_pare()]


def test_sp_count_is_22196(sp_rekords):
    assert len(sp_rekords) == 22196


def test_brooklyn_in_at_least_4_records_across_3_mn_names(sp_rekords):
    brooklyn = [r for r in sp_rekords if "brooklyn" in r["SP_NAME"].lower()]
    assert len(brooklyn) >= 4
    assert len({r["MN_NAME"] for r in brooklyn}) >= 3


def test_waterkloof_record_exists_in_tshwane(sp_rekords):
    waterkloof_tshwane = [
        r for r in sp_rekords if "waterkloof" in r["SP_NAME"].lower() and "tshwane" in r["MN_NAME"].lower()
    ]
    assert len(waterkloof_tshwane) >= 1


def test_skoon_plek_naam_toegepas_op_3_regte_rekords():
    # "Kliprand SP" -> stedelik ("SP"-agtervoegsel gestroop, landelik=False)
    naam, landelik = teks.skoon_plek_naam("Kliprand SP")
    assert naam == "Kliprand"
    assert landelik is False

    # "Matzikama NU" -> landelik ("NU"-agtervoegsel gestroop, landelik=True)
    naam, landelik = teks.skoon_plek_naam("Matzikama NU")
    assert naam == "Matzikama"
    assert landelik is True

    # "Hartebeesfontein SH" -> landelik ("SH"-agtervoegsel gestroop, landelik=True)
    naam, landelik = teks.skoon_plek_naam("Hartebeesfontein SH")
    assert naam == "Hartebeesfontein"
    assert landelik is True


def test_bou_plek_rye_shape(sp_rekords):
    vorm_rekord_pare = lp.lees_vorm_rekord_pare()
    rye, oorgeslaan_geom = lp.bou_plek_rye(vorm_rekord_pare[:50])
    assert oorgeslaan_geom == [] or isinstance(oorgeslaan_geom, list)
    for ry in rye:
        assert set(ry.keys()) == {"sp_kode", "naam", "naam_soek", "mp_naam", "landelik", "geom"}
        assert ry["sp_kode"].isdigit()
        assert ry["geom"].startswith("SRID=4326;")


def test_sp_kode_is_clean_integer_text(sp_rekords):
    vorm_rekord_pare = lp.lees_vorm_rekord_pare()
    rye, _ = lp.bou_plek_rye(vorm_rekord_pare[:5])
    for ry in rye:
        assert "." not in ry["sp_kode"]


# --- alias-resolusie (suiwer, sintetiese data) ----------------------------------


def _sintetiese_plekke() -> list[dict]:
    return [
        {"sp_kode": "1", "naam": "Cape Town CBD", "mp_naam": "Cape Town"},
        {"sp_kode": "2", "naam": "Bellville", "mp_naam": "Cape Town"},
        {"sp_kode": "3", "naam": "Pretoria West", "mp_naam": "Pretoria"},
        {"sp_kode": "4", "naam": "Brooklyn", "mp_naam": "Pretoria"},
        {"sp_kode": "5", "naam": "Brooklyn", "mp_naam": "Overberg"},
    ]


def test_los_alias_op_naam_en_mp_naam_presies():
    per_naam_mp, per_mp = lp.bou_alias_indeks(_sintetiese_plekke())
    sp_kodes, _ = lp.los_alias_op({"naam": "Pretoria West", "mp_naam": "Pretoria"}, per_naam_mp, per_mp)
    assert sp_kodes == ["3"]


def test_los_alias_op_net_naam_bybring_oor_alle_mp_naam():
    per_naam_mp, per_mp = lp.bou_alias_indeks(_sintetiese_plekke())
    sp_kodes, _ = lp.los_alias_op({"naam": "Brooklyn", "mp_naam": ""}, per_naam_mp, per_mp)
    assert sorted(sp_kodes) == ["4", "5"]


def test_los_alias_op_net_mp_naam_bring_hele_hoofplek_by():
    per_naam_mp, per_mp = lp.bou_alias_indeks(_sintetiese_plekke())
    sp_kodes, _ = lp.los_alias_op({"naam": "", "mp_naam": "Cape Town"}, per_naam_mp, per_mp)
    assert sorted(sp_kodes) == ["1", "2"]


def test_los_alias_op_onopgelos_gee_leë_lys():
    per_naam_mp, per_mp = lp.bou_alias_indeks(_sintetiese_plekke())
    sp_kodes, _ = lp.los_alias_op({"naam": "Nêrens Bestaande Plek", "mp_naam": ""}, per_naam_mp, per_mp)
    assert sp_kodes == []


# --- _roep_bou_plek_wyke_reeks: halveer op statement-timeout (suiwer, gemock) --------


def test_roep_bou_plek_wyke_reeks_halveer_op_timeout(monkeypatch):
    """'n Reeks wat misluk, word gehalveer; elke helfte word apart aangeroep."""
    oproepe: list[tuple[int, int]] = []

    def vals_rpc(naam, args):
        van, tot = args["van"], args["tot"]
        oproepe.append((van, tot))
        if (van, tot) == (1, 10):
            raise lp.supabase.SupabaseFout("57014 statement timeout")
        return tot - van + 1  # elke plek in die reeks "kry" een wyk

    monkeypatch.setattr(lp.supabase, "rpc", vals_rpc)
    tydsberekenings: list = []
    oorgeslaan: list = []
    totaal = lp._roep_bou_plek_wyke_reeks(1, 10, tydsberekenings, oorgeslaan)

    assert (1, 10) in oproepe  # die aanvanklike, mislukte poging
    assert (1, 5) in oproepe
    assert (6, 10) in oproepe
    assert totaal == 10  # 5 + 5, ongeag die halvering
    assert len(tydsberekenings) == 2  # net die suksesvolle helftes word aangeteken
    assert oorgeslaan == []


def test_roep_bou_plek_wyke_reeks_slaan_hardnekkige_enkel_plek_oor(monkeypatch):
    monkeypatch.setattr(lp, "ENKEL_PLEK_HERHALING_VERTRAGING_S", 0)  # nie regtig slaap in toetse nie

    def val_misluk(naam, args):
        raise lp.supabase.SupabaseFout("57014 statement timeout")

    monkeypatch.setattr(lp.supabase, "rpc", val_misluk)
    tydsberekenings: list = []
    oorgeslaan: list = []
    totaal = lp._roep_bou_plek_wyke_reeks(5, 5, tydsberekenings, oorgeslaan)

    assert totaal == 0
    assert tydsberekenings == []
    assert len(oorgeslaan) == 1
    assert oorgeslaan[0][:2] == (5, 5)


def test_roep_bou_plek_wyke_reeks_herstel_ná_tydelike_enkel_plek_fout(monkeypatch):
    monkeypatch.setattr(lp, "ENKEL_PLEK_HERHALING_VERTRAGING_S", 0)
    pogings = {"n": 0}

    def wisselvallige_rpc(naam, args):
        pogings["n"] += 1
        if pogings["n"] < 2:
            raise lp.supabase.SupabaseFout("57014 statement timeout")
        return 1

    monkeypatch.setattr(lp.supabase, "rpc", wisselvallige_rpc)
    tydsberekenings: list = []
    oorgeslaan: list = []
    totaal = lp._roep_bou_plek_wyke_reeks(9, 9, tydsberekenings, oorgeslaan)

    assert totaal == 1
    assert oorgeslaan == []
    assert len(tydsberekenings) == 1


def test_bou_alias_rye_skei_opgelos_van_onopgelos():
    per_naam_mp, per_mp = lp.bou_alias_indeks(_sintetiese_plekke())
    csv_rye = [
        {"alias": "Kaapstad", "naam": "", "mp_naam": "Cape Town"},
        {"alias": "Nooit-Bestaan-Nie", "naam": "Nêrens", "mp_naam": ""},
    ]
    aliasse, onopgelos = lp.bou_alias_rye(csv_rye, per_naam_mp, per_mp)
    assert {a["sp_kode"] for a in aliasse if a["alias"] == "Kaapstad"} == {"1", "2"}
    assert len(onopgelos) == 1
    assert onopgelos[0]["alias"] == "Nooit-Bestaan-Nie"
