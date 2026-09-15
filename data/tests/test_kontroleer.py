"""Tests for kontroleer.py's pure (network-free) helper functions only — the report's
network calls are exercised manually against the real project (see task-8-report.md),
not mocked here."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import kontroleer


def test_ontleed_inhoud_reeks_met_rye():
    assert kontroleer.ontleed_inhoud_reeks("0-0/4485") == 4485


def test_ontleed_inhoud_reeks_leeg():
    assert kontroleer.ontleed_inhoud_reeks("*/0") == 0


def test_ontleed_inhoud_reeks_groot_reeks():
    assert kontroleer.ontleed_inhoud_reeks("0-999/23696") == 23696


def test_bereken_geen_meerderheid_party_oor_helfte_word_uitgesluit():
    uitslae = [
        {"muni_kode": "AAA", "party_naam": "PARTY X", "setels_totaal": 6},
        {"muni_kode": "AAA", "party_naam": "PARTY Y", "setels_totaal": 4},
    ]
    grootte = {"AAA": {"muni_kode": "AAA", "raadsgrootte_totaal": 10, "onafhanklike_setels": 0}}
    assert kontroleer.bereken_geen_meerderheid(uitslae, grootte) == []


def test_bereken_geen_meerderheid_presies_helfte_tel_as_geen_meerderheid():
    uitslae = [
        {"muni_kode": "AAA", "party_naam": "PARTY X", "setels_totaal": 5},
        {"muni_kode": "AAA", "party_naam": "PARTY Y", "setels_totaal": 5},
    ]
    grootte = {"AAA": {"muni_kode": "AAA", "raadsgrootte_totaal": 10, "onafhanklike_setels": 0}}
    resultaat = kontroleer.bereken_geen_meerderheid(uitslae, grootte)
    assert resultaat == [
        {"muni_kode": "AAA", "raadsgrootte_totaal": 10, "grootste_party": "PARTY X", "setels": 5}
    ]


def test_bereken_geen_meerderheid_gebruik_volle_raadsgrootte_nie_net_party_som_nie():
    # Party X het al die party-setels (6/6) maar die raad se volle grootte (10) sluit
    # 4 onafhanklike wykraadslede in — 6 <= 10/2 is vals, so dit IS 'n meerderheid.
    uitslae = [{"muni_kode": "AAA", "party_naam": "PARTY X", "setels_totaal": 6}]
    grootte = {"AAA": {"muni_kode": "AAA", "raadsgrootte_totaal": 10, "onafhanklike_setels": 4}}
    assert kontroleer.bereken_geen_meerderheid(uitslae, grootte) == []


def test_bereken_geen_meerderheid_raad_sonder_uitslae_rye():
    # 'n Raad in stg_raad_grootte_2021 met geen ooreenstemmende party-ry nie (sou nie
    # in werklike data gebeur nie, maar moet nie 'n KeyError gooi nie).
    grootte = {"BBB": {"muni_kode": "BBB", "raadsgrootte_totaal": 5, "onafhanklike_setels": 0}}
    resultaat = kontroleer.bereken_geen_meerderheid([], grootte)
    assert resultaat == [
        {"muni_kode": "BBB", "raadsgrootte_totaal": 5, "grootste_party": None, "setels": 0}
    ]


def test_bereken_geen_meerderheid_sorteer_op_muni_kode():
    uitslae = [
        {"muni_kode": "ZZZ", "party_naam": "P", "setels_totaal": 1},
        {"muni_kode": "AAA", "party_naam": "P", "setels_totaal": 1},
    ]
    grootte = {
        "ZZZ": {"muni_kode": "ZZZ", "raadsgrootte_totaal": 10, "onafhanklike_setels": 0},
        "AAA": {"muni_kode": "AAA", "raadsgrootte_totaal": 10, "onafhanklike_setels": 0},
    }
    resultaat = kontroleer.bereken_geen_meerderheid(uitslae, grootte)
    assert [r["muni_kode"] for r in resultaat] == ["AAA", "ZZZ"]


def test_tel_per_sleutel_groepeer_en_sorteer():
    waardes = ["CPT", "CPT", "TSH", "onbekend-kode"]
    opsoek = {"CPT": "Western Cape", "TSH": "Gauteng"}
    assert kontroleer.tel_per_sleutel(waardes, opsoek) == {
        "Gauteng": 1,
        "ONBEKEND": 1,
        "Western Cape": 2,
    }


def test_vind_ontbrekende():
    alles = {"a", "b", "c"}
    teenwoordig = {"b"}
    assert kontroleer.vind_ontbrekende(alles, teenwoordig) == ["a", "c"]


def test_vind_ontbrekende_niks_ontbreek_nie():
    assert kontroleer.vind_ontbrekende({"a"}, {"a"}) == []


def test_formatteer_telling_reël_sonder_verwagting():
    assert kontroleer.formatteer_telling_reël("stg_plekke", 22196) == "- stg_plekke: **22196**"


def test_formatteer_telling_reël_met_ooreenstemmende_verwagting():
    assert (
        kontroleer.formatteer_telling_reël("distrikte", 44, 44)
        == "- distrikte: **44** (verwag 44)"
    )


def test_formatteer_telling_reël_met_verskil():
    assert (
        kontroleer.formatteer_telling_reël("stg_wyke", 4485, 4488)
        == "- stg_wyke: **4485** (verwag 4488, verskil -3)"
    )
