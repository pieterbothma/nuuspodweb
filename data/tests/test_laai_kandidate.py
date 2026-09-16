"""Tests for laai_kandidate.py — pure, no network.

Database reads/writes are injected into `hoof()` as plain callables, so nothing here
touches Supabase. The fixture tests parse the 2021 Western Cape list already in
`data/bron/` (skipped when that gitignored file is absent).
"""

import random
import re
from pathlib import Path

import pytest

import kandidate_ontleder as ko
import laai_kandidate as lk

BRON_PAD = Path(__file__).parent.parent / "bron" / "kandidate-2021-WC.pdf"
SES_SYFERS = re.compile(r"\d{6,}")
_SINTETIESE_ID = "8001015009087"  # synthetic, 1980-01-01 — not a real person
_KOLOM_INDEKSE = {"muni": 0, "party": 1, "wyklys": 2, "id": 3, "volle_naam": 4, "van": 5}


def _k(
    muni="WC024 - Stellenbosch",
    party="PARTY A",
    wyklys="10204001",
    naam="TOETS",
    van="PERSOON",
    bladsy=1,
    ry=1,
    lêer="kandidate-2026-WC.pdf",
) -> ko.Kandidaat:
    """Build a Kandidaat through the real parser row builder (so its guards apply)."""
    rou = [muni, party, wyklys, "######****00*", naam, van]
    return ko.bou_kandidaat(rou, _KOLOM_INDEKSE, bladsy_nr=bladsy, ry_nr=ry, bron_lêer=lêer)


# Reference data shaped like the stg_ reads: kode -> {tipe, provinsie}, wyk_id -> muni_kode.
MUNIS = {
    "WC024": {"tipe": "plaaslik", "provinsie": "Western Cape"},
    "CPT": {"tipe": "metro", "provinsie": "Western Cape"},
    "DC2": {"tipe": "distrik", "provinsie": "Western Cape"},
}
WYKE = {"10204001": "WC024", "10204002": "WC024", "19100001": "CPT"}


def _klein_stel() -> list[ko.Kandidaat]:
    return [
        _k(party="PARTY B", wyklys="10204001", naam="ANNA", van="AAB", ry=1),
        _k(party="INDEPENDENT", wyklys="10204002", naam="BEN", van="BAB", ry=2),
        _k(party="PARTY A", wyklys="3", naam="CARL", van="CAB", ry=3),
        _k(muni="DC2 - Cape Winelands", party="PARTY A", wyklys="1", naam="DAAN", van="DAB", ry=4),
        _k(muni="CPT - City of Cape Town", party="PARTY C", wyklys="19100001", naam="EVA", van="EAB", ry=5),
    ]


# --- Brief step 1 tests ----------------------------------------------------------------


def test_party_ids_is_stabiel_oor_twee_lopies():
    kandidate = _klein_stel()
    eerste = lk.bou_partye(kandidate)
    geskommel = list(kandidate)
    random.Random(7).shuffle(geskommel)
    tweede = lk.bou_partye(geskommel)
    assert eerste == tweede
    # sorted by name, 1-based, no abbreviation in the source
    assert eerste == [
        {"id": 1, "naam": "PARTY A", "afkorting": None},
        {"id": 2, "naam": "PARTY B", "afkorting": None},
        {"id": 3, "naam": "PARTY C", "afkorting": None},
    ]
    # candidate ids are stable too, whatever order the parser yielded the rows in
    assert lk.bou_kandidaat_rye(kandidate, eerste) == lk.bou_kandidaat_rye(geskommel, tweede)


def test_stembrief_afleiding():
    wyk = _k(wyklys="10204001")
    plaaslik = _k(wyklys="7")
    distrik = _k(muni="DC2 - Cape Winelands", wyklys="2")
    partye = lk.bou_partye([wyk, plaaslik, distrik])
    rye = {r["stembrief"]: r for r in lk.bou_kandidaat_rye([wyk, plaaslik, distrik], partye)}
    assert rye["wyk"]["wyk_id"] == "10204001" and rye["wyk"]["lys_posisie"] is None
    assert rye["pv_plaaslik"]["lys_posisie"] == 7 and rye["pv_plaaslik"]["wyk_id"] is None
    assert rye["pv_distrik"]["muni_kode"] == "DC2" and rye["pv_distrik"]["lys_posisie"] == 2
    # the three pass the ballot-vs-council-type cross-check
    assert lk.valideer(list(rye.values()), partye, MUNIS, WYKE) == []


