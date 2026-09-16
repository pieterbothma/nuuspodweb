"""Netwerktoetse vir die soek-/punt-RPCs (`rpc/soek`, `rpc/vind_wyk`) teen die
gepubliseerde Verkiesing-data.

Anders as die res van `data/tests/` praat hierdie lêer met die werklike databasis:
die RPCs is SQL, so daar is niks om in Python te stub nie. Die toetse slaan met 'n
duidelike boodskap oor as `~/nuuspod/.env.local` (of sy twee Verkiesing-sleutels)
ontbreek. Die sleutel self word nooit gedruk of aangeteken nie — `omgewing.lees()` gee
dit terug en `lib.supabase` sit dit in koptekste; die oorslaan-boodskap noem net die
sleutelname.
"""

from __future__ import annotations

import pytest

from lib import omgewing, supabase

try:
    omgewing.lees()
    OMGEWING_FOUT: str | None = None
except omgewing.OmgewingFout as fout:  # pragma: no cover - omgewing-afhanklik
    OMGEWING_FOUT = str(fout)

pytestmark = pytest.mark.skipif(
    OMGEWING_FOUT is not None,
    reason=(
        "geen Verkiesing-Supabase-omgewing nie, so die RPCs kan nie geroep word nie: "
        f"{OMGEWING_FOUT}"
    ),
)


def roep_soek(q: str) -> list[dict]:
    return supabase.rpc("soek", {"q": q})


def roep_vind_wyk(lat: float, lng: float) -> list[dict]:
    return supabase.rpc("vind_wyk", {"lat": lat, "lng": lng})


def test_soek_gee_niks_vir_een_karakter():
    assert roep_soek("B") == []


def test_brooklyn_gee_meer_as_een_munisipaliteit():
    rye = roep_soek("Brooklyn")
    munis = {r["muni_naam"] for r in rye}
    assert "City of Tshwane" in munis and "City of Cape Town" in munis


def test_kaapstad_alias_gee_stad_kaapstad_gegroepeer():
    """Een ry per (alias, munisipaliteit) — nie 20 los Kaapse sub-pleknaam nie.

    Piet se besluit in die globale beperkings ("search groups places per main place/
    municipality rather than listing sub places") wen oor die taakbrief se etiket-reël.
    """
    rye = roep_soek("Kaapstad")
    kaapstad = [r for r in rye if r["etiket"] == "Kaapstad"]
    assert len(kaapstad) == 1
    ry = kaapstad[0]
    assert ry["soort"] == "plek"
    assert ry["muni_kode"] == "CPT"
    assert ry["muni_naam"] == "City of Cape Town"
    assert ry["rang"] == 1
    # Die 126 sub-plekke onder hoofplek "Cape Town" dek 26 wyke.
    assert len(ry["wyk_ids"]) == 26
    assert len(ry["wyk_nrs"]) == 26
    assert ry["teiken"] is None  # meer as een wyk


def test_mahikeng_alias_gee_een_ry_vir_nw383():
    rye = [
        r for r in roep_soek("Mahikeng")
        if r["etiket"] == "Mahikeng" and r["muni_kode"] == "NW383"
    ]
    assert len(rye) == 1
    assert rye[0]["soort"] == "plek"
    assert rye[0]["muni_naam"] == "Mafikeng"
    assert len(rye[0]["wyk_ids"]) == 12


def test_alias_en_pleknaam_met_dieselfde_etiket_smelt_saam():
    # "Durban" is 'n alias EN 'n sub-pleknaam EN 'n hoofplek — dit moet een ry gee.
    rye = [r for r in roep_soek("Durban") if r["etiket"] == "Durban"]
    assert len(rye) == 1
    assert rye[0]["muni_naam"] == "eThekwini"
    assert len(rye[0]["wyk_ids"]) > 1


def test_geen_plek_etiket_kom_twee_keer_vir_dieselfde_munisipaliteit_voor():
    for navraag in ("Kaapstad", "Durban", "Bloemfontein", "Mahikeng", "Gqeberha", "Brooklyn"):
        sleutels = [
            (r["etiket"], r["muni_kode"]) for r in roep_soek(navraag) if r["soort"] == "plek"
        ]
        assert len(sleutels) == len(set(sleutels)), navraag


def test_soweto_kom_deur_die_hoofplek():
    rye = roep_soek("Soweto")
    assert any(r["muni_naam"] == "City of Johannesburg" for r in rye)


def test_hawe_snippers_kom_nooit_terug_nie():
    assert not [r for r in roep_soek("Habour") if r["soort"] == "plek"]


def test_stemlokaal_gee_een_wyk_en_n_teiken():
    rye = [r for r in roep_soek("Kaya Mandi High") if r["soort"] == "stemlokaal"]
    assert rye and len(rye[0]["wyk_ids"]) == 1 and rye[0]["teiken"].endswith("#stemlokale")


def test_vind_wyk_op_n_punt_binne_stellenbosch():
    ry = roep_vind_wyk(-33.9367, 18.8614)  # Stellenbosch-dorp
    assert ry and ry[0]["muni_kode"] == "WC024"


def test_vind_wyk_buite_die_land_gee_niks():
    assert roep_vind_wyk(51.5, -0.12) == []


# --- eienskappe wat die brief se reëls vir soek() vastrek ---------------------------


def test_plekke_kom_voor_stemlokale_by_dieselfde_treffersklas():
    rye = roep_soek("Brooklyn")
    soorte = [r["soort"] for r in rye]
    # Die vier presiese "Brooklyn"-plekke staan voor enige stemlokaal.
    assert soorte[:4] == ["plek"] * 4
    assert "stemlokaal" in soorte


def test_rang_is_oplopend_en_begin_by_een():
    rye = roep_soek("Stellenbosch")
    assert rye
    assert [r["rang"] for r in rye] == list(range(1, len(rye) + 1))


def test_wyk_nrs_volg_dieselfde_orde_as_wyk_ids():
    # Soweto is 'n hoofplek-treffer met ~47 wyke, so die twee skikkings moet in stap bly.
    rye = [r for r in roep_soek("Soweto") if r["etiket"] == "Soweto"]
    assert rye
    for ry in rye:
        assert len(ry["wyk_ids"]) == len(ry["wyk_nrs"])
        assert ry["wyk_ids"] == sorted(ry["wyk_ids"])
        assert [int(w[-3:]) for w in ry["wyk_ids"]] == ry["wyk_nrs"]


def test_teiken_is_nul_wanneer_daar_meer_as_een_wyk_is():
    rye = roep_soek("Soweto")
    for ry in rye:
        if len(ry["wyk_ids"]) == 1:
            assert ry["teiken"] is not None
        else:
            assert ry["teiken"] is None


def test_soek_hanteer_like_metakarakters_sonder_om_alles_terug_te_gee():
    # % en _ bly ná normalisering in die navraag oor, so hulle moet ontsnap word.
    assert roep_soek("%%") == []
    assert roep_soek("__") == []


def test_publiseer_rpcs_weier_n_onbekende_datastel():
    with pytest.raises(supabase.SupabaseFout) as fout:
        supabase.rpc("publiseer_leeg", {"datastel": "pg_class"})
    assert "onbekende datastel" in str(fout.value)
