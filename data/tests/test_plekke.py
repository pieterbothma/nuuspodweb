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
        assert set(ry.keys()) == {
            "sp_kode", "naam", "naam_soek", "mp_naam", "mp_naam_soek", "landelik", "geom",
        }
        assert ry["sp_kode"].isdigit()
        assert ry["geom"].startswith("SRID=4326;")


def test_na_mp_naam_soek_stroop_landelike_agtervoegsel_en_normaliseer():
    assert lp.na_mp_naam_soek("Soweto") == "soweto"
    assert lp.na_mp_naam_soek("Emalahleni NU") == "emalahleni"
    assert lp.na_mp_naam_soek("Hartebeesfontein SH") == "hartebeesfontein"
    assert lp.na_mp_naam_soek("Khâi-Ma") == "khai ma"
    assert lp.na_mp_naam_soek(None) is None


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


# --- aliasse.csv: "Die Strand" verwyder (Fix round 1) ------------------------------


def test_aliasse_csv_bevat_nie_meer_die_strand_nie():
    """Produkeienaar: mense sê "Strand", nie "Die Strand" nie — die ry is verwyder."""
    rye = lp.lees_aliasse_csv(lp.ALIASSE_CSV_PAD)
    aliasse = {ry["alias"] for ry in rye}
    assert "Die Strand" not in aliasse


# --- ontleed_argumente: CLI-argumenthantering (suiwer, geen netwerk) ---------------


def test_ontleed_argumente_geen_argumente_gee_bondel_verstek():
    assert lp.ontleed_argumente([]) == {"modus": "vol", "volledig": False}


def test_ontleed_argumente_volledig_vlag():
    assert lp.ontleed_argumente(["--volledig"]) == {"modus": "vol", "volledig": True}


def test_ontleed_argumente_net_aliasse():
    assert lp.ontleed_argumente(["--net-aliasse"]) == {"modus": "net_aliasse"}


def test_ontleed_argumente_net_oorvleueling_vir_enkel_sp_kode():
    assert lp.ontleed_argumente(["--net-oorvleueling-vir", "271002001"]) == {
        "modus": "net_oorvleueling_vir",
        "sp_kodes": ["271002001"],
    }


def test_ontleed_argumente_net_oorvleueling_vir_verskeie_sp_kodes():
    resultaat = lp.ontleed_argumente(
        ["--net-oorvleueling-vir", "271002001,290003001, 292002001 ,966002001"]
    )
    assert resultaat == {
        "modus": "net_oorvleueling_vir",
        "sp_kodes": ["271002001", "290003001", "292002001", "966002001"],
    }


def test_ontleed_argumente_net_oorvleueling_vir_sonder_waarde_gooi():
    with pytest.raises(ValueError):
        lp.ontleed_argumente(["--net-oorvleueling-vir"])


def test_ontleed_argumente_net_oorvleueling_vir_leë_lys_gooi():
    with pytest.raises(ValueError):
        lp.ontleed_argumente(["--net-oorvleueling-vir", " , , "])


def test_ontleed_argumente_onbekende_vlag_gooi():
    with pytest.raises(ValueError):
        lp.ontleed_argumente(["--bondel"])  # ou vlag, nie meer geldig nie ná Fix round 1


def test_ontleed_argumente_te_veel_argumente_gooi():
    with pytest.raises(ValueError):
        lp.ontleed_argumente(["--volledig", "--net-aliasse"])


# --- vervang_verslag_afdeling: suiwer teks-manipulasie ------------------------------


def test_vervang_verslag_afdeling_vervang_bestaande_afdeling():
    teks = "\n".join(
        [
            "# Verslag",
            "",
            "## Aliasse",
            "ou inhoud",
            "",
            "## Ander afdeling",
            "bly onaangeraak",
            "",
        ]
    )
    nuwe = lp.vervang_verslag_afdeling(teks, "## Aliasse", ["nuwe inhoud"])
    assert "ou inhoud" not in nuwe
    assert "nuwe inhoud" in nuwe
    assert "## Ander afdeling" in nuwe
    assert "bly onaangeraak" in nuwe


def test_vervang_verslag_afdeling_voeg_by_as_afwesig():
    teks = "# Verslag\n\n## Bestaande\ninhoud\n"
    nuwe = lp.vervang_verslag_afdeling(teks, "## Nuwe Afdeling", ["bygevoegde inhoud"])
    assert "## Bestaande" in nuwe
    assert "inhoud" in nuwe
    assert "## Nuwe Afdeling" in nuwe
    assert "bygevoegde inhoud" in nuwe
    # oorspronklike afdeling moet steeds voor die nuwe een kom
    assert nuwe.index("## Bestaande") < nuwe.index("## Nuwe Afdeling")


# --- roep_bou_plek_wyke_enkel_plek: --net-oorvleueling-vir se herhaal-logika --------


