import re
import time
from collections import Counter
from pathlib import Path

import pytest

import kandidate_ontleder as ko

BRON_PAD = Path(__file__).parent.parent / "bron" / "kandidate-2021-WC.pdf"

pytestmark_fixture = pytest.mark.skipif(
    not BRON_PAD.exists(), reason=f"bronlêer nie gevind nie: {BRON_PAD}"
)

# Presiese tellings vir die 2021 WC-kandidaatlys-vastrigger — self bereken tydens
# ontdekking (geen amptelike IEC-2021-totale is gepubliseer nie; sien task-7-report.md
# §Ontdekking). Die getalle is deterministies solank die vastrigger-lêer nie verander nie.
VERWAGTE_TOTAAL = 12434
VERWAGTE_WYK = 7916
VERWAGTE_PV_PLAASLIK = 3970
VERWAGTE_PV_DISTRIK = 548
VERWAGTE_ONAFHANKLIK = 86

DIGIT_LOOP_PATROON = re.compile(r"\d{6,}")


# --- eenheidstoetse: kop-herkenning (geen PDF nodig nie) -----------------------------


def test_kry_kolom_indekse_presiese_koptekste():
    kop = ["Municipality", "Party", "Ward \\ List Order", "IDNumber", "Fullname", "Surname"]
    indekse = ko.kry_kolom_indekse(kop)
    assert indekse == {"muni": 0, "party": 1, "wyklys": 2, "id": 3, "volle_naam": 4, "van": 5}


def test_kry_kolom_indekse_verdraagsaam_vir_variante():
    # Moontlike 2026-variante: ander spasiëring/hoofletters, "Ward/List" i.p.v. "Ward \ List
    # Order", "Full Name" met spasie.
    kop = ["  municipality ", "PARTY", "Ward/List", "ID Number", "Full Name", "SURNAME"]
    indekse = ko.kry_kolom_indekse(kop)
    assert indekse == {"muni": 0, "party": 1, "wyklys": 2, "id": 3, "volle_naam": 4, "van": 5}


def test_kry_kolom_indekse_nie_kop_ry_gee_none():
    # 'n Gewone data-ry moet nie per ongeluk as kop-ry herken word nie.
    data_ry = ["CPT - City of Cape Town", "ABANTU BATHO CONGRESS", "1", "######****08*", "VUYANI", "MGWALI"]
    assert ko.kry_kolom_indekse(data_ry) is None


def test_kry_kolom_indekse_ontbrekende_kolom_gooi_fout():
    kop = ["Municipality", "Party", "Ward \\ List Order", "IDNumber", "Fullname"]  # geen Surname
    with pytest.raises(ko.KandidaatOntledingFout) as fout:
        ko.kry_kolom_indekse(kop)
    assert "van" in str(fout.value)


def test_is_leeg_of_titel_ry():
    assert ko.is_leeg_of_titel_ry(["Updated LGE2021 Candidate Lists - 8 Oct 2021", None, None, None, None, None])
    assert not ko.is_leeg_of_titel_ry(
        ["CPT - City of Cape Town", "ABANTU BATHO CONGRESS", "1", "######****08*", "VUYANI", "MGWALI"]
    )


# --- eenheidstoetse: munisipaliteit-ontleding -----------------------------------------


def test_ontleed_muni_met_kode():
    assert ko.ontleed_muni("CPT - City of Cape Town") == ("City of Cape Town", "CPT")
    assert ko.ontleed_muni("DC1 - West Coast") == ("West Coast", "DC1")


def test_ontleed_muni_sonder_kode():
    assert ko.ontleed_muni("Onbekende Munisipaliteit") == ("Onbekende Munisipaliteit", None)


def test_is_distrik():
    assert ko.is_distrik("DC1 - West Coast") is True
    assert ko.is_distrik("Some District Municipality") is True
    assert ko.is_distrik("CPT - City of Cape Town") is False
    assert ko.is_distrik("WC011 - Matzikama") is False


# --- eenheidstoetse: een ry bou (dié waar die ID-kolom se posisionele weglating getoets word) ---


_KOLOM_INDEKSE = {"muni": 0, "party": 1, "wyklys": 2, "id": 3, "volle_naam": 4, "van": 5}


