"""Netwerktoetse vir `koppel_nuus` (plaaslike nuus → wyke) teen die gepubliseerde data.

Soos test_soek_rpc.py: die logika is SQL, so dit word teen die werklike databasis getoets en
oorgeslaan as die Verkiesing-omgewing ontbreek. `koppel_nuus` skryf niks nie.
"""

from __future__ import annotations

import pytest

from lib import omgewing, supabase

try:
    omgewing.lees()
    OMGEWING_FOUT: str | None = None
except omgewing.OmgewingFout as fout:  # pragma: no cover - omgewing-afhanklik
    OMGEWING_FOUT = str(fout)

pytestmark = pytest.mark.skipif(OMGEWING_FOUT is not None, reason=f"geen Verkiesing-omgewing nie: {OMGEWING_FOUT}")


def koppel(teks: str, munis: list[str]) -> list[dict]:
    return supabase.rpc("koppel_nuus", {"teks": teks, "munis": munis}) or []


def test_voorstad_met_min_wyke_is_wykvlak():
    rye = koppel("Work starts on Pretoria North stormwater system repair project", ["TSH"])
    assert rye and all(r["vlak"] == "wyk" and r["plek"] == "Pretoria North" for r in rye)
    assert 1 <= len(rye) <= 3


def test_langste_naam_wen_bo_die_stad():
    rye = koppel("Man found stabbed to death in Pretoria West street", ["TSH"])
    assert rye and not any(r["vlak"] == "munisipaliteit" for r in rye)


def test_munisipaliteit_self_genoem():
    rye = koppel("Treasury signs another loan to fix City of Joburg and others", ["EKU"])
    assert rye == [{"muni_kode": "JHB", "wyk_id": None, "plek": "Joburg", "vlak": "munisipaliteit"}]


def test_dorp_met_baie_wyke_is_dorpvlak():
    rye = koppel("St Ursula's learners in Krugersdorp support SANParks K9 unit", ["GT481"])
    assert len(rye) > 3 and {r["vlak"] for r in rye} == {"dorp"}


def test_vanne_gewone_woorde_en_buiteland_koppel_nie():
    assert koppel("Solly Mkhize says Rugby fans in Washington found no memory", ["KZN245", "CPT", "NC451", "KZN292"]) == []


def test_onbevestigde_munisipaliteit_word_verwerp():
    # Pretoria North exists only in TSH; an outlet from Cape Town that does not name Tshwane
    # does not get to place it.
    assert koppel("Work starts on Pretoria North stormwater system repair project", ["CPT"]) == []


def test_teks_wat_die_munisipaliteit_noem_bevestig_die_plek():
    rye = koppel("Tshwane: work starts on Pretoria North stormwater repairs", ["CPT"])
    assert any(r["vlak"] == "wyk" and r["muni_kode"] == "TSH" for r in rye)
