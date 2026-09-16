from laai_gewone_woorde import STOPWOORDE, gewone_woorde, normaliseer


def test_normaliseer_stem_ooreen_met_sql_nuusteks():
    assert normaliseer("Simon's Town") == "simon s town"
    assert normaliseer("  Pretoria-Noord (Oos)  ") == "pretoria noord oos"
    assert normaliseer("Môreson") == "moreson"


def test_net_eenwoord_name_wat_gewone_woorde_is():
    woordelys = {"rugby", "memory", "north", "pretoria"}
    uit = gewone_woorde(["Rugby", "Memory", "Pretoria North", "Soshanguve", "Ark"], woordelys)
    assert "rugby" in uit and "memory" in uit
    # Multi-word names are never flagged, and a name absent from the word list stays usable.
    assert "pretoria north" not in uit and "soshanguve" not in uit
    # Three letters or fewer never reach the index at all, so they are not listed either.
    assert "ark" not in uit


def test_stoplys_is_altyd_ingesluit():
    uit = gewone_woorde([], set())
    assert set(uit) == set(STOPWOORDE)
