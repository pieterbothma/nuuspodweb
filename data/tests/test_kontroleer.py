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


# --- Fix round 1: item 1 (per-sectie faal-veilig) --------------------------------------


def test_formatteer_afdeling_fout_geen_fout_nie():
    assert kontroleer.formatteer_afdeling_fout("wyke", {}) is None


def test_formatteer_afdeling_fout_met_fout():
    sectie_foute = {"wyke": "canceling statement due to statement timeout"}
    assert (
        kontroleer.formatteer_afdeling_fout("wyke", sectie_foute)
        == "kon nie gekontroleer word nie: canceling statement due to statement timeout"
    )


def test_veilig_gee_resultaat_terug_as_dit_slaag():
    hard_gefaal: list[str] = []
    sectie_foute: dict[str, str] = {}
    resultaat = kontroleer.veilig(hard_gefaal, sectie_foute, "wyke", lambda: {"totaal": 4485})
    assert resultaat == {"totaal": 4485}
    assert hard_gefaal == []
    assert sectie_foute == {}


def test_veilig_vang_supabasefout_en_teken_aan_sonder_om_te_gooi():
    hard_gefaal: list[str] = []
    sectie_foute: dict[str, str] = {}

    def faal():
        raise kontroleer.supabase.SupabaseFout("57014 statement timeout")

    resultaat = kontroleer.veilig(hard_gefaal, sectie_foute, "plekke", faal)

    assert resultaat is None
    assert hard_gefaal == ["plekke: 57014 statement timeout"]
    assert sectie_foute == {"plekke": "57014 statement timeout"}


def test_veilig_vang_httpx_fout_en_teken_aan_sonder_om_te_gooi():
    import httpx

    hard_gefaal: list[str] = []
    sectie_foute: dict[str, str] = {}

    def faal():
        raise httpx.ConnectError("connection refused")

    resultaat = kontroleer.veilig(hard_gefaal, sectie_foute, "stemlokale", faal)

    assert resultaat is None
    assert hard_gefaal == ["stemlokale: connection refused"]
    assert sectie_foute == {"stemlokale": "connection refused"}


def test_veilig_boodskap_bevat_nooit_die_woord_apikey_of_bearer_nie():
    # Reguleringstoets: SupabaseFout se boodskap is altyd net die (afgekapte)
    # responsliggaam — nooit koptekste nie — so 'n boodskap wat lyk soos 'n kopteks
    # sou 'n regressie in lib.supabase._kort_boodskap wees, nie hierdie funksie s'n
    # nie. Bevestig net dat veilig() self niks byvoeg wat 'n kopteks sou lyk nie.
    hard_gefaal: list[str] = []
    sectie_foute: dict[str, str] = {}

    def faal():
        raise kontroleer.supabase.SupabaseFout("permission denied for table stg_wyke")

    kontroleer.veilig(hard_gefaal, sectie_foute, "wyke", faal)

    for boodskap in (*hard_gefaal, *sectie_foute.values()):
        assert "apikey" not in boodskap.lower()
        assert "authorization" not in boodskap.lower()
        assert "bearer" not in boodskap.lower()


# --- Fix round 1: item 2 (spec §8 Brooklyn/Waterkloof-verwagting) ----------------------


def test_kontroleer_veelvuldige_munisipaliteite_voldoen():
    assert (
        kontroleer.kontroleer_veelvuldige_munisipaliteite(
            ["City of Cape Town", "City of Tshwane", "Bushbuckridge"],
            ("Tshwane", "Cape Town"),
            min_aantal=2,
        )
        is None
    )


def test_kontroleer_veelvuldige_munisipaliteite_te_min_munisipaliteite():
    fout = kontroleer.kontroleer_veelvuldige_munisipaliteite(
        ["City of Tshwane"], ("Tshwane", "Cape Town"), min_aantal=2
    )
    assert fout is not None
    assert "minder as 2" in fout
    assert "Cape Town" in fout


def test_kontroleer_veelvuldige_munisipaliteite_ontbrekende_stuk():
    fout = kontroleer.kontroleer_veelvuldige_munisipaliteite(
        ["City of Tshwane", "Kopanong", "Rustenburg"], ("Tshwane",), min_aantal=1
    )
    assert fout is None


