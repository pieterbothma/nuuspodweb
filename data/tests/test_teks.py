from lib import teks


def test_normaliseer_pretoria_oos():
    assert teks.normaliseer("Pretoria-Oos") == "pretoria oos"


def test_normaliseer_morelig_omlaut():
    assert teks.normaliseer("Môrelig") == "morelig"


def test_normaliseer_die_boord():
    assert teks.normaliseer("Die Boord") == "die boord"


def test_normaliseer_accents_e_and_e_trema():
    assert teks.normaliseer("Café Eékê") == "cafe eeke"


def test_normaliseer_apostrophe_to_space():
    assert teks.normaliseer("N'kandla") == "n kandla"


def test_normaliseer_collapses_repeated_spaces():
    assert teks.normaliseer("Groot   Brak  Rivier") == "groot brak rivier"


def test_skoon_plek_naam_sp_suffix():
    assert teks.skoon_plek_naam("Stellenbosch SP") == ("Stellenbosch", False)


def test_skoon_plek_naam_nu_suffix():
    assert teks.skoon_plek_naam("Paarl NU") == ("Paarl", True)


def test_skoon_plek_naam_sh_suffix():
    assert teks.skoon_plek_naam("Kuilsrivier SH") == ("Kuilsrivier", True)


def test_skoon_plek_naam_trims_whitespace():
    assert teks.skoon_plek_naam("  Worcester SP  ") == ("Worcester", False)


def test_skoon_plek_naam_no_suffix():
    assert teks.skoon_plek_naam("George") == ("George", False)
