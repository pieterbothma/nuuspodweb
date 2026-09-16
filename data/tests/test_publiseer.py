"""Tests for publiseer.py's pure (network-free) helpers, plus the herlaai POST and one
chunk-publish loop driven through httpx.MockTransport — nothing here touches the network
or reads a real .env file.

The real publish run against `verkiesing-2026` is recorded in task-2-report.md.
"""

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import publiseer  # noqa: E402
from lib import omgewing  # noqa: E402


# --- stukkies ---------------------------------------------------------------------


def test_stukkies_dek_elke_ry():
    assert list(publiseer.stukkies(4485, 2000)) == [(1, 2000), (2001, 4000), (4001, 4485)]


def test_stukkies_presies_een_stuk_as_dit_pas():
    assert list(publiseer.stukkies(2000, 2000)) == [(1, 2000)]


def test_stukkies_van_nul_rye_is_leeg():
    assert list(publiseer.stukkies(0, 2000)) == []


def test_stukkies_weier_n_nie_positiewe_grootte():
    with pytest.raises(publiseer.PubliseerFout):
        list(publiseer.stukkies(10, 0))


# --- kontroleer_datastelle --------------------------------------------------------


def test_datastel_moet_op_die_witlys_wees():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.kontroleer_datastelle(["wyke", "geheime_tabel"])


def test_kontroleer_datastelle_orden_volgens_publiseer_orde():
    gevra = ["stembrief_volgorde", "wyke", "munisipaliteite", "kandidate", "partye"]
    assert publiseer.kontroleer_datastelle(gevra) == [
        "munisipaliteite",
        "wyke",
        "partye",
        "kandidate",
        "stembrief_volgorde",
    ]


def test_kontroleer_datastelle_weier_n_leë_lys():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.kontroleer_datastelle([])


def test_kontroleer_datastelle_weier_duplikate():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.kontroleer_datastelle(["wyke", "wyke"])


def test_witlys_is_presies_die_sql_funksie_se_lys():
    # Same 11 names, same order, as the hard-coded array in publiseer_leeg /
    # publiseer_tabel / publiseer_afrond (migration 20260916062706 and its fix rounds).
    assert publiseer.PUBLISEERBAAR == (
        "munisipaliteite",
        "wyke",
        "stemstasies",
        "plekke",
        "plek_wyke",
        "plek_aliasse",
        "raad_uitslae_2021",
        "raad_grootte_2021",
        "partye",
        "kandidate",
        "stembrief_volgorde",
    )


# --- tags ------------------------------------------------------------------------


def test_tags_vir_datastelle():
    assert publiseer.tags_vir(["wyke", "stemstasies"]) == ["wyke"]
    assert publiseer.tags_vir(["kandidate", "partye"]) == ["kandidate"]


def test_tags_vir_albei_tags_in_n_vaste_orde():
    assert publiseer.tags_vir(["kandidate", "wyke"]) == ["wyke", "kandidate"]


def test_elke_publiseerbare_datastel_het_n_tag():
    for datastel in publiseer.PUBLISEERBAAR:
        assert publiseer.tags_vir([datastel]), datastel


# --- leeg-orde (omgekeerde afhanklikheidsorde) ------------------------------------


def test_leeg_orde_is_die_omgekeerde_van_die_vul_orde():
    datastelle = ["munisipaliteite", "wyke", "plek_wyke", "plekke"]
    assert publiseer.leeg_orde(datastelle) == [
        "plek_wyke",
        "plekke",
        "wyke",
        "munisipaliteite",
    ]


# --- FK-afhanklikheidshek ---------------------------------------------------------


def test_afhanklikheidshek_blokkeer_n_ouer_sonder_sy_gevulde_kind():
    # Emptying public.wyke while public.stemstasies still holds rows violates the FK.
    blokkeerders = publiseer.kontroleer_afhanklikhede(["wyke"], {"stemstasies": 23696})
    assert len(blokkeerders) == 1
    assert "stemstasies" in blokkeerders[0]


def test_afhanklikheidshek_laat_n_leë_kind_deur():
    assert publiseer.kontroleer_afhanklikhede(["wyke"], {"stemstasies": 0}) == []


def test_afhanklikheidshek_laat_die_kind_deur_as_dit_ook_gevra_is():
    assert (
        publiseer.kontroleer_afhanklikhede(
            ["wyke", "stemstasies"], {"stemstasies": 23696}
        )
        == []
    )