def test_stembrief_teen_raadstipe_word_gevang():
    # A list position printed against a district without the "DC" prefix would parse as
    # pv_plaaslik; the loader cross-checks against stg_munisipaliteite.tipe.
    kandidaat = _k(muni="DC2 - Cape Winelands", wyklys="2")
    partye = lk.bou_partye([kandidaat])
    ry = lk.bou_kandidaat_rye([kandidaat], partye)[0]
    ry["stembrief"] = "pv_plaaslik"
    foute = lk.valideer([ry], partye, MUNIS, WYKE)
    assert any("stembrief" in f and "distrik" in f for f in foute)


def test_onafhanklike_kandidaat_kry_geen_party_id():
    kandidate = _klein_stel()
    partye = lk.bou_partye(kandidate)
    assert "INDEPENDENT" not in {p["naam"] for p in partye}
    rye = lk.bou_kandidaat_rye(kandidate, partye)
    onafhanklik = [r for r in rye if r["onafhanklik"]]
    assert len(onafhanklik) == 1
    assert onafhanklik[0]["party_id"] is None
    assert all(r["party_id"] is not None for r in rye if not r["onafhanklik"])
    assert lk.valideer(rye, partye, MUNIS, WYKE) == []


def test_geen_id_nommer_beland_in_n_ry_nie():
    kandidate = _klein_stel()
    partye = lk.bou_partye(kandidate)
    rye = lk.bou_kandidaat_rye(kandidate, partye)
    assert lk.kontroleer_id_skans(rye, partye) == []
    for ry in rye + partye:
        for veld, waarde in ry.items():
            if veld in lk.HEELGETAL_TELLERS or veld == "wyk_id":
                continue
            assert not SES_SYFERS.search(str(waarde or "")), veld

    # A row built around the parser (e.g. a future source adapter) that carries an ID:
    # the loader's own guard must catch it, and never echo the value.
    rye[0]["volle_naam"] = f"TOETS {_SINTETIESE_ID}"
    partye[0]["naam"] = _SINTETIESE_ID
    foute = lk.kontroleer_id_skans(rye, partye)
    assert len(foute) == 2
    assert any("volle_naam" in f for f in foute) and any("naam" in f for f in foute)
    assert not any(SES_SYFERS.search(f) for f in foute)


def test_id_skans_vang_n_wyk_id_wat_nie_8_syfers_is_nie_en_n_te_groot_teller():
    kandidate = _klein_stel()
    partye = lk.bou_partye(kandidate)
    rye = lk.bou_kandidaat_rye(kandidate, partye)
    rye[0]["wyk_id"] = _SINTETIESE_ID
    rye[2]["lys_posisie"] = int(_SINTETIESE_ID)
    foute = lk.kontroleer_id_skans(rye, partye)
    assert len(foute) == 2
    assert not any(SES_SYFERS.search(f) for f in foute)


def test_wyk_id_moet_in_stg_wyke_bestaan(tmp_path):
    kandidate = _klein_stel() + [_k(party="PARTY A", wyklys="10299999", naam="ONBEKEND", van="WYK", ry=9)]
    skryf_oproepe = []
    verslag = tmp_path / "kandidate-verslag.md"
    kode = lk.hoof(
        ["--bron", "kandidate-2026-WC.pdf"],
        ontleed=lambda pad: iter(kandidate),
        lees_verwysings=lambda: (MUNIS, WYKE),
        skryf_stg=lambda partye, rye: skryf_oproepe.append((partye, rye)),
        bestaan=lambda pad: True,
        verslag_pad=verslag,
    )
    assert kode == 1
    assert skryf_oproepe == []  # nothing emptied, nothing written
    teks = verslag.read_text()
    assert "10299999" in teks
    assert "NIKS GESKRYF NIE" in teks


# --- Further gates ---------------------------------------------------------------------


def test_onbekende_muni_kode_word_gevang():
    kandidaat = _k(muni="WC999 - Nowhere", wyklys="4")
    partye = lk.bou_partye([kandidaat])
    rye = lk.bou_kandidaat_rye([kandidaat], partye)
    foute = lk.valideer(rye, partye, MUNIS, WYKE)
    assert any("WC999" in f for f in foute)


def test_wyk_van_ander_munisipaliteit_word_gevang():
    kandidaat = _k(muni="CPT - City of Cape Town", wyklys="10204001")
    partye = lk.bou_partye([kandidaat])
    rye = lk.bou_kandidaat_rye([kandidaat], partye)
    foute = lk.valideer(rye, partye, MUNIS, WYKE)
    assert any("10204001" in f and "WC024" in f for f in foute)