def test_kontroleer_veelvuldige_munisipaliteite_waterkloof_sonder_tshwane():
    fout = kontroleer.kontroleer_veelvuldige_munisipaliteite(
        ["Kopanong", "Rustenburg"], ("Tshwane",), min_aantal=1
    )
    assert fout == "geen 'Tshwane' nie"


# --- Fix round 1: item 4 (lewendige plattelandse-plek-tellings) -----------------------


def test_formatteer_landelike_plekke():
    per_plek = {
        "271002001": {"sp_kode": "271002001", "naam_in_bron": "Mnquna", "wyktal": 34},
        "290003001": {"sp_kode": "290003001", "naam_in_bron": "Ngquza Hill", "wyktal": 32},
        "292002001": {"sp_kode": "292002001", "naam_in_bron": "Nyandeni", "wyktal": 32},
        "966002001": {"sp_kode": "966002001", "naam_in_bron": "Thulamela", "wyktal": 58},
    }
    assert (
        kontroleer.formatteer_landelike_plekke(per_plek)
        == "Mnquna (34), Ngquza Hill (32), Nyandeni (32), Thulamela (58) = 156 rye"
    )


def test_formatteer_landelike_plekke_met_nul_wyke():
    per_plek = {"271002001": {"sp_kode": "271002001", "naam_in_bron": "Mnquna", "wyktal": 0}}
    assert kontroleer.formatteer_landelike_plekke(per_plek) == "Mnquna (0) = 0 rye"


def test_bou_alias_opsomming_munisipaliteite_en_nul_aliasse():
    csv_aliasse = ["Kaapstad", "Leeg-Alias"]
    alias_rye = [
        {"alias": "Kaapstad", "sp_kode": "1"},
        {"alias": "Kaapstad", "sp_kode": "2"},
        {"alias": "Oud", "sp_kode": "3"},
    ]
    plek_wyke_rye = [
        {"sp_kode": "1", "wyk_id": "19100001"},
        {"sp_kode": "2", "wyk_id": "19100002"},
        {"sp_kode": "2", "wyk_id": "10203001"},
        {"sp_kode": "3", "wyk_id": "79800001"},
    ]
    wyk_muni = {"19100001": "CPT", "19100002": "CPT", "10203001": "WC024", "79800001": "TSH"}
    muni_naam = {"CPT": "City of Cape Town", "TSH": "City of Tshwane"}

    opsomming = kontroleer.bou_alias_opsomming(csv_aliasse, alias_rye, plek_wyke_rye, wyk_muni, muni_naam)

    assert list(opsomming) == ["Kaapstad", "Leeg-Alias", "Oud"]
    assert opsomming["Kaapstad"] == {
        "subplekke": 2,
        "munisipaliteite": ["City of Cape Town", "WC024"],
        "in_csv": True,
    }
    assert opsomming["Leeg-Alias"] == {"subplekke": 0, "munisipaliteite": [], "in_csv": True}
    assert opsomming["Oud"]["in_csv"] is False
    assert opsomming["Oud"]["munisipaliteite"] == ["City of Tshwane"]


def test_lees_alias_name_uit_regte_csv():
    name = kontroleer.lees_alias_name(kontroleer.ALIASSE_CSV_PAD)
    assert "Kaapstad" in name
    assert "Pretoria-Oos" not in name


# --- harde hekke (final-review fix round) ------------------------------------------


def _goeie_resultate():
    muni_res = {"metro": 8, "plaaslik": 205, "distrik": 44, "kodes": [f"M{i}" for i in range(257)]}
    wyke_res = {"totaal": 4485, "wyk_ids": [f"{i:08d}" for i in range(4485)]}
    stasies_res = {"totaal": 3, "onbekende_wyk": [], "vd_nommers": ["1", "2", "3"]}
    plekke_res = {
        "totaal": 10,
        "plek_wyke_totaal": 20,
        "alias_totaal": 5,
        "sonder_wyk": [{"sp_kode": k} for k in sorted(kontroleer.BEKENDE_HAWE_SP_KODES)],
        "sp_kodes": ["a", "b"],
        "plek_wyk_pare": [("a", "1"), ("a", "2"), ("b", "1")],
        "alias_opsomming": {"Kaapstad": {"subplekke": 126, "munisipaliteite": ["x"], "in_csv": True}},
    }
    raad_res = {"uitslae_totaal": 2789, "grootte_totaal": 213}
    return muni_res, wyke_res, stasies_res, plekke_res, raad_res


