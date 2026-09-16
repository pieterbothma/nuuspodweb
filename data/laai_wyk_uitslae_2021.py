"""Laai amptelike 2021-wykuitslae vir 2026-wyke met presies dieselfde stemdistrikte.

Gebruik (uit `data/`):

    uv run --with httpx python laai_wyk_uitslae_2021.py
    uv run --with httpx python laai_wyk_uitslae_2021.py --droogloop   # niks skryf nie

Piet (2026-09-16): a ward page shows the 2021 ward result only when the 2026 ward is made
up of exactly the same voting districts as a 2021 ward — the same area, so the IEC's own
2021 figures describe it without any estimate. Wards that were redrawn get nothing here;
the site tells the reader the boundaries changed. The internal VD remap for the prediction
model is a different thing and never goes through this loader.

Source: `bron/lge2021_*.csv`, the IEC's official 2021 results per voting district (one row
per VD × ballot × party). Only the ward ballot is loaded. The 2026 side comes from
`stg_stemstasies` (voting district → 2026 ward) and `stg_wyke`.

Per matched ward:
- `stg_wyk_2021_opsomming`: 2021 ward id and number, registered voters, valid and spoilt
  ward-ballot votes, number of voting districts.
- `stg_wyk_uitslae_2021`: votes per party on the ward ballot (parties with 0 votes left
  out). The IEC file names every independent "INDEPENDENT", so several independents in one
  ward are one row — the site labels it accordingly.

Hard checks before anything is written: every matched ward exists in `stg_wyke`; party votes
add up to the valid votes; valid + spoilt never exceeds registered voters; no voting
district sits in two 2021 wards. Writes `uitvoer/wyk-uitslae-2021-verslag.md`.
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

BASIS_PAD = Path(__file__).parent
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "wyk-uitslae-2021-verslag.md"
WYK_ID = re.compile(r"(\d{8})")


@dataclass
class Wyk2021:
    vds: set[str] = field(default_factory=set)
    geregistreer: dict[str, int] = field(default_factory=dict)  # per VD, ward ballot
    bedorwe: dict[str, int] = field(default_factory=dict)  # per VD, ward ballot
    stemme: dict[str, int] = field(default_factory=lambda: defaultdict(int))  # per party


def heel(s: str | None) -> int:
    s = (s or "").strip().replace(" ", "")
    return int(s) if s else 0


def lees_2021(rye: Iterable[dict]) -> tuple[dict[str, Wyk2021], list[str]]:
    """Group the per-VD rows into 2021 wards. Returns the wards and any VD found in two wards."""
    wyke: dict[str, Wyk2021] = defaultdict(Wyk2021)
    vd_wyk: dict[str, str] = {}
    dubbel: set[str] = set()
    for r in rye:
        m = WYK_ID.search(r.get("Ward") or "")
        vd = (r.get("VotingDistrict") or "").strip()
        if not m or not vd:
            continue
        wyk_id = m.group(1)
        if vd_wyk.setdefault(vd, wyk_id) != wyk_id:
            dubbel.add(vd)
        w = wyke[wyk_id]
        w.vds.add(vd)
        if (r.get("BallotType") or "").strip().lower() != "ward":
            continue
        w.geregistreer.setdefault(vd, heel(r.get("RegisteredVoters")))
        w.bedorwe.setdefault(vd, heel(r.get("SpoiltVotes")))
        party = (r.get("PartyName") or "").strip()
        if party:
            w.stemme[party] += heel(r.get("TotalValidVotes"))
    return dict(wyke), sorted(dubbel)


def pas_wyke(wyke_2021: dict[str, set[str]], wyke_2026: dict[str, set[str]]) -> dict[str, str]:
    """2026 ward id → 2021 ward id, only where the voting-district sets are identical.
    The same id is preferred; otherwise a renumbered ward with the identical set counts."""
    per_stel = {frozenset(v): k for k, v in wyke_2021.items() if v}
    uit: dict[str, str] = {}
    for wyk_id, vds in wyke_2026.items():
        if not vds:
            continue
        if wyke_2021.get(wyk_id) == vds:
            uit[wyk_id] = wyk_id
        elif frozenset(vds) in per_stel:
            uit[wyk_id] = per_stel[frozenset(vds)]
    return uit


def bou_rye(pas: dict[str, str], wyke_2021: dict[str, Wyk2021]) -> tuple[list[dict], list[dict], list[str]]:
    """The two stg_ row sets, plus any consistency error (empty list = fine)."""
    opsomming: list[dict] = []
    uitslae: list[dict] = []
    foute: list[str] = []
    for wyk_id in sorted(pas):
        w = wyke_2021[pas[wyk_id]]
        geldig = sum(w.stemme.values())
        geregistreer = sum(w.geregistreer.values())
        bedorwe = sum(w.bedorwe.values())
        if geldig == 0:
            foute.append(f"{wyk_id}: geen geldige wykstemme in 2021 nie")
            continue
        if geldig + bedorwe > geregistreer:
            foute.append(f"{wyk_id}: {geldig}+{bedorwe} stemme > {geregistreer} geregistreer")
        opsomming.append({
            "wyk_id": wyk_id,
            "wyk_id_2021": pas[wyk_id],
            "wyk_nr_2021": int(pas[wyk_id][-3:]),
            "geregistreer": geregistreer,
            "geldige_stemme": geldig,
            "bedorwe_stemme": bedorwe,
            "stemdistrikte": len(w.vds),
        })
        rye = [{"wyk_id": wyk_id, "party_naam": p, "stemme": s} for p, s in sorted(w.stemme.items()) if s > 0]
        if sum(r["stemme"] for r in rye) != geldig:
            foute.append(f"{wyk_id}: partystemme tel nie op na {geldig} nie")
        uitslae.extend(rye)
    return opsomming, uitslae, foute


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)
    r = [
        "# 2021-wykuitslae vir onveranderde wyke",
        "",
        f"- 2021-wyke in die IEC-lêers: {kw['wyke_2021']}",
        f"- 2026-wyke (stg_wyke): {kw['wyke_2026']}",
        f"- Onveranderd (selfde stemdistrikte): **{kw['gepas']}** "
        f"({kw['gepas'] / max(kw['wyke_2026'], 1):.0%}), waarvan hernommer: {kw['hernommer']}",
        f"- Partyrye gelaai: {kw['uitslae']}",
        f"- Stemdistrikte in twee 2021-wyke: {len(kw['dubbel'])}",
        "",
        "## Foute" if kw["foute"] else "Geen foute nie.",
        *[f"- {f}" for f in kw["foute"][:100]],
        "",
        "## Per munisipaliteit (onveranderd / totaal)",
        *[f"- {m}: {a}/{t}" for m, (a, t) in sorted(kw["per_muni"].items())],
    ]
    VERSLAG_PAD.write_text("\n".join(r) + "\n", encoding="utf-8")


def hoof(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--droogloop", action="store_true")
    args = ap.parse_args(argv)

    from lib import supabase  # network only from here on

    paaie = sorted(glob.glob(str(BASIS_PAD / "bron" / "lge2021_*.csv")))
    if len(paaie) != 9:
        print(f"verwag 9 provinsie-CSV's in bron/, het {len(paaie)}", file=sys.stderr)
        return 1

    def alle_rye():
        for pad in paaie:
            with open(pad, encoding="utf-8-sig", newline="") as f:
                yield from csv.DictReader(f)

    wyke_2021, dubbel = lees_2021(alle_rye())
    stasies = supabase.kry_alles("stg_stemstasies", {"select": "vd_nommer,wyk_id"}, orde="vd_nommer")
    wyke = supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"}, orde="wyk_id")
    wyke_2026: dict[str, set[str]] = defaultdict(set)
    for s in stasies:
        wyke_2026[s["wyk_id"]].add(str(s["vd_nommer"]).strip())

    pas = pas_wyke({k: w.vds for k, w in wyke_2021.items()}, dict(wyke_2026))
    opsomming, uitslae, foute = bou_rye(pas, wyke_2021)
    bekend = {w["wyk_id"] for w in wyke}
    foute += [f"{r['wyk_id']}: nie in stg_wyke nie" for r in opsomming if r["wyk_id"] not in bekend]
    foute += [f"stemdistrik {vd} in twee 2021-wyke" for vd in dubbel]

    per_muni: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for w in wyke:
        per_muni[w["muni_kode"]][1] += 1
        if w["wyk_id"] in pas:
            per_muni[w["muni_kode"]][0] += 1

    skryf_verslag(
        wyke_2021=len(wyke_2021), wyke_2026=len(wyke), gepas=len(opsomming),
        hernommer=sum(1 for k, v in pas.items() if k != v), uitslae=len(uitslae),
        dubbel=dubbel, foute=foute, per_muni=per_muni,
    )
    print(f"{len(opsomming)} onveranderde wyke, {len(uitslae)} partyrye, {len(foute)} fout(e). Verslag: {VERSLAG_PAD}")
    if foute:
        return 1
    if args.droogloop:
        print("Droogloop: niks geskryf nie.")
        return 0

    supabase.rpc("stg_leeg", {"tabel": "stg_wyk_uitslae_2021"})
    supabase.rpc("stg_leeg", {"tabel": "stg_wyk_2021_opsomming"})
    supabase.plaas_bondels("stg_wyk_2021_opsomming", opsomming, grootte=1000)
    supabase.plaas_bondels("stg_wyk_uitslae_2021", uitslae, grootte=2000)
    print("Gelaai na stg_. Publiseer met: python publiseer.py --datastelle wyk_2021_opsomming,wyk_uitslae_2021")
    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