def test_duplikate_en_leë_name_word_gevang():
    a = _k(party="PARTY A", wyklys="10204001", naam="SAME", van="NAME", ry=1)
    b = _k(party="PARTY A", wyklys="10204001", naam="SAME", van="NAME", ry=2)
    leeg = _k(party="PARTY A", wyklys="5", naam="", van="NAME", ry=3)
    partye = lk.bou_partye([a, b, leeg])
    rye = lk.bou_kandidaat_rye([a, b, leeg], partye)
    foute = lk.valideer(rye, partye, MUNIS, WYKE)
    assert any("duplika" in f for f in foute)
    assert any("leë naam" in f for f in foute)
    # the empty-name message names the source position, not a person
    assert any("bladsy 1 ry 3" in f for f in foute)


def test_elke_ry_kry_n_unieke_nie_nul_id():
    kandidate = _klein_stel()
    partye = lk.bou_partye(kandidate)
    rye = lk.bou_kandidaat_rye(kandidate, partye)
    assert [r["id"] for r in rye] == list(range(1, len(rye) + 1))
    assert lk.kontroleer_ids(rye, "stg_kandidate") == []
    rye[1]["id"] = None
    rye[2]["id"] = rye[3]["id"]
    foute = lk.kontroleer_ids(rye, "stg_kandidate")
    assert any("nul" in f for f in foute) and any("duplikaat" in f for f in foute)


def test_iec_totale_verskil_is_n_besluit_nie_n_fout_nie():
    tellings = {"wyk_party": 100_000, "wyk_onafhanklik": 975, "pv": 40_241, "totaal": 141_216}
    besluite = lk.vergelyk_met_iec(tellings)
    assert len(besluite) == 2  # ward and total differ
    assert any("100856" in b.replace(",", "").replace(" ", "") for b in besluite)
    assert lk.vergelyk_met_iec(
        {"wyk_party": 100_856, "wyk_onafhanklik": 975, "pv": 40_241, "totaal": 142_072}
    ) == []


def test_skryf_volgorde_en_vorm(tmp_path):
    kandidate = _klein_stel()
    skryf_oproepe = []
    kode = lk.hoof(
        ["--bron", "kandidate-2026-WC.pdf"],
        ontleed=lambda pad: iter(kandidate),
        lees_verwysings=lambda: (MUNIS, WYKE),
        skryf_stg=lambda partye, rye: skryf_oproepe.append((partye, rye)),
        bestaan=lambda pad: True,
        verslag_pad=tmp_path / "v.md",
    )
    assert kode == 0
    assert len(skryf_oproepe) == 1
    partye, rye = skryf_oproepe[0]
    assert len(partye) == 3 and len(rye) == 5
    assert set(rye[0]) == {
        "id", "muni_kode", "stembrief", "wyk_id", "lys_posisie", "party_id", "onafhanklik",
        "volle_naam", "van", "bron_lêer", "bron_ry",
    }


def test_net_ontleed_raak_nie_die_databasis_nie(tmp_path):
    def verbode():
        raise AssertionError("database touched")

    kode = lk.hoof(
        ["--bron", "kandidate-2026-WC.pdf", "--net-ontleed"],
        ontleed=lambda pad: iter(_klein_stel()),
        lees_verwysings=verbode,
        skryf_stg=lambda p, r: verbode(),
        bestaan=lambda pad: True,
        verslag_pad=tmp_path / "v.md",
    )
    assert kode == 0


def test_droogloop_valideer_maar_skryf_nie(tmp_path):
    skryf_oproepe = []
    kode = lk.hoof(
        ["--bron", "kandidate-2026-WC.pdf", "--droogloop"],
        ontleed=lambda pad: iter(_klein_stel()),
        lees_verwysings=lambda: (MUNIS, WYKE),
        skryf_stg=lambda p, r: skryf_oproepe.append(1),
        bestaan=lambda pad: True,
        verslag_pad=tmp_path / "v.md",
    )
    assert kode == 0 and skryf_oproepe == []


def test_ontledingsfout_stop_alles(tmp_path):
    def stukkend(pad):
        yield _k()
        raise ko.KandidaatOntledingFout("kop-ry herken maar kolomme ontbreek: ['van']")

    skryf_oproepe = []
    verslag = tmp_path / "v.md"
    kode = lk.hoof(
        ["--bron", "kandidate-2026-WC.pdf"],
        ontleed=stukkend,
        lees_verwysings=lambda: (MUNIS, WYKE),
        skryf_stg=lambda p, r: skryf_oproepe.append(1),
        bestaan=lambda pad: True,
        verslag_pad=verslag,
    )
    assert kode == 1 and skryf_oproepe == []
    assert "kolomme ontbreek" in verslag.read_text()