def test_harde_hekke_konstantes():
    assert kontroleer.VERWAG_WYKE_GELAAI == 4485
    assert kontroleer.VERWAG_MUNISIPALITEITE == 213
    assert kontroleer.VERWAG_DISTRIKTE == 44
    assert kontroleer.VERWAG_RADE_2021 == 213
    assert kontroleer.MAKS_PLEKKE_SONDER_WYK == 3
    assert kontroleer.BEKENDE_HAWE_SP_KODES == {"199056003", "199057014", "199063016"}


def test_harde_hekke_alles_goed():
    assert kontroleer.evalueer_harde_hekke(*_goeie_resultate()) == []


def test_harde_hekke_mislukte_afdelings_word_oorgeslaan():
    assert kontroleer.evalueer_harde_hekke(None, None, None, None, None) == []


def test_harde_hekke_verkeerde_tellings():
    muni_res, wyke_res, stasies_res, plekke_res, raad_res = _goeie_resultate()
    muni_res["plaaslik"] = 204
    muni_res["distrik"] = 43
    wyke_res["totaal"] = 4470
    raad_res["grootte_totaal"] = 212
    foute = kontroleer.evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res)
    assert len(foute) == 4
    assert any(f.startswith("munisipaliteite: 212") for f in foute)
    assert any(f.startswith("distrikte: 43") for f in foute)
    assert any(f.startswith("wyke: 4470") for f in foute)
    assert any("stg_raad_grootte_2021" in f and "212" in f for f in foute)


def test_harde_hekke_stasies_met_onbekende_wyk():
    muni_res, wyke_res, stasies_res, plekke_res, raad_res = _goeie_resultate()
    stasies_res["onbekende_wyk"] = ["34501001"]
    foute = kontroleer.evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res)
    assert len(foute) == 1 and "onbekende wyk" in foute[0]


def test_harde_hekke_plekke_sonder_wyk_meer_as_3():
    muni_res, wyke_res, stasies_res, plekke_res, raad_res = _goeie_resultate()
    plekke_res["sonder_wyk"].append({"sp_kode": "271002001"})
    foute = kontroleer.evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res)
    assert len(foute) == 1 and "plekke sonder wyk" in foute[0]


def test_harde_hekke_plekke_sonder_wyk_verkeerde_3():
    muni_res, wyke_res, stasies_res, plekke_res, raad_res = _goeie_resultate()
    plekke_res["sonder_wyk"] = [{"sp_kode": "199056003"}, {"sp_kode": "199057014"}, {"sp_kode": "292002001"}]
    foute = kontroleer.evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res)
    assert len(foute) == 1 and "plekke sonder wyk" in foute[0]


def test_harde_hekke_duplikaat_natuurlike_sleutels():
    muni_res, wyke_res, stasies_res, plekke_res, raad_res = _goeie_resultate()
    muni_res["kodes"].append("M0")
    wyke_res["wyk_ids"].append("00000000")
    stasies_res["vd_nommers"].append("1")
    plekke_res["sp_kodes"].append("a")
    plekke_res["plek_wyk_pare"].append(("a", "1"))
    foute = kontroleer.evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res)
    assert len(foute) == 5
    assert all("duplikaat" in f for f in foute)


def test_harde_hekke_alias_met_0_subplekke():
    muni_res, wyke_res, stasies_res, plekke_res, raad_res = _goeie_resultate()
    plekke_res["alias_opsomming"]["Johannesburg-Suid"] = {"subplekke": 0, "munisipaliteite": [], "in_csv": True}
    foute = kontroleer.evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res)
    assert foute == ["aliasse wat na 0 subplekke oplos: ['Johannesburg-Suid']"]


def test_vind_duplikate():
    assert kontroleer.vind_duplikate(["b", "a", "b", "c", "a"]) == ["a", "b"]
    assert kontroleer.vind_duplikate([]) == []
