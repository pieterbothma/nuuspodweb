from laai_wyk_uitslae_2021 import bou_rye, lees_2021, pas_wyke


def ry(wyk, vd, ballot, party, stemme, reg=1000, bedorwe=5):
    return {"Ward": f"Ward {wyk}", "VotingDistrict": vd, "BallotType": ballot, "PartyName": party,
            "TotalValidVotes": str(stemme), "RegisteredVoters": str(reg), "SpoiltVotes": str(bedorwe)}


RYE = [
    ry("19100055", "9001", "Ward", "PARTY A", 300),
    ry("19100055", "9001", "Ward", "INDEPENDENT", 50),
    ry("19100055", "9001", "PR", "PARTY A", 999),  # PR ballot is ignored for votes
    ry("19100055", "9002", "Ward", "PARTY A", 100, reg=800, bedorwe=2),
    ry("19100055", "9002", "Ward", "PARTY B", 0, reg=800, bedorwe=2),
    ry("19100056", "9003", "Ward", "PARTY B", 400),
]


def test_lees_2021_tel_net_die_wykstembrief_en_elke_stemdistrik_een_keer():
    wyke, dubbel = lees_2021(RYE)
    w = wyke["19100055"]
    assert w.vds == {"9001", "9002"}
    assert dict(w.stemme) == {"PARTY A": 400, "INDEPENDENT": 50, "PARTY B": 0}
    assert sum(w.geregistreer.values()) == 1800  # per VD once, not per party row
    assert sum(w.bedorwe.values()) == 7
    assert dubbel == []


def test_stemdistrik_in_twee_wyke_word_gerapporteer():
    _, dubbel = lees_2021(RYE + [ry("19100056", "9001", "Ward", "PARTY B", 1)])
    assert dubbel == ["9001"]


def test_pas_net_identiese_stelle_selfde_id_eerste_dan_hernommer():
    w21 = {"19100055": {"9001", "9002"}, "19100056": {"9003"}, "19100057": {"9004", "9005"}}
    w26 = {
        "19100055": {"9001", "9002"},   # unchanged
        "19100099": {"9003"},           # renumbered, same area
        "19100057": {"9004"},           # split: not a match
        "19100058": {"9005", "9006"},   # new shape: not a match
    }
    assert pas_wyke(w21, w26) == {"19100055": "19100055", "19100099": "19100056"}


def test_bou_rye_laat_nul_stemme_uit_en_klop():
    wyke, _ = lees_2021(RYE)
    opsomming, uitslae, foute = bou_rye({"19100055": "19100055"}, wyke)
    assert foute == []
    assert opsomming == [{"wyk_id": "19100055", "wyk_id_2021": "19100055", "wyk_nr_2021": 55,
                          "geregistreer": 1800, "geldige_stemme": 450, "bedorwe_stemme": 7, "stemdistrikte": 2}]
    assert [(r["party_naam"], r["stemme"]) for r in uitslae] == [("INDEPENDENT", 50), ("PARTY A", 400)]


def test_bou_rye_vang_meer_stemme_as_kiesers():
    wyke, _ = lees_2021([ry("19100060", "9100", "Ward", "PARTY A", 900, reg=100)])
    _, _, foute = bou_rye({"19100060": "19100060"}, wyke)
    assert foute and "geregistreer" in foute[0]