def test_bronlêernaam_met_ses_syfers_word_geweier(tmp_path):
    kode = lk.hoof(
        ["--bron", "candidates_20260916.pdf", "--net-ontleed"],
        ontleed=lambda pad: iter(_klein_stel()),
        lees_verwysings=lambda: (MUNIS, WYKE),
        skryf_stg=lambda p, r: None,
        bestaan=lambda pad: True,
        verslag_pad=tmp_path / "v.md",
    )
    assert kode == 1


def test_dieselfde_lêernaam_twee_keer_word_geweier(tmp_path):
    kode = lk.hoof(
        ["--bron", "a/kandidate-2026-WC.pdf", "b/kandidate-2026-WC.pdf", "--net-ontleed"],
        ontleed=lambda pad: iter(_klein_stel()),
        lees_verwysings=lambda: (MUNIS, WYKE),
        skryf_stg=lambda p, r: None,
        bestaan=lambda pad: True,
        verslag_pad=tmp_path / "v.md",
    )
    assert kode == 1


# --- 2021 Western Cape fixture ------------------------------------------------------------


@pytest.fixture(scope="module")
def wc_kandidate():
    if not BRON_PAD.exists():
        pytest.skip(f"bronlêer nie gevind nie: {BRON_PAD}")
    return list(ko.ontleed(BRON_PAD))


def test_vastrigger_partye_en_kandidate(wc_kandidate):
    partye = lk.bou_partye(wc_kandidate)
    rye = lk.bou_kandidaat_rye(wc_kandidate, partye)
    assert len(rye) == 12434
    assert len(partye) == 95
    assert lk.kontroleer_ids(rye, "stg_kandidate") == []
    assert lk.kontroleer_ids(partye, "stg_partye") == []
    assert lk.kontroleer_id_skans(rye, partye) == []
    assert lk.vind_duplikate(rye) == []
    tellings = lk.tel_stembriewe(rye)
    assert tellings == {
        "wyk_party": 7916 - 86,
        "wyk_onafhanklik": 86,
        "pv_plaaslik": 3970,
        "pv_distrik": 548,
        "pv": 3970 + 548,
        "totaal": 12434,
    }


def test_vastrigger_ids_stabiel_oor_twee_lopies(wc_kandidate):
    geskommel = list(wc_kandidate)
    random.Random(2026).shuffle(geskommel)
    assert lk.bou_partye(wc_kandidate) == lk.bou_partye(geskommel)
    assert lk.bou_kandidaat_rye(wc_kandidate, lk.bou_partye(wc_kandidate)) == lk.bou_kandidaat_rye(
        geskommel, lk.bou_partye(geskommel)
    )


def test_vastrigger_geen_id_nommer_in_enige_ry_of_verslag_nie(wc_kandidate, tmp_path):
    verslag = tmp_path / "v.md"
    kode = lk.hoof(
        ["--bron", str(BRON_PAD), "--net-ontleed"],
        ontleed=lambda pad: iter(wc_kandidate),
        verslag_pad=verslag,
    )
    assert kode == 0
    for reël in verslag.read_text().splitlines():
        for treffer in SES_SYFERS.findall(reël):
            assert len(treffer) == 8, reël  # only ward ids


# --- kontroleer.py: candidate sections, gates and the publish diff (pure) -----------------

import kontroleer  # noqa: E402


def _db_rye():
    """stg_kandidate/stg_partye rows as kontroleer reads them back."""
    kandidate = _klein_stel()
    partye = lk.bou_partye(kandidate)
    return lk.bou_kandidaat_rye(kandidate, partye), partye


MUNI_PROVINSIE = {"WC024": "Western Cape", "CPT": "Western Cape", "DC2": "Western Cape"}


def test_kontroleer_kandidate_skoon():
    rye, partye = _db_rye()
    res = kontroleer.ontleed_kandidate(rye, partye, WYKE, MUNI_PROVINSIE)
    assert res["gelaai"] is True
    assert res["tellings"]["totaal"] == 5
    assert res["partye_totaal"] == 3
    assert res["onbekende_wyk"] == []
    assert res["duplikate"] == 0
    assert res["leë_name"] == 0
    assert res["id_vorm"] == []
    assert res["per_provinsie"]["Western Cape"]["totaal"] == 5
    # every ward in WYKE has a ward candidate
    assert res["wyke_sonder_kandidaat"] == {}
    assert kontroleer.evalueer_kandidaat_hekke(res) == []
    # 5 candidates is nowhere near the OVK totals: a decision, not a gate
    assert res["iec_besluite"]