def test_bou_kandidaat_wyk_ry():
    ry = ["CPT - City of Cape Town", "ABANTU BATHO CONGRESS", "12345678", "8001015009087", "VUYANI PUNCTUAL", "MGWALI"]
    k = ko.bou_kandidaat(ry, _KOLOM_INDEKSE, bladsy_nr=1, ry_nr=1, bron_lêer="toets.pdf")
    assert k.stembrief == "wyk"
    assert k.wyk_id == "12345678"
    assert k.lys_posisie is None
    assert k.muni_naam == "City of Cape Town"
    assert k.muni_kode == "CPT"
    assert k.onafhanklik is False
    assert k.volle_naam == "VUYANI PUNCTUAL"
    assert k.van == "MGWALI"


def test_bou_kandidaat_pv_plaaslik_ry():
    ry = ["CPT - City of Cape Town", "SOME PARTY", "7", "8001015009087", "A B", "C"]
    k = ko.bou_kandidaat(ry, _KOLOM_INDEKSE, bladsy_nr=1, ry_nr=2, bron_lêer="toets.pdf")
    assert k.stembrief == "pv_plaaslik"
    assert k.lys_posisie == 7
    assert k.wyk_id is None


def test_bou_kandidaat_pv_distrik_ry():
    ry = ["DC1 - West Coast", "SOME PARTY", "3", "8001015009087", "A B", "C"]
    k = ko.bou_kandidaat(ry, _KOLOM_INDEKSE, bladsy_nr=1, ry_nr=3, bron_lêer="toets.pdf")
    assert k.stembrief == "pv_distrik"
    assert k.lys_posisie == 3


def test_bou_kandidaat_onafhanklik_slegs_op_wyk():
    ry = ["CPT - City of Cape Town", "INDEPENDENT", "87654321", "8001015009087", "A B", "C"]
    k = ko.bou_kandidaat(ry, _KOLOM_INDEKSE, bladsy_nr=1, ry_nr=4, bron_lêer="toets.pdf")
    assert k.onafhanklik is True
    assert k.stembrief == "wyk"


def test_bou_kandidaat_onbekende_wyklys_waarde_gooi_fout():
    ry = ["CPT - City of Cape Town", "SOME PARTY", "N/A", "8001015009087", "A B", "C"]
    with pytest.raises(ko.KandidaatOntledingFout):
        ko.bou_kandidaat(ry, _KOLOM_INDEKSE, bladsy_nr=1, ry_nr=5, bron_lêer="toets.pdf")


def test_bou_kandidaat_id_kolom_word_nooit_in_die_objek_nie():
    """PERSONAL DATA RULE: die gemaskeerde ID-nommer word posisioneel oorgeslaan — dit
    mag nooit in enige Kandidaat-veld verskyn nie, ongeag wat in die ID-kolom staan."""
    id_waarde = "9203145678123"  # sintetiese "volledige" ID-agtige string, ter toetsing
    ry = ["CPT - City of Cape Town", "SOME PARTY", "1", id_waarde, "A B", "C"]
    k = ko.bou_kandidaat(ry, _KOLOM_INDEKSE, bladsy_nr=1, ry_nr=6, bron_lêer="toets.pdf")
    for veld_waarde in vars(k).values():
        assert id_waarde not in str(veld_waarde)


def test_kandidaat_het_geen_id_veld_nie():
    veldname = set(ko.Kandidaat.__dataclass_fields__.keys())
    assert "id" not in veldname
    assert "id_nommer" not in veldname
    assert "idnommer" not in veldname


def test_bron_ry_kode():
    assert ko.bron_ry_kode(1, 1) == 101
    assert ko.bron_ry_kode(249, 50) == 24950


# --- vastrigger-toetse: die werklike 2021 WC-PDF (oorgeslaan as die lêer nie daar is nie) ---


@pytest.fixture(scope="module")
def wc_kandidate():
    if not BRON_PAD.exists():
        pytest.skip(f"bronlêer nie gevind nie: {BRON_PAD}")
    return list(ko.ontleed(BRON_PAD))


def test_ontleed_wc_totaal_rye_positief(wc_kandidate):
    assert len(wc_kandidate) > 0


