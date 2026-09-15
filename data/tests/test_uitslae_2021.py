"""Toetse vir `laai_uitslae_2021.py` — 2021-raadsetel-ontleder.

Eenheidstoetse (kop-herkenning, URL-bou, provinsie-vouer) loop sonder netwerk of PDF.
Die fixture-toetse ontleed die werklike EC135-vastrigger
(`data/bron/setelberekening-2021-EC135.pdf`, Intsika Yethu, Oos-Kaap) en word
oorgeslaan as dié lêer nie teenwoordig is nie (gitignored bronlêer).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import laai_uitslae_2021 as lu

BRON_PAD = Path(__file__).parent.parent / "bron" / "setelberekening-2021-EC135.pdf"

pytestmark_fixture = pytest.mark.skipif(
    not BRON_PAD.exists(), reason=f"bronlêer nie gevind nie: {BRON_PAD}"
)


# --- eenheidstoetse: provinsie -> IEC-vouerkode -------------------------------------


def test_provinsie_na_vouer_bekende_provinsies():
    assert lu.provinsie_na_vouer("Eastern Cape") == "EC"
    assert lu.provinsie_na_vouer("Western Cape") == "WP"
    assert lu.provinsie_na_vouer("Gauteng") == "GP"
    assert lu.provinsie_na_vouer("KwaZulu-Natal") == "KN"
    assert lu.provinsie_na_vouer("Limpopo") == "NP"


def test_provinsie_na_vouer_onbekende_provinsie_gooi_fout():
    with pytest.raises(lu.OntledingsFout):
        lu.provinsie_na_vouer("Neverland")


def test_bou_url():
    assert lu.bou_url("EC135", "Eastern Cape") == (
        "https://results.elections.org.za/home/LGEPublicReports/1091/"
        "Seat%20Calculation%20Detail/EC/EC135.pdf"
    )
    assert lu.bou_url("CPT", "Western Cape") == (
        "https://results.elections.org.za/home/LGEPublicReports/1091/"
        "Seat%20Calculation%20Detail/WP/CPT.pdf"
    )


# --- eenheidstoetse: setel-tabel-kop-herkenning (geen PDF nodig nie) ----------------


def test_is_setel_tabel_kop_presiese_koptekste():
    kop = ["Party Name", "Total Party\nSeats (x)", "Ward Seats (y)", "PR List Seats\n(x-y)", None]
    assert lu.is_setel_tabel_kop(kop)


def test_is_setel_tabel_kop_verwerp_ander_tabelle():
    # Die eerste (kwota-)tabel op bladsy 1 begin ook met "Party Name" maar dra ander
    # kolomme — moet nie per ongeluk hier pas nie.
    kop = ["Party Name", "Total Valid\nVotes", "Total Valid\nVotes /\nQuota", "Round 1\nAllocation"]
    assert not lu.is_setel_tabel_kop(kop)


def test_is_setel_tabel_kop_leë_of_te_kort():
    assert not lu.is_setel_tabel_kop([])
    assert not lu.is_setel_tabel_kop(["Party Name", "Total Party\nSeats (x)"])


# --- eenheidstoetse: ontleed_setel_tabel (sintetiese tabel, geen PDF nodig nie) -----


def test_ontleed_setel_tabel_party_rye_en_raadsgrootte():
    tabel = [
        ["Party Name", "Total Party\nSeats (x)", "Ward Seats (y)", "PR List Seats\n(x-y)", None],
        ["AFRICAN NATIONAL CONGRESS", "35", "21", "14", None],
        ["DEMOCRATIC ALLIANCE", "1", "0", "1", None],
        ["Total Party Seats", "42", "21", "21", None],
        ["Independents", None, "0", "", None],
        ["Total Seats", None, "21", "21", "42"],
    ]
    rye, raadsgrootte, waarskuwings = lu.ontleed_setel_tabel(tabel, "EC135")
    assert raadsgrootte == 42
    assert waarskuwings == []
    assert rye == [
        {
            "muni_kode": "EC135",
            "party_naam": "AFRICAN NATIONAL CONGRESS",
            "setels_wyk": 21,
            "setels_pv": 14,
            "setels_totaal": 35,
        },
        {
            "muni_kode": "EC135",
            "party_naam": "DEMOCRATIC ALLIANCE",
            "setels_wyk": 0,
            "setels_pv": 1,
            "setels_totaal": 1,
        },
    ]


def test_ontleed_setel_tabel_party_naam_span_meer_as_een_lyn():
    tabel = [
        ["Party Name", "Total Party\nSeats (x)", "Ward Seats (y)", "PR List Seats\n(x-y)", None],
        ["AFRICAN TRANSFORMATION\nMOVEMENT", "0", "0", "0", None],
        ["Total Party Seats", "0", "0", "0", None],
    ]
    rye, _, _ = lu.ontleed_setel_tabel(tabel, "EC135")
    assert rye[0]["party_naam"] == "AFRICAN TRANSFORMATION MOVEMENT"
    assert "\n" not in rye[0]["party_naam"]


def test_ontleed_setel_tabel_wyk_plus_pv_moet_totaal_wees():
    # 'n Ry waar wyk+pv != totaal moet 'n waarskuwing gee maar steeds gelaai word
    # (die brondata word ongewysig gelaai; die afwyking word aangeteken).
    tabel = [
        ["Party Name", "Total Party\nSeats (x)", "Ward Seats (y)", "PR List Seats\n(x-y)", None],
        ["FOUTIEWE PARTY", "5", "2", "2", None],
    ]
    rye, _, waarskuwings = lu.ontleed_setel_tabel(tabel, "EC135")
    assert len(rye) == 1
    assert len(waarskuwings) == 1
    assert "FOUTIEWE PARTY" in waarskuwings[0]


def test_ontleed_setel_tabel_stroop_oormaat_voetnootmerker():
    # Die IEC merk die party wat 'n oormaat setel veroorsaak het met 'n hangende "*"
    # (voetnoot: "Denotes the party that resulted in an excessive seat(s)..."). Die
    # merker verskyn op sy eie fisiese lyn ná die partynaam (bv. "AFRICAN NATIONAL
    # CONGRESS\n*") — na whitespace-samevoeging lyk dit soos "... *" met 'n spasie
    # voor die asterisk. Moet gestroop word, nooit in party_naam beland nie.
    tabel = [
        ["Party Name", "Total Party\nSeats (x)", "Ward Seats (y)", "PR List Seats\n(x-y)", None],
        ["AFRICAN NATIONAL CONGRESS\n*", "38", "38", "0", None],
        ["DEMOCRATIC ALLIANCE *", "1", "0", "1", None],
    ]
    rye, _, waarskuwings = lu.ontleed_setel_tabel(tabel, "GT421")
    party_name = [r["party_naam"] for r in rye]
    assert party_name == ["AFRICAN NATIONAL CONGRESS", "DEMOCRATIC ALLIANCE"]
    assert not any("*" in n for n in party_name)
    # die merker se stropping is nie 'n ontledingsprobleem nie — geen waarskuwing hieroor
    assert waarskuwings == []


# --- fixture-toetse: die werklike EC135-PDF (RED tot laai_uitslae_2021.py bestaan) --


@pytest.mark.skipif(not BRON_PAD.exists(), reason=f"bronlêer nie gevind nie: {BRON_PAD}")
class TestOntleedPdfEc135:
    @staticmethod
    @pytest.fixture(scope="class")
    def resultaat():
        return lu.ontleed_pdf(BRON_PAD, "EC135")

    def test_sewe_partye(self, resultaat):
        assert len(resultaat.party_rye) == 7

    def test_elke_ry_se_muni_kode(self, resultaat):
        assert all(r["muni_kode"] == "EC135" for r in resultaat.party_rye)

    def test_wyk_plus_pv_is_totaal_vir_elke_party(self, resultaat):
        for ry in resultaat.party_rye:
            assert ry["setels_wyk"] + ry["setels_pv"] == ry["setels_totaal"]

    def test_som_van_totale_is_raadsgrootte(self, resultaat):
        raadsgrootte = sum(r["setels_totaal"] for r in resultaat.party_rye)
        assert raadsgrootte == 42
        assert resultaat.raadsgrootte == 42
        assert resultaat.raadsgrootte_koptekst == 42

    def test_bekende_party_teenwoordig(self, resultaat):
        anc = next(
            r for r in resultaat.party_rye if r["party_naam"] == "AFRICAN NATIONAL CONGRESS"
        )
        assert anc["setels_wyk"] == 21
        assert anc["setels_pv"] == 14
        assert anc["setels_totaal"] == 35

    def test_geen_party_naam_dra_nuwe_lyne_nie(self, resultaat):
        assert all("\n" not in r["party_naam"] for r in resultaat.party_rye)

    def test_geen_waarskuwings_vir_skoon_vastrigger(self, resultaat):
        assert resultaat.waarskuwings == []

    def test_geen_onafhanklikes_en_geen_verklaarde_verskil(self, resultaat):
        # EC135 dra "Independent Ward Councillors Elected - (C) 0" — raadsgrootte
        # (42) klop reeds presies met die koptekssyfer (B=42), so daar's niks om te
        # verklaar nie.
        assert resultaat.onafhanklike_setels == 0
        assert resultaat.verklaarde_verskille == []


# --- eenheidstoets: setel-tabel wat oor meer as een bladsy loop (groot rade) --------


class _NepBladsy:
    def __init__(self, tabelle: list[list[list]]):
        self._tabelle = tabelle

    def extract_tables(self):
        return self._tabelle


class _NepPdf:
    def __init__(self, bladsye: list[_NepBladsy]):
        self.pages = bladsye


def test_kry_setel_tabel_kombineer_oor_meer_as_een_bladsy():
    kop = ["Party Name", "Total Party\nSeats (x)", "Ward Seats (y)", "PR List Seats\n(x-y)"]
    bladsy1 = _NepBladsy([[kop, ["ACTIONSA", "44", "0", "44"], ["AL JAMA-AH", "3", "1", "2"]]])
    bladsy2 = _NepBladsy(
        [[kop, ["DEMOCRATIC ALLIANCE", "71", "43", "28"], ["Total Party Seats", "118", "44", "74"]]]
    )
    nep_pdf = _NepPdf([bladsy1, bladsy2])

    tabel = lu._kry_setel_tabel(nep_pdf)

    assert tabel is not None
    # een kopry, gevolg deur al die party-/somrye uit BEIDE bladsye
    assert tabel[0] == kop
    etikette = [ry[0] for ry in tabel[1:]]
    assert etikette == ["ACTIONSA", "AL JAMA-AH", "DEMOCRATIC ALLIANCE", "Total Party Seats"]


def test_kry_setel_tabel_gee_none_as_geen_tabel_pas_nie():
    ander_kop = ["Party Name", "Total Valid\nVotes", "Total Valid\nVotes /\nQuota", "Round 1\nAllocation"]
    bladsy1 = _NepBladsy([[ander_kop, ["ANC", "100", "5.0", "5"]]])
    assert lu._kry_setel_tabel(_NepPdf([bladsy1])) is None


# --- eenheidstoetse: koptekssyfer (B) teenoor party-som, verklaar deur onafhanklikes -


def test_kry_koptekstal_vind_ry_op_enige_bladsy():
    bladsy1 = _NepBladsy(
        [[["Total Seats Available in Municipality - (B)", "64", ""]]]
    )
    assert lu._kry_koptekstal(_NepPdf([bladsy1]), lu.RAADSGROOTTE_ETIKET) == 64


def test_kry_koptekstal_ontbrekende_etiket_gee_none():
    bladsy1 = _NepBladsy([[["iets anders", "1", ""]]])
    assert lu._kry_koptekstal(_NepPdf([bladsy1]), lu.RAADSGROOTTE_ETIKET) is None


# --- eenheidstoetse: verifieer_raadsgrootte (harde poort voor die Supabase-laai) ----


def test_verifieer_raadsgrootte_klop_gee_leë_lys():
    party_rye = [
        {"muni_kode": "EC135", "party_naam": "ANC", "setels_wyk": 21, "setels_pv": 14, "setels_totaal": 35},
        {"muni_kode": "EC135", "party_naam": "DA", "setels_wyk": 0, "setels_pv": 7, "setels_totaal": 7},
    ]
    raad_grootte_rye = [{"muni_kode": "EC135", "raadsgrootte_totaal": 42, "onafhanklike_setels": 0}]
    assert lu.verifieer_raadsgrootte(party_rye, raad_grootte_rye) == []


def test_verifieer_raadsgrootte_hou_rekening_met_onafhanklikes():
    party_rye = [
        {"muni_kode": "EC109", "party_naam": "ANC", "setels_wyk": 6, "setels_pv": 0, "setels_totaal": 6},
        {"muni_kode": "EC109", "party_naam": "DA", "setels_wyk": 0, "setels_pv": 5, "setels_totaal": 5},
    ]
    # raadsgrootte_totaal (12) = party-som (11) + 1 onafhanklike — moet klop, geen probleem.
    raad_grootte_rye = [{"muni_kode": "EC109", "raadsgrootte_totaal": 12, "onafhanklike_setels": 1}]
    assert lu.verifieer_raadsgrootte(party_rye, raad_grootte_rye) == []


def test_verifieer_raadsgrootte_teenstrydigheid_gee_probleem():
    party_rye = [
        {"muni_kode": "XX000", "party_naam": "ANC", "setels_wyk": 6, "setels_pv": 0, "setels_totaal": 6},
    ]
    # raadsgrootte_totaal (12) != party-som (6) + onafhanklikes (1) = 7
    raad_grootte_rye = [{"muni_kode": "XX000", "raadsgrootte_totaal": 12, "onafhanklike_setels": 1}]
    probleme = lu.verifieer_raadsgrootte(party_rye, raad_grootte_rye)
    assert len(probleme) == 1
    assert "XX000" in probleme[0]


# --- eenheidstoetse: kry_geen_meerderheid_rade teen die VOLLE raadsgrootte ----------


def test_geen_meerderheid_gebruik_volle_raadsgrootte_nie_net_party_som_nie():
    # EC109-agtige geval: party-som is 11 (ANC 6, DA 5), maar die raad het 12 setels
    # (1 onafhanklike wykraadslid wat geen party s'n is nie). Teen die party-som alleen
    # sou ANC (6) 'n "meerderheid" gelyk het (6*2=12 > 11); teen die VOLLE raad (12) is
    # 6*2=12 NIE > 12 nie — geen party het dus 'n werklike meerderheid nie.
    party_rye = [
        {"muni_kode": "EC109", "party_naam": "ANC", "setels_wyk": 6, "setels_pv": 0, "setels_totaal": 6},
        {"muni_kode": "EC109", "party_naam": "DA", "setels_wyk": 0, "setels_pv": 5, "setels_totaal": 5},
    ]
    raad_grootte_rye = [{"muni_kode": "EC109", "raadsgrootte_totaal": 12, "onafhanklike_setels": 1}]

    geen_meerderheid = lu.kry_geen_meerderheid_rade(party_rye, raad_grootte_rye)

    assert len(geen_meerderheid) == 1
    assert geen_meerderheid[0]["muni_kode"] == "EC109"
    assert geen_meerderheid[0]["raadsgrootte"] == 12


def test_geen_meerderheid_werklike_meerderheid_word_uitgesluit():
    party_rye = [
        {"muni_kode": "EC135", "party_naam": "ANC", "setels_wyk": 21, "setels_pv": 14, "setels_totaal": 35},
        {"muni_kode": "EC135", "party_naam": "DA", "setels_wyk": 0, "setels_pv": 7, "setels_totaal": 7},
    ]
    raad_grootte_rye = [{"muni_kode": "EC135", "raadsgrootte_totaal": 42, "onafhanklike_setels": 0}]
    assert lu.kry_geen_meerderheid_rade(party_rye, raad_grootte_rye) == []


# --- fixture-toets: 'n regte, tiny 2-bladsy PDF wat die meerbladsy-bug oefen ---------

MEERBLADSY_FIXTURE_PAD = (
    Path(__file__).parent / "fixtures" / "setelberekening-2021-LIM354-meerbladsy.pdf"
)


@pytest.mark.skipif(
    not MEERBLADSY_FIXTURE_PAD.exists(), reason=f"vastrigger nie gevind nie: {MEERBLADSY_FIXTURE_PAD}"
)
def test_ontleed_pdf_meerbladsy_vastrigger_lim354():
    # Bladsye 3-4 (van die volle LIM354/Polokwane-PDF, 90-setel raad) geknip in 'n eie
    # klein vastrigger: die setel-opsplitsingstabel begin op die EERSTE bladsy van hierdie
    # 2-bladsy-lêer en gaan voort op die tweede — presies die situasie wat die
    # meerbladsy-bug (net die eerste bladsy se partye ingetel) getref het.
    resultaat = lu.ontleed_pdf(MEERBLADSY_FIXTURE_PAD, "LIM354")

    # 23 partye op die eerste geknipte bladsy + "YOUNG PEOPLES PARTY" op die tweede.
    assert len(resultaat.party_rye) == 24
    party_name = [r["party_naam"] for r in resultaat.party_rye]
    assert "AFRICAN NATIONAL CONGRESS" in party_name
    assert "YOUNG PEOPLES PARTY" in party_name  # bewys die tweede bladsy is ingesluit

    anc = next(r for r in resultaat.party_rye if r["party_naam"] == "AFRICAN NATIONAL CONGRESS")
    assert anc["setels_wyk"] == 37
    assert anc["setels_pv"] == 19
    assert anc["setels_totaal"] == 56

    assert resultaat.raadsgrootte == 90
    assert sum(r["setels_totaal"] for r in resultaat.party_rye) == 90
