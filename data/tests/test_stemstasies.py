import re
from collections import Counter
from pathlib import Path

import pytest

import laai_stemstasies as ls

BRON_PAD = Path(__file__).parent.parent / "bron" / "stemstasies-2026-WC.pdf"

# All WC muni_kode wyk_id prefixes (first 5 digits), derived once from stg_wyke via
# read-only SQL during discovery (Task 4) — see task-4-report.md §Ontdekking. Used only
# to sanity-check that WC ward ids share the expected numeric namespace; the loader
# itself never hardcodes this (it fetches the real prefix map from stg_wyke via REST).
WC_WYK_VOORVOEGSELS = {
    "19100",  # CPT
    "10101", "10102", "10103", "10104", "10105",  # WC011-WC015
    "10202", "10203", "10204", "10205", "10206",  # WC022-WC026
    "10301", "10302", "10303", "10304",  # WC031-WC034
    "10401", "10402", "10403", "10404", "10405", "10407", "10408",  # WC041-WC048
    "10501", "10502", "10503",  # WC051-WC053
}

pytestmark = pytest.mark.skipif(not BRON_PAD.exists(), reason=f"bronlêer nie gevind nie: {BRON_PAD}")


@pytest.fixture(scope="module")
def wc_rye() -> list[dict]:
    return ls.ontleed(BRON_PAD)


def test_ontleed_wc_row_count_at_least_1600(wc_rye):
    assert len(wc_rye) >= 1600


def test_ontleed_wc_wyk_id_format_and_prefix(wc_rye):
    patroon = re.compile(r"^\d{8}$")
    for ry in wc_rye:
        assert patroon.match(ry["wyk_id"]), ry["wyk_id"]
        assert ry["wyk_id"][:5] in WC_WYK_VOORVOEGSELS, ry


def test_ontleed_wc_no_duplicate_vd(wc_rye):
    tellings = Counter(ry["vd_nommer"] for ry in wc_rye)
    duplikate = [vd for vd, n in tellings.items() if n > 1]
    assert duplikate == []


def test_ontleed_wc_rows_have_all_keys(wc_rye):
    verwagte_sleutels = {"vd_nommer", "naam", "adres", "wyk_id", "muni_kode", "bron_lêer", "bron_ry"}
    for ry in wc_rye[:20]:
        assert set(ry.keys()) == verwagte_sleutels


def test_ontleed_wc_explicit_muni_kode_used(wc_rye):
    # Every WC station row prints an explicit "KODE - Naam" municipality — no fallback needed.
    kodes = {ry["muni_kode"] for ry in wc_rye}
    assert "CPT" in kodes
    assert all(re.match(r"^(CPT|WC\d{3})$", k) for k in kodes)


def test_ontleed_wc_bron_lêer_and_bron_ry(wc_rye):
    for ry in wc_rye[:5]:
        assert ry["bron_lêer"] == "stemstasies-2026-WC.pdf"
        assert isinstance(ry["bron_ry"], int)
        assert ry["bron_ry"] > 0


# --- bou_stasie_ry: pure row-building + municipality-resolution tiers ---------------


def _rou_ry(muni="CPT - City of Cape Town", wyk_id="19100001", vd="97140078", naam="X SKOOL", adres="X STRAAT"):
    return ["Western Cape", muni, wyk_id, vd, naam, adres]


def test_bou_stasie_ry_uses_explicit_muni_kode():
    ry, metode, probleem = ls.bou_stasie_ry(_rou_ry(), 1, 1, "stemstasies-2026-WC.pdf", {}, {})
    assert probleem is None
    assert metode == "eksplisiet"
    assert ry == {
        "vd_nommer": "97140078",
        "naam": "X SKOOL",
        "adres": "X STRAAT",
        "wyk_id": "19100001",
        "muni_kode": "CPT",
        "bron_lêer": "stemstasies-2026-WC.pdf",
        "bron_ry": 1001,
    }


def test_bou_stasie_ry_falls_back_to_wyk_voorvoegsel():
    rou = _rou_ry(muni="Onbekende Munisipaliteit")  # no " - " separator
    ry, metode, probleem = ls.bou_stasie_ry(
        rou, 2, 3, "x.pdf", {"19100": "CPT"}, {}
    )
    assert probleem is None
    assert metode == "wyk_voorvoegsel"
    assert ry["muni_kode"] == "CPT"
    assert ry["bron_ry"] == 2003


def test_bou_stasie_ry_falls_back_to_munisipaliteit_naam():
    rou = _rou_ry(muni="Stad Kaapstad")  # no " - " separator, no wyk prefix match
    ry, metode, probleem = ls.bou_stasie_ry(
        rou, 1, 1, "x.pdf", {}, {"stad kaapstad": "CPT"}
    )
    assert probleem is None
    assert metode == "naam"
    assert ry["muni_kode"] == "CPT"


def test_bou_stasie_ry_unresolved_muni_reports_probleem_and_no_row():
    rou = _rou_ry(muni="Heeltemal Onbekend")
    ry, metode, probleem = ls.bou_stasie_ry(rou, 1, 1, "x.pdf", {}, {})
    assert ry is not None  # row is still built...
    assert ry["muni_kode"] is None
    assert metode is None
    assert probleem is not None


def test_bou_stasie_ry_rejects_bad_wyk_id():
    rou = _rou_ry(wyk_id="1234")
    ry, metode, probleem = ls.bou_stasie_ry(rou, 1, 1, "x.pdf", {}, {})
    assert ry is None
    assert "wyk_id" in probleem


def test_bou_stasie_ry_rejects_incomplete_row():
    rou = _rou_ry(wyk_id="", vd="")
    ry, metode, probleem = ls.bou_stasie_ry(rou, 1, 1, "x.pdf", {}, {})
    assert ry is None
    assert probleem is not None


def test_bron_ry_kode_encodes_page_and_row():
    assert ls.bron_ry_kode(1, 1) == 1001
    assert ls.bron_ry_kode(27, 15) == 27015


# --- ontleed_met_diagnostiek: aggregation over bou_stasie_ry -------------------------


def test_ontleed_met_diagnostiek_reports_unresolved_muni(monkeypatch):
    rou_rye = [
        (1, 1, _rou_ry()),
        (1, 2, _rou_ry(muni="Onbekend", wyk_id="19100002", vd="97140079")),
    ]
    monkeypatch.setattr(ls, "lees_rye_uit_pdf", lambda pad: rou_rye)

    rye, diagnostiek = ls.ontleed_met_diagnostiek("nepad.pdf")

    assert len(rye) == 1
    assert diagnostiek["rou_rytal"] == 2
    assert diagnostiek["gelaaide_rytal"] == 1
    assert diagnostiek["onopgeloste_munisipaliteite"] == ["Onbekend"]
    assert diagnostiek["metode_tellings"] == {"eksplisiet": 1}