def test_ontleed_wc_presiese_totale(wc_kandidate):
    assert len(wc_kandidate) == VERWAGTE_TOTAAL
    tellings = Counter(k.stembrief for k in wc_kandidate)
    assert tellings["wyk"] == VERWAGTE_WYK
    assert tellings["pv_plaaslik"] == VERWAGTE_PV_PLAASLIK
    assert tellings["pv_distrik"] == VERWAGTE_PV_DISTRIK
    onafhanklikes = [k for k in wc_kandidate if k.onafhanklik]
    assert len(onafhanklikes) == VERWAGTE_ONAFHANKLIK


def test_ontleed_wc_wyk_xor_lys_posisie(wc_kandidate):
    for k in wc_kandidate:
        het_wyk = k.wyk_id is not None
        het_lys = k.lys_posisie is not None
        assert het_wyk != het_lys, k


def test_ontleed_wc_onafhanklik_slegs_op_wyk(wc_kandidate):
    for k in wc_kandidate:
        if k.onafhanklik:
            assert k.stembrief == "wyk", k


def test_ontleed_wc_geen_id_lek_nie(wc_kandidate):
    """Verpligte skans (PERSONAL DATA RULE): geen syfer-string van >=6 syfers mag in enige
    veld voorkom nie, behalwe wyk_id self (wat altyd presies 8 syfers is)."""
    for k in wc_kandidate:
        for veldnaam, veldwaarde in vars(k).items():
            if veldnaam == "wyk_id":
                continue
            treffers = DIGIT_LOOP_PATROON.findall(str(veldwaarde) if veldwaarde is not None else "")
            assert treffers == [], (veldnaam, veldwaarde, k)


def test_ontleed_wc_wyk_id_formaat(wc_kandidate):
    patroon = re.compile(r"^\d{8}$")
    for k in wc_kandidate:
        if k.wyk_id is not None:
            assert patroon.match(k.wyk_id), k.wyk_id


def test_ontleed_wc_bron_lêer_en_bron_ry(wc_kandidate):
    for k in wc_kandidate[:20]:
        assert k.bron_lêer == "kandidate-2021-WC.pdf"
        assert isinstance(k.bron_ry, int)
        assert k.bron_ry > 0


def test_ontleed_wc_timing_word_aangeteken(wc_kandidate):
    # Self nie 'n toets van 'n spesifieke drempel nie — bloot bevestig dat ontleding van
    # die volle 249-bladsy-vastrigger binne 'n redelike tyd klaarmaak.
    begin = time.monotonic()
    _ = list(ko.ontleed(BRON_PAD))
    duur = time.monotonic() - begin
    assert duur < 120


def test_formateer_verslag_teks_bevat_tellings(wc_kandidate):
    teks = ko.formateer_verslag_teks(wc_kandidate, ontleedtyd=1.23)
    assert f"Totaal: {VERWAGTE_TOTAAL}" in teks
    assert f"wyk: {VERWAGTE_WYK}" in teks
    assert f"pv_plaaslik: {VERWAGTE_PV_PLAASLIK}" in teks
    assert f"pv_distrik: {VERWAGTE_PV_DISTRIK}" in teks
    assert "City of Cape Town" in teks
    # Geen naam mag in die tellings-teks verskyn nie (net munisipaliteite/stembriewe).
    for k in wc_kandidate[:5]:
        assert k.volle_naam not in teks


def test_hoof_cli_skryf_verslag(tmp_path):
    if not BRON_PAD.exists():
        pytest.skip(f"bronlêer nie gevind nie: {BRON_PAD}")
    verslag_pad = tmp_path / "toets-verslag.md"
    kode = ko.hoof([str(BRON_PAD), "--verslag", str(verslag_pad)])
    assert kode == 0
    assert verslag_pad.exists()
    inhoud = verslag_pad.read_text()
    assert f"Totaal: {VERWAGTE_TOTAAL}" in inhoud
    assert "## Steekproef" in inhoud
    # Geen ID-agtige lang syfer-string in die hele verslag nie (behalwe 8-syfer wyk_id's,
    # wat hulself nie ID-nommers is nie).
    for reël in inhoud.splitlines():
        for treffer in DIGIT_LOOP_PATROON.findall(reël):
            assert len(treffer) == 8, reël