def test_kontroleer_kandidaat_hekke_faal():
    rye, partye = _db_rye()
    rye[0]["wyk_id"] = "10299999"  # not in stg_wyke
    rye[1]["van"] = f"X{_SINTETIESE_ID}"  # ID-shaped field
    rye.append(dict(rye[2], id=99))  # duplicate candidate
    wyke = dict(WYKE, **{"10204009": "WC024"})  # a ward with no candidate
    res = kontroleer.ontleed_kandidate(rye, partye, wyke, MUNI_PROVINSIE)
    assert res["onbekende_wyk"] == ["10299999"]
    assert res["duplikate"] == 1
    assert len(res["id_vorm"]) == 1
    # rye[0] (sorted first) was CPT's only ward candidate, now pointing at an unknown ward
    assert res["wyke_sonder_kandidaat"] == {"CPT": ["19100001"], "WC024": ["10204009"]}
    hekke = kontroleer.evalueer_kandidaat_hekke(res)
    assert len(hekke) == 3
    assert not any(SES_SYFERS.search(h) and "10299999" not in h for h in hekke)


def test_kontroleer_kandidate_nog_nie_gelaai_nie_is_geen_hek_nie():
    res = {"gelaai": False, "totaal": 0, "partye_totaal": 0}
    assert kontroleer.evalueer_kandidaat_hekke(res) == []
    assert kontroleer.evalueer_kandidaat_hekke(None) == []
    reëls = kontroleer.formatteer_kandidaat_afdeling(res, {})
    assert any("nog nie gelaai nie" in r for r in reëls)


def test_kontroleer_kandidaat_afdeling_wys_iec_vergelyking():
    rye, partye = _db_rye()
    res = kontroleer.ontleed_kandidate(rye, partye, WYKE, MUNI_PROVINSIE)
    teks = "\n".join(kontroleer.formatteer_kandidaat_afdeling(res, {}))
    assert "142 072" in teks and "100 856" in teks and "40 241" in teks and "975" in teks
    assert "Besluit" in teks


def test_kontroleer_kandidaat_afdeling_fout():
    reëls = kontroleer.formatteer_kandidaat_afdeling(None, {"kandidate": "statement timeout"})
    assert reëls == ["- kon nie gekontroleer word nie: statement timeout"]


def test_nog_nie_gelaai_nie_laat_kandidate_val_sodra_gelaai():
    leeg = kontroleer.formatteer_nie_gelaai({"kandidate_totaal": 0, "stembrief_volgorde_totaal": 0})
    assert any("stg_kandidate" in r for r in leeg)
    assert any("stg_stembrief_volgorde" in r for r in leeg)
    gelaai = kontroleer.formatteer_nie_gelaai({"kandidate_totaal": 12, "stembrief_volgorde_totaal": 0})
    assert not any("stg_kandidate" in r for r in gelaai)
    assert any("stg_stembrief_volgorde" in r and "23 Sep" in r for r in gelaai)


def test_vergelyk_tabelle():
    stg = [{"k": "a", "v": 1}, {"k": "b", "v": 2}, {"k": "d", "v": 4}]
    pub = [{"k": "a", "v": 1}, {"k": "b", "v": 3}, {"k": "c", "v": 9}]
    res = kontroleer.vergelyk_tabelle(stg, pub, ("k",))
    assert res["stg"] == 3 and res["publiek"] == 3
    assert res["toegevoeg"] == 1 and res["verwyder"] == 1 and res["verander"] == 1
    assert res["voorbeelde"]["toegevoeg"] == ["d"]
    assert res["voorbeelde"]["verwyder"] == ["c"]
    assert res["voorbeelde"]["verander"] == ["b"]
    assert kontroleer.vergelyk_tabelle(stg, list(stg), ("k",))["gelyk"] is True


def test_vergelyk_tabelle_saamgestelde_sleutel():
    stg = [{"a": "x", "b": "1", "v": 0.5}]
    pub = [{"a": "x", "b": "1", "v": 0.25}]
    res = kontroleer.vergelyk_tabelle(stg, pub, ("a", "b"))
    assert res["verander"] == 1 and res["voorbeelde"]["verander"] == ["x|1"]


def test_diff_spek_dek_al_11_publieke_tabelle():
    assert set(kontroleer.DIFF_SPEK) == {
        "munisipaliteite", "wyke", "stemstasies", "plekke", "plek_wyke", "plek_aliasse",
        "raad_uitslae_2021", "raad_grootte_2021", "partye", "kandidate", "stembrief_volgorde",
    }
    for sleutel, kolomme in kontroleer.DIFF_SPEK.values():
        assert "geom" not in kolomme
        assert set(sleutel) <= set(kolomme.split(","))
