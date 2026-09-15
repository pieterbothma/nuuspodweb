import json

import httpx
import pytest

from lib import supabase


def _klient(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(
        base_url="https://voorbeeld.supabase.co/rest/v1/",
        headers={"apikey": "toets-sleutel", "Authorization": "Bearer toets-sleutel"},
        transport=transport,
    )


def test_plaas_bondels_halves_batch_on_413(monkeypatch):
    monkeypatch.setattr(supabase.time, "sleep", lambda *_: None)
    oproepe = []

    def handler(request: httpx.Request) -> httpx.Response:
        liggaam = json.loads(request.content)
        oproepe.append(len(liggaam))
        if len(liggaam) > 2:
            return httpx.Response(413, text="Payload Too Large")
        assert request.headers["prefer"] == "return=minimal"
        return httpx.Response(200, json=[])

    klient = _klient(handler)
    rye = [{"id": i} for i in range(4)]

    gestuur = supabase.plaas_bondels("stg_wyke", rye, grootte=10, klient=klient)

    assert gestuur == rye
    # 1 failed call with all 4, then 2 successful calls with 2 each.
    assert oproepe == [4, 2, 2]


def test_plaas_bondels_retries_on_5xx_then_succeeds(monkeypatch):
    slaap_oproepe = []
    monkeypatch.setattr(supabase.time, "sleep", lambda s: slaap_oproepe.append(s))

    pogings = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        pogings["n"] += 1
        if pogings["n"] < 3:
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, json=[])

    klient = _klient(handler)
    rye = [{"id": 1}]

    gestuur = supabase.plaas_bondels("stg_wyke", rye, klient=klient)

    assert gestuur == rye
    assert pogings["n"] == 3
    assert len(slaap_oproepe) == 2  # backed off twice before the 3rd (successful) try


def test_plaas_bondels_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(supabase.time, "sleep", lambda *_: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="x" * 1000 + " geheime-koptekste-moet-nie-hier-wees")

    klient = _klient(handler)
    rye = [{"id": 1}]

    with pytest.raises(supabase.SupabaseFout) as fout_inligting:
        supabase.plaas_bondels("stg_wyke", rye, klient=klient)

    boodskap = str(fout_inligting.value)
    assert len(boodskap) <= 500
    assert "apikey" not in boodskap
    assert "authorization" not in boodskap.lower()
    assert "toets-sleutel" not in boodskap


def test_plaas_bondels_raises_immediately_on_400_without_retry(monkeypatch):
    monkeypatch.setattr(supabase.time, "sleep", lambda *_: None)
    oproepe = []

    def handler(request: httpx.Request) -> httpx.Response:
        oproepe.append(1)
        return httpx.Response(400, text="bad request: kolom bestaan nie")

    klient = _klient(handler)
    rye = [{"id": 1}]

    with pytest.raises(supabase.SupabaseFout) as fout_inligting:
        supabase.plaas_bondels("stg_wyke", rye, klient=klient)

    assert len(oproepe) == 1
    assert "bad request" in str(fout_inligting.value)


def test_rpc_returns_parsed_json(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/rpc/kontroleer_wyke")
        return httpx.Response(200, json={"wyke_totaal": 4485})

    klient = _klient(handler)
    resultaat = supabase.rpc("kontroleer_wyke", {}, klient=klient)
    assert resultaat == {"wyke_totaal": 4485}


def test_rpc_returns_none_on_204(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    klient = _klient(handler)
    resultaat = supabase.rpc("stg_leeg", {"tabel": "stg_wyke"}, klient=klient)
    assert resultaat is None


def test_rpc_raises_on_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="onbekende stg-tabel: wyke")

    klient = _klient(handler)
    with pytest.raises(supabase.SupabaseFout):
        supabase.rpc("stg_leeg", {"tabel": "wyke"}, klient=klient)


def test_kry_alles_pages_until_short_page(monkeypatch):
    alle_rye = [{"wyk_id": f"{i:08d}"} for i in range(5)]
    oproepe = []

    def handler(request: httpx.Request) -> httpx.Response:
        oproepe.append(request.headers.get("range"))
        rng = request.headers["range"]
        begin_s, _, einde_s = rng.partition("-")
        begin, einde = int(begin_s), int(einde_s)
        return httpx.Response(200, json=alle_rye[begin : einde + 1])

    klient = _klient(handler)
    resultaat = supabase.kry_alles("stg_wyke", orde="wyk_id", klient=klient, bladsy_grootte=2)

    assert resultaat == alle_rye
    assert oproepe == ["0-1", "2-3", "4-5"]


def test_kry_alles_returns_empty_list_for_empty_table(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    klient = _klient(handler)
    resultaat = supabase.kry_alles("stg_stemstasies", orde="vd_nommer", klient=klient)
    assert resultaat == []


def test_kry_alles_passes_query_parameters(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["select"] == "wyk_id,muni_kode"
        assert request.url.params["muni_kode"] == "eq.NC451"
        return httpx.Response(200, json=[{"wyk_id": "34501001", "muni_kode": "NC451"}])

    klient = _klient(handler)
    resultaat = supabase.kry_alles(
        "stg_wyke",
        {"select": "wyk_id,muni_kode", "muni_kode": "eq.NC451"},
        orde="wyk_id",
        klient=klient,
    )
    assert resultaat == [{"wyk_id": "34501001", "muni_kode": "NC451"}]


def test_kry_alles_raises_on_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="interne fout")

    klient = _klient(handler)
    with pytest.raises(supabase.SupabaseFout):
        supabase.kry_alles("stg_wyke", orde="wyk_id", klient=klient)


def test_kry_alles_stuur_orde_as_order_op_elke_bladsy():
    alle_rye = [{"sp_kode": str(i), "wyk_id": "1"} for i in range(3)]
    ordes = []

    def handler(request: httpx.Request) -> httpx.Response:
        ordes.append(request.url.params.get("order"))
        begin_s, _, einde_s = request.headers["range"].partition("-")
        return httpx.Response(200, json=alle_rye[int(begin_s) : int(einde_s) + 1])

    klient = _klient(handler)
    resultaat = supabase.kry_alles(
        "stg_plek_wyke", {"select": "sp_kode,wyk_id"}, orde="sp_kode,wyk_id", klient=klient, bladsy_grootte=2
    )
    assert resultaat == alle_rye
    assert ordes == ["sp_kode,wyk_id", "sp_kode,wyk_id"]


def test_kry_alles_vereis_orde():
    klient = _klient(lambda request: httpx.Response(200, json=[]))
    with pytest.raises(TypeError):
        supabase.kry_alles("stg_wyke", klient=klient)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        supabase.kry_alles("stg_wyke", orde=" ", klient=klient)
    with pytest.raises(ValueError):
        supabase.kry_alles("stg_wyke", {"order": "wyk_id"}, orde="wyk_id", klient=klient)