def test_afhanklikheidshek_laat_die_volle_basisdata_deur():
    basis = [
        "munisipaliteite",
        "wyke",
        "stemstasies",
        "plekke",
        "plek_wyke",
        "plek_aliasse",
        "raad_uitslae_2021",
        "raad_grootte_2021",
    ]
    tellings = {"kandidate": 0, "stembrief_volgorde": 0, "partye": 0}
    assert publiseer.kontroleer_afhanklikhede(basis, tellings) == []


# --- Content-Range ---------------------------------------------------------------


def test_ontleed_inhoud_reeks():
    assert publiseer.ontleed_inhoud_reeks("0-0/4485") == 4485
    assert publiseer.ontleed_inhoud_reeks("*/0") == 0


# --- omgewing.lees_herlaai -------------------------------------------------------


def test_lees_herlaai_geheim(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text('HERLAAI_SECRET="hs_geheim"\nANDER=iets\n')
    assert omgewing.lees_herlaai(pad) == "hs_geheim"


def test_lees_herlaai_geheim_ontbreek(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text("ANDER=iets\n")
    with pytest.raises(omgewing.OmgewingFout) as fout:
        omgewing.lees_herlaai(pad)
    boodskap = str(fout.value)
    assert "HERLAAI_SECRET" in boodskap
    assert "iets" not in boodskap


def test_lees_herlaai_lêer_ontbreek(tmp_path):
    with pytest.raises(omgewing.OmgewingFout):
        omgewing.lees_herlaai(tmp_path / "geen-so-lêer.env")


def test_lees_werf_gee_elke_gevraagde_sleutel(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text(
        'SUPABASE_URL="https://voorbeeld.supabase.co"\n'
        "SUPABASE_PUBLISHABLE_KEY=sb_publishable_xyz\n"
        "HERLAAI_SECRET=hs_geheim\n"
    )
    assert omgewing.lees_werf("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", pad=pad) == {
        "SUPABASE_URL": "https://voorbeeld.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_xyz",
    }


def test_lees_werf_noem_net_die_ontbrekende_sleutel(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text('SUPABASE_URL="https://voorbeeld.supabase.co"\n')
    with pytest.raises(omgewing.OmgewingFout) as fout:
        omgewing.lees_werf("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", pad=pad)
    boodskap = str(fout.value)
    assert "SUPABASE_PUBLISHABLE_KEY" in boodskap
    assert "voorbeeld.supabase.co" not in boodskap


# --- publiseer_stuk: herhaling en halvering --------------------------------------


def _klient(handler):
    return httpx.Client(
        base_url="https://voorbeeld.supabase.co/rest/v1/",
        headers={"apikey": "toets", "Authorization": "Bearer toets"},
        transport=httpx.MockTransport(handler),
    )


def test_publiseer_stuk_halveer_op_n_timeout(monkeypatch):
    monkeypatch.setattr(publiseer.time, "sleep", lambda *_: None)
    monkeypatch.setattr(publiseer.supabase.time, "sleep", lambda *_: None)
    reekse = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        args = json.loads(request.content)
        reekse.append((args["van"], args["tot"]))
        if args["tot"] - args["van"] + 1 > 2:
            return httpx.Response(500, json={"code": "57014", "message": "statement timeout"})
        return httpx.Response(200, json=args["tot"] - args["van"] + 1)

    klient = _klient(handler)
    tydsberekenings: list[dict] = []

    ingevoeg = publiseer.publiseer_stuk("wyke", 1, 4, tydsberekenings, klient=klient)

    assert ingevoeg == 4
    # The 4-row range fails (with lib.supabase's own 5xx retries), then each half of 2
    # succeeds.
    assert (1, 4) in reekse
    assert (1, 2) in reekse and (3, 4) in reekse
    assert [t["van"] for t in tydsberekenings] == [1, 3]


def test_publiseer_stuk_gee_op_na_die_maksimum_halverings(monkeypatch):
    monkeypatch.setattr(publiseer.time, "sleep", lambda *_: None)
    monkeypatch.setattr(publiseer.supabase.time, "sleep", lambda *_: None)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"code": "57014", "message": "statement timeout"})

    klient = _klient(handler)
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.publiseer_stuk("wyke", 1, 2, [], klient=klient)


# --- herlaai ---------------------------------------------------------------------


def test_herlaai_stuur_een_pos_per_tag_en_gee_die_uitslae():
    gestuur = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        gestuur.append((str(request.url), json.loads(request.content)))
        assert request.headers["authorization"] == "Bearer hs_geheim"
        return httpx.Response(200, json={"ok": True, "tag": json.loads(request.content)["tag"]})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    uitslae = publiseer.herlaai(["wyke", "kandidate"], "hs_geheim", klient=klient)

    assert [u["tag"] for u in uitslae] == ["wyke", "kandidate"]
    assert all(u["ok"] for u in uitslae)
    assert [url for url, _ in gestuur] == [publiseer.HERLAAI_URL, publiseer.HERLAAI_URL]
    assert [liggaam["tag"] for _, liggaam in gestuur] == ["wyke", "kandidate"]


def test_herlaai_n_mislukte_tag_is_n_waarskuwing_nie_n_uitsondering():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"fout": "Onbekende tag"})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    uitslae = publiseer.herlaai(["wyke"], "hs_geheim", klient=klient)

    assert uitslae[0]["ok"] is False
    assert uitslae[0]["status"] == 400


