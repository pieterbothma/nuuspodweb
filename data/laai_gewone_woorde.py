"""Laai `gewone_woorde`: eenwoord-plekname wat ook gewone woorde is.

Gebruik (uit `data/`):

    uv run --with httpx python laai_gewone_woorde.py            # laai en herbou plek_name
    uv run --with httpx python laai_gewone_woorde.py --droogloop

Census sub-place names include ordinary English words and surnames ("Rugby", "Memory",
"Point", "Global", "Washington"), and a headline that uses the word would otherwise land on
a ward. `koppel_nuus()` ignores a one-word place name that is in this table; multi-word
names ("Pretoria North") are never affected.

The list is the intersection of the single-word place and alias names with the system word
list (`/usr/share/dict/words`, present on every Mac), plus a fixed stoplist of common
headline words and foreign places. Afterwards `bou_plek_name()` must be run so the flag is
applied — this script prints the SQL to run with the Supabase MCP (the RPC itself runs
longer than PostgREST's 8 s statement timeout).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

from lib import supabase, teks

WOORDELYS = Path("/usr/share/dict/words")

# Headline words and foreign places that are also South African place names but are not
# in the system word list, or are proper nouns that almost never mean the SA place.
STOPWOORDE = frozenset({
    "washington", "london", "rome", "paris", "india", "china", "europe", "palestine",
    "zimbabwe", "kenya", "nairobi", "japan", "iran", "israel", "gaza", "america", "canada",
    "brazil", "moscow", "berlin", "africa", "mandela", "zuma", "ramaphosa", "mbeki",
    "trump", "global", "central", "industrial", "extension", "township", "informal",
    "settlement", "police", "court", "council", "school", "hospital", "station",
    "springbok", "harmony", "rugby", "matlala", "masemola", "mkhize", "james", "maile",
    "majozi", "phumlani", "mncwabe", "vusimuzi", "arena", "memory", "loss", "sparks",
    "five", "seven", "military", "point", "fairways", "union", "unity", "freedom",
    "victory", "progress", "president", "premier", "mayor", "water", "power",
})


def normaliseer(s: str) -> str:
    """Same as SQL normaliseer_nuusteks: normaliseer + every non-alphanumeric → space."""
    return re.sub(r"[^a-z0-9]+", " ", teks.normaliseer(s)).strip()


def gewone_woorde(name: list[str], woordelys: set[str]) -> list[str]:
    """Single-word normalised names (4+ letters) that are ordinary words, plus the stoplist."""
    enkel = {n for n in (normaliseer(x) for x in name) if n and " " not in n and len(n) >= 4}
    return sorted((enkel & woordelys) | STOPWOORDE)


def lees_woordelys(pad: Path = WOORDELYS) -> set[str]:
    return {w.strip().lower() for w in pad.read_text().splitlines() if w.strip().isalpha()}


def hoof(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--droogloop", action="store_true")
    args = ap.parse_args(argv)

    plekke = supabase.kry_alles("plekke", {"select": "sp_kode,naam,mp_naam"}, orde="sp_kode")
    aliasse = supabase.kry_alles("plek_aliasse", {"select": "alias,sp_kode"}, orde="alias,sp_kode")
    name = [re.sub(r"\s+(NU|SH)$", "", n) for p in plekke for n in (p["naam"], p.get("mp_naam")) if n]
    name += [a["alias"] for a in aliasse]

    woorde = gewone_woorde(name, lees_woordelys())
    print(f"{len(woorde)} gewone woorde uit {len(set(name))} plekname")
    if args.droogloop:
        print(", ".join(woorde[:60]), "…")
        return 0

    with supabase._bou_klient() as klient:
        resp = klient.delete("gewone_woorde", params={"woord": "not.is.null"})
        if resp.status_code >= 400:
            print(f"kon nie gewone_woorde leegmaak nie: {resp.status_code}", file=sys.stderr)
            return 1
    supabase.plaas_bondels("gewone_woorde", [{"woord": w} for w in woorde])
    print("Gelaai. Herbou nou die indeks met die Supabase MCP: select public.bou_plek_name();")
    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