def test_roep_bou_plek_wyke_enkel_plek_herstel_ná_tydelike_fout(monkeypatch):
    monkeypatch.setattr(lp, "NET_OORVLEUELING_VERTRAGING_S", 0)
    pogings = {"n": 0}

    def wisselvallige_rpc(naam, args):
        pogings["n"] += 1
        if pogings["n"] < 2:
            raise lp.supabase.SupabaseFout("57014 statement timeout")
        return 3

    monkeypatch.setattr(lp.supabase, "rpc", wisselvallige_rpc)
    ingevoeg, _tyd, fout = lp.roep_bou_plek_wyke_enkel_plek(2813)

    assert ingevoeg == 3
    assert fout is None
    assert pogings["n"] == 2


def test_roep_bou_plek_wyke_enkel_plek_gee_op_ná_3_pogings(monkeypatch):
    monkeypatch.setattr(lp, "NET_OORVLEUELING_VERTRAGING_S", 0)
    pogings = {"n": 0}

    def val_misluk(naam, args):
        pogings["n"] += 1
        raise lp.supabase.SupabaseFout("57014 statement timeout")

    monkeypatch.setattr(lp.supabase, "rpc", val_misluk)
    ingevoeg, _tyd, fout = lp.roep_bou_plek_wyke_enkel_plek(2813)

    assert ingevoeg is None
    assert fout is not None
    assert pogings["n"] == lp.NET_OORVLEUELING_HERHALINGS


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


# --- aliasse.csv: final-review fix round (teikens reggemaak, 3 rye verwyder) ----------


def test_aliasse_csv_finale_rye_en_teikens():
    rye = {ry["alias"]: ry for ry in lp.lees_aliasse_csv(lp.ALIASSE_CSV_PAD)}
    assert len(rye) == 10
    # Curated targets are an owner decision for Fase 2b — not in the CSV now.
    for verwyder in ("Pretoria-Oos", "Johannesburg-Suid", "Kaapse Vlakte"):
        assert verwyder not in rye
    # Fase 2b (Piet, 2026-09-15): "Mahikeng" searches the Mafikeng main place (NW383).
    assert rye["Mahikeng"]["mp_naam"] == "Mafikeng"
    assert rye["Mahikeng"]["naam"] == ""
    # Stats SA spells the Port Elizabeth main place "Port Elizaberth".
    assert rye["Port Elizabeth"]["mp_naam"] == "Port Elizaberth"
    assert rye["Gqeberha"]["mp_naam"] == "Port Elizaberth"
    # eThekwini points at the same Durban main place as the Durban row.
    assert (rye["eThekwini"]["naam"], rye["eThekwini"]["mp_naam"]) == (
        rye["Durban"]["naam"],
        rye["Durban"]["mp_naam"],
    )


def test_vind_onopgeloste_aliasse_sintetiese_plekke():
    csv_rye = [
        {"alias": "Kaapstad", "naam": "", "mp_naam": "Cape Town"},
        {"alias": "Nooit-Bestaan-Nie", "naam": "Nêrens", "mp_naam": ""},
    ]
    onopgelos = lp.vind_onopgeloste_aliasse(csv_rye, _sintetiese_plekke())
    assert [ry["alias"] for ry in onopgelos] == ["Nooit-Bestaan-Nie"]


def test_elke_alias_in_csv_los_op_teen_die_bron_shapefile(sp_rekords):
    """Every alias row must resolve to >0 sub places against the real Subplace source
    (the loader hard-fails otherwise), with the expected fan-out for the fixed rows."""
    plekke = []
    for rekord in sp_rekords:
        naam, _landelik = teks.skoon_plek_naam(rekord["SP_NAME"])
        plekke.append({"sp_kode": lp.na_sp_kode(rekord["SP_CODE"]), "naam": naam, "mp_naam": rekord["MP_NAME"]})
    csv_rye = lp.lees_aliasse_csv(lp.ALIASSE_CSV_PAD)
    assert lp.vind_onopgeloste_aliasse(csv_rye, plekke) == []

    per_naam_mp, per_mp = lp.bou_alias_indeks(plekke)
    tal = {
        ry["alias"]: len(lp.los_alias_op(ry, per_naam_mp, per_mp)[0]) for ry in csv_rye
    }
    assert tal["Port Elizabeth"] == 127
    assert tal["Gqeberha"] == 127
    assert tal["eThekwini"] == tal["Durban"] == 21


def test_net_aliasse_faal_hard_en_skryf_niks_as_n_alias_na_0_plekke_oplos(monkeypatch, tmp_path):
    csv_pad = tmp_path / "aliasse.csv"
    csv_pad.write_text(
        "alias,naam,mp_naam,munisipaliteit_naam\n"
        "Kaapstad,,Cape Town,City of Cape Town\n"
        "Nooit-Bestaan-Nie,Nêrens,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lp, "ALIASSE_CSV_PAD", csv_pad)
    monkeypatch.setattr(lp, "VERSLAG_PAD", tmp_path / "plekke-verslag.md")
    monkeypatch.setattr(lp.supabase, "kry_alles", lambda *a, **kw: _sintetiese_plekke())

    def _mag_nie_skryf_nie(*a, **kw):
        raise AssertionError("mag nie na Supabase skryf nie")

    monkeypatch.setattr(lp.supabase, "rpc", _mag_nie_skryf_nie)
    monkeypatch.setattr(lp.supabase, "plaas_bondels", _mag_nie_skryf_nie)

    assert lp.hoof_net_aliasse() == 1