def test_herlaai_dra_nooit_die_geheim_in_sy_uitslag():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"fout": "Nie gemagtig nie"})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    uitslae = publiseer.herlaai(["wyke"], "hs_uiters_geheim", klient=klient)

    assert "hs_uiters_geheim" not in repr(uitslae)


def test_herlaai_volg_nie_n_herleiding_nie():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(308, headers={"location": "https://nuuspod.co.za/api/herlaai"})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    uitslae = publiseer.herlaai(["wyke"], "hs_geheim", klient=klient)

    assert uitslae[0]["ok"] is False
    assert uitslae[0]["status"] == 308


# --- CLI-argumente ---------------------------------------------------------------


def test_ontleed_argumente_verstek():
    argumente = publiseer.ontleed_argumente(["--datastelle", "wyke,stemstasies"])
    assert argumente["datastelle"] == ["wyke", "stemstasies"]
    assert argumente["stukgrootte"] == publiseer.STANDAARD_STUKGROOTTE
    assert argumente["droogloop"] is False
    assert argumente["aanvaar_verskil"] is None


def test_ontleed_argumente_volledig():
    argumente = publiseer.ontleed_argumente(
        [
            "--datastelle",
            "wyke",
            "--stukgrootte",
            "500",
            "--bron-datum",
            "2026-09-16",
            "--droogloop",
            "--aanvaar-verskil",
            "hawe-snippers",
        ]
    )
    assert argumente["stukgrootte"] == 500
    assert argumente["bron_datum"] == "2026-09-16"
    assert argumente["droogloop"] is True
    assert argumente["aanvaar_verskil"] == "hawe-snippers"


def test_ontleed_argumente_vereis_datastelle():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.ontleed_argumente([])


def test_ontleed_argumente_weier_n_onbekende_vlag():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.ontleed_argumente(["--datastelle", "wyke", "--vinnig"])


def test_ontleed_argumente_weier_n_slegte_bron_datum():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.ontleed_argumente(["--datastelle", "wyke", "--bron-datum", "16/09/2026"])


# --- verslag ---------------------------------------------------------------------


def test_bou_verslag_wys_elke_datastel_se_tellings_en_die_herlaai():
    teks = publiseer.bou_verslag(
        tydstempel="2026-09-16 10:00:00 SAST",
        bron_datum="2026-09-16",
        stukgrootte=2000,
        droogloop=False,
        aanvaar_verskil=None,
        gevra=["wyke"],
        uitslae=[
            {
                "datastel": "wyke",
                "stg": 4485,
                "verwyder": 4485,
                "gepubliseer": 4485,
                "publiek_na": 4485,
                "stukke": 3,
                "langste_stuk_s": 1.2,
                "tyd_s": 3.4,
                "oorgeslaan": False,
                "verskil": None,
            }
        ],
        herlaai_uitslae=[{"tag": "wyke", "ok": True, "status": 200, "liggaam": '{"ok":true}'}],
        foute=[],
        afrond_ok=True,
    )
    assert "wyke" in teks
    assert "4485" in teks
    assert "herlaai" in teks.lower()
    assert "**Geslaag**" in teks or "geslaag" in teks.lower()


def test_bou_verslag_wys_n_mislukking_en_bly_skryfbaar():
    teks = publiseer.bou_verslag(
        tydstempel="2026-09-16 10:00:00 SAST",
        bron_datum="2026-09-16",
        stukgrootte=2000,
        droogloop=False,
        aanvaar_verskil=None,
        gevra=["wyke"],
        uitslae=[],
        herlaai_uitslae=[],
        foute=["wyke: telling klop nie (stg 4485, publiek 4484)"],
        afrond_ok=False,
    )
    assert "klop nie" in teks
    assert "GEFAAL" in teks
