"""Text normalisation helpers for matching Afrikaans place/ward names."""

from __future__ import annotations

import re
import unicodedata

_SKEI_PATROON = re.compile(r"[-'’]")
_SPASIE_PATROON = re.compile(r"\s+")

_LANDELIKE_AGTERVOEGSELS = (" NU", " SH")
_STEDELIKE_AGTERVOEGSEL = " SP"


def normaliseer(s: str) -> str:
    """Lowercase, strip accents, fold hyphens/apostrophes to spaces.

    "Pretoria-Oos" -> "pretoria oos"; "Môrelig" -> "morelig".
    """
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = _SKEI_PATROON.sub(" ", s)
    s = _SPASIE_PATROON.sub(" ", s).strip()
    return s


def skoon_plek_naam(naam: str) -> tuple[str, bool]:
    """Strip the Subplace/MainPlace type suffix, return (naam, landelik).

    " SP" -> stedelik (landelik=False). " NU" or " SH" -> landelik=True.
    """
    naam = naam.strip()
    if naam.endswith(_STEDELIKE_AGTERVOEGSEL):
        return naam[: -len(_STEDELIKE_AGTERVOEGSEL)].strip(), False
    for agtervoegsel in _LANDELIKE_AGTERVOEGSELS:
        if naam.endswith(agtervoegsel):
            return naam[: -len(agtervoegsel)].strip(), True
    return naam, False
