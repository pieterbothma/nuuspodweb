"""Laai die OVK se finale kandidaatlys(te) na `stg_partye` en `stg_kandidate`.

Gebruik (uit `data/`):

    uv run --with pdfplumber,httpx python laai_kandidate.py --bron bron/kandidate-2026-*.pdf
    ... --droogloop     # parse + validate against stg_ (read-only), write nothing
    ... --net-ontleed   # parse + offline checks only, no database at all

Every mode writes `uitvoer/kandidate-verslag.md` and exits non-zero on any failure.

Flow (default mode):
1. Parse every `--bron` file with `kandidate_ontleder.ontleed`; any parse error aborts
   before anything else happens.
2. `stg_partye`: distinct party names (independents excluded), sorted by name
   (Python code-point order, locale-independent), ids 1..N. `afkorting` stays null — the
   OVK lists carry no abbreviation column.
3. `stg_kandidate`: one row per parsed candidate, sorted by a total key (municipality,
   ballot, ward, party, list position, surname, full name, source file, source row),
   ids 1..N. The same input files therefore always yield the same ids, whatever order
   the parser or the shell glob delivered them in. `publiseer_tabel` publishes both
   tables with OVERRIDING SYSTEM VALUE and `id` as the conflict arbiter, so
   `kandidate.party_id` keeps pointing at the right party.
   Ids are stable for identical input only: a corrected OVK list that adds or removes
   a candidate shifts later ids. That is fine because a publish replaces the whole
   public table, and nothing on the site uses a candidate id in a URL.
4. Hard gates, all before `stg_leeg`: every row has a non-null unique integer id; the
   personal-data guard (below); every `muni_kode` in `stg_munisipaliteite`; every
   `wyk_id` in `stg_wyke` and belonging to the candidate's municipality; ballot type
   matches the council type; independents have no party and stand only in wards;
   party candidates have a party; PR rows have a list position; no duplicate
   `(muni_kode, stembrief, wyk_id, volle_naam, van, party_id)`; no empty names.
5. `stg_leeg` both tables, insert parties then candidates in batches, then re-count
   both tables and confirm no null id landed.

PERSONAL DATA RULE: the parser never reads the masked ID column (see
`kandidate_ontleder`). This loader re-asserts that on the exact rows it is about to
send: no text field may hold a 6+ digit run, `wyk_id` must be exactly 8 digits,
integer columns must be real integers (a list position of 6+ digits is refused), and a
row may carry no column outside the schema. Failure messages name the table, source
file, page, row and field — never a value. The report is scrubbed before it is
written: any digit run of 6+ that is not exactly 8 long (a ward id) is replaced, and
that replacement itself fails the run.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable, Iterator

import kandidate_ontleder as ko

BASIS_PAD = Path(__file__).parent
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "kandidate-verslag.md"

# The OVK's published 2026 totals (candidacies). Ward excludes independents.
# IEC_TOTAAL is the certified figure from the OVK media release of 16 Sep 2026 (136 790);
# the split below is still the pre-certification one from 14 Sep, for which no certified
# breakdown was published yet — differences there are expected and reported as decisions.
IEC_WYK_PARTY = 100_856
IEC_PV = 40_241
IEC_WYK_ONAFHANKLIK = 975
IEC_TOTAAL = 136_790
IEC_REGSTELLING_TOT = "25 Sep"

ID_SKANS_PATROON = ko.ID_SKANS_PATROON  # any 6+ digit run
WYK_ID_PATROON = re.compile(r"^\d{8}$")
MAKS_LYS_POSISIE = 99_999  # a list position of 6+ digits can only be a shifted ID

STEMBRIEF_ORDE = {"wyk": 0, "pv_plaaslik": 1, "pv_distrik": 2}
STEMBRIEWE_PER_TIPE = {
    "metro": {"wyk", "pv_plaaslik"},
    "plaaslik": {"wyk", "pv_plaaslik"},
    "distrik": {"pv_distrik"},
}

KANDIDAAT_KOLOMME = frozenset(
    {
        "id", "muni_kode", "stembrief", "wyk_id", "lys_posisie", "party_id", "onafhanklik",
        "volle_naam", "van", "bron_lêer", "bron_ry",
    }
)
PARTY_KOLOMME = frozenset({"id", "naam", "afkorting"})
KANDIDAAT_TEKSVELDE = ("muni_kode", "stembrief", "volle_naam", "van", "bron_lêer")
PARTY_TEKSVELDE = ("naam", "afkorting")
# Integer counters derived from sort order / page and row numbers, never from a cell
# of the ID column. `id` and `bron_ry` legitimately reach 6+ digits (142k candidates;
# bron_ry = page * 10000 + row), so they are type-checked rather than digit-scanned.
HEELGETAL_TELLERS = ("id", "party_id", "lys_posisie", "bron_ry")

MAKS_LYS = 30  # cap on items listed per failure line


# `kandidate-2026-<PROV>.pdf` → the municipality codes that belong to that province (local
# and metro prefixes plus the district councils). The Western Cape file is cut from the
# OVK's national PDF, whose first cut page still carries Northern Cape rows; every file is
# filtered so a row can only come from its own province, and the drop count is reported.
PROVINSIE_VOORVOEGSELS: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    "EC": (("EC", "BUF", "NMA"), frozenset({"DC10", "DC12", "DC13", "DC14", "DC15", "DC44"})),
    "FS": (("FS", "MAN"), frozenset({"DC16", "DC18", "DC19", "DC20"})),
    "GP": (("GT", "JHB", "TSH", "EKU"), frozenset({"DC42", "DC48"})),
    "KZN": (("KZN", "ETH"), frozenset({"DC21", "DC22", "DC23", "DC24", "DC25", "DC26", "DC27", "DC28", "DC29", "DC43"})),
    "LP": (("LIM",), frozenset({"DC33", "DC34", "DC35", "DC36", "DC47"})),
    "MP": (("MP",), frozenset({"DC30", "DC31", "DC32"})),
    "NC": (("NC",), frozenset({"DC6", "DC7", "DC8", "DC9", "DC45"})),
    "NW": (("NW",), frozenset({"DC37", "DC38", "DC39", "DC40"})),
    "WC": (("WC", "CPT"), frozenset({"DC1", "DC2", "DC3", "DC4", "DC5"})),
}
LÊER_PROVINSIE = re.compile(r"^kandidate-\d{4}-([A-Z]{2,3})\.pdf$")


def hou_eie_provinsie(kandidate: list, lêernaam: str) -> tuple[list, int]:
    """Keep only rows whose municipality belongs to the province in the file name. Files
    without a province suffix are returned unchanged."""
    m = LÊER_PROVINSIE.match(lêernaam)
    if not m or m.group(1) not in PROVINSIE_VOORVOEGSELS:
        return kandidate, 0
    voorvoegsels, distrikte = PROVINSIE_VOORVOEGSELS[m.group(1)]

    def hoort(kode: str | None) -> bool:
        kode = kode or ""
        return kode in distrikte or (not kode.startswith("DC") and kode.startswith(voorvoegsels))

    hou = [k for k in kandidate if hoort(k.muni_kode)]
    return hou, len(kandidate) - len(hou)


class BronFout(Exception):
    """A `--bron` argument cannot be used (missing, duplicate name, digits in the name)."""


# ---------------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------------


def getal(n: int) -> str:
    """12345 -> "12 345". Counts in the report are space-grouped so that no count ever
    looks like a 6+ digit run to the report scrubber."""
    return f"{n:,}".replace(",", " ")


def posisie(ry: dict) -> str:
    """"<file> bladsy B ry R" for a candidate row — the only way rows are identified in
    messages (never by name or id)."""
    bron_ry = ry.get("bron_ry")
    if isinstance(bron_ry, int) and not isinstance(bron_ry, bool):
        return f"{ry.get('bron_lêer')} bladsy {bron_ry // 10000} ry {bron_ry % 10000}"
    return f"{ry.get('bron_lêer')} (onbekende posisie)"


def bou_partye(kandidate: Iterable[ko.Kandidaat]) -> list[dict]:
    """Distinct non-independent party names, sorted, ids 1..N."""
    name = sorted({k.party_naam for k in kandidate if not k.onafhanklik})
    return [{"id": i, "naam": naam, "afkorting": None} for i, naam in enumerate(name, start=1)]


def _sorteer_sleutel(k: ko.Kandidaat) -> tuple:
    return (
        k.muni_kode or "",
        STEMBRIEF_ORDE.get(k.stembrief, 9),
        k.wyk_id or "",
        k.party_naam,
        k.lys_posisie if k.lys_posisie is not None else 0,
        k.van,
        k.volle_naam,
        k.bron_lêer,
        k.bron_ry,
    )


def bou_kandidaat_rye(kandidate: Iterable[ko.Kandidaat], partye: list[dict]) -> list[dict]:
    """`stg_kandidate` rows in a total, input-order-independent sort, ids 1..N."""
    party_id = {p["naam"]: p["id"] for p in partye}
    rye: list[dict] = []
    for i, k in enumerate(sorted(kandidate, key=_sorteer_sleutel), start=1):
        rye.append(
            {
                "id": i,
                "muni_kode": k.muni_kode,
                "stembrief": k.stembrief,
                "wyk_id": k.wyk_id,
                "lys_posisie": k.lys_posisie,
                "party_id": None if k.onafhanklik else party_id.get(k.party_naam),
                "onafhanklik": k.onafhanklik,
                "volle_naam": k.volle_naam,
                "van": k.van,
                "bron_lêer": k.bron_lêer,
                "bron_ry": k.bron_ry,
            }
        )
    return rye


def _is_heelgetal(waarde) -> bool:
    return isinstance(waarde, int) and not isinstance(waarde, bool)


def kontroleer_ids(rye: list[dict], tabel: str) -> list[str]:
    """Every row must carry a unique, positive integer id (stg_ ids are nullable in the
    schema, and publiseer_tabel orders and conflicts on id)."""
    foute: list[str] = []
    sonder = sum(1 for r in rye if not _is_heelgetal(r.get("id")) or r["id"] < 1)
    if sonder:
        foute.append(f"{tabel}: {getal(sonder)} ry(e) met 'n nul of ongeldige id")
    tellings = Counter(r.get("id") for r in rye if _is_heelgetal(r.get("id")))
    dubbel = sum(1 for n in tellings.values() if n > 1)
    if dubbel:
        foute.append(f"{tabel}: {getal(dubbel)} duplikaat id-waarde(s)")
    return foute


def kontroleer_id_skans(rye: list[dict], partye: list[dict]) -> list[str]:
    """Personal-data guard over the exact rows about to be sent. Messages never carry a
    value — only table, source position and field name."""
    foute: list[str] = []
    for ry in rye:
        waar = posisie(ry)
        vreemd = set(ry) - KANDIDAAT_KOLOMME
        if vreemd:
            foute.append(f"ID-skans: stg_kandidate {waar}: onverwagte kolom(me) {sorted(vreemd)}")
        for veld in KANDIDAAT_TEKSVELDE:
            waarde = ry.get(veld)
            if waarde is not None and ID_SKANS_PATROON.search(str(waarde)):
                foute.append(f"ID-skans: stg_kandidate {waar}: veld '{veld}' dra 'n 6+-syferreeks — waarde nie gewys nie")
        wyk_id = ry.get("wyk_id")
        if wyk_id is not None and not (isinstance(wyk_id, str) and WYK_ID_PATROON.match(wyk_id)):
            foute.append(f"ID-skans: stg_kandidate {waar}: wyk_id is nie presies 8 syfers nie — waarde nie gewys nie")
        for veld in HEELGETAL_TELLERS:
            waarde = ry.get(veld)
            if waarde is not None and not _is_heelgetal(waarde):
                foute.append(f"ID-skans: stg_kandidate {waar}: veld '{veld}' is nie 'n heelgetal nie")
        lys = ry.get("lys_posisie")
        if _is_heelgetal(lys) and lys > MAKS_LYS_POSISIE:
            foute.append(f"ID-skans: stg_kandidate {waar}: lys_posisie het 6+ syfers — waarde nie gewys nie")

    for indeks, party in enumerate(partye, start=1):
        vreemd = set(party) - PARTY_KOLOMME
        if vreemd:
            foute.append(f"ID-skans: stg_partye ry {indeks}: onverwagte kolom(me) {sorted(vreemd)}")
        for veld in PARTY_TEKSVELDE:
            waarde = party.get(veld)
            if waarde is not None and ID_SKANS_PATROON.search(str(waarde)):
                foute.append(f"ID-skans: stg_partye ry {indeks}: veld '{veld}' dra 'n 6+-syferreeks — waarde nie gewys nie")
        if party.get("id") is not None and not _is_heelgetal(party.get("id")):
            foute.append(f"ID-skans: stg_partye ry {indeks}: id is nie 'n heelgetal nie")
    return foute


def duplikaat_sleutel(ry: dict) -> tuple:
    """Identical in every published field, list position included: a true duplicate row.
    (Piet, 2026-09-16: the same person at two positions on one party list is kept as the
    OVK published it — list positions decide seats — and reported, not failed.)"""
    return (
        ry["muni_kode"], ry["stembrief"], ry["wyk_id"], ry["lys_posisie"],
        ry["volle_naam"], ry["van"], ry["party_id"],
    )


def vind_duplikate(rye: list[dict]) -> list[list[dict]]:
    """Groups (in first-seen order) of rows sharing the duplicate key."""
    groepe: dict[tuple, list[dict]] = defaultdict(list)
    for ry in rye:
        groepe[duplikaat_sleutel(ry)].append(ry)
    return [g for g in groepe.values() if len(g) > 1]


def herhaal_op_lys(rye: list[dict]) -> list[list[dict]]:
    """The same name on the same council's party list at more than one position — kept
    exactly as published, and listed in the report."""
    groepe: dict[tuple, list[dict]] = defaultdict(list)
    for ry in rye:
        if ry["lys_posisie"] is not None:
            groepe[(ry["muni_kode"], ry["stembrief"], ry["party_id"], ry["volle_naam"], ry["van"])].append(ry)
    return [g for g in groepe.values() if len({r["lys_posisie"] for r in g}) > 1]


def sonder_naam_posisies(kandidate: list) -> list[str]:
    """Source positions of rows the OVK published without a name or surname. They are kept
    (Piet, 2026-09-16: the candidate is on the ballot; the site shows "no name in the OVK
    list" in place of the name) and listed in the report — positions only, never a value."""
    return [
        f"{k.bron_lêer} bladsy {k.bron_ry // 10000} ry {k.bron_ry % 10000}"
        for k in kandidate
        if not ((k.volle_naam or "").strip() and (k.van or "").strip())
    ]


def _afkap(items: list, n: int = MAKS_LYS) -> str:
    lys = ", ".join(str(i) for i in items[:n])
    return lys + (f" … (+{getal(len(items) - n)})" if len(items) > n else "")


def valideer_struktuur(rye: list[dict], partye: list[dict]) -> list[str]:
    """Checks that need no reference data."""
    foute: list[str] = []
    foute.extend(kontroleer_ids(partye, "stg_partye"))
    foute.extend(kontroleer_ids(rye, "stg_kandidate"))

    party_ids = {p["id"] for p in partye}
    leë_partye = [i for i, p in enumerate(partye, start=1) if not (p.get("naam") or "").strip()]
    if leë_partye:
        foute.append(f"stg_partye: {getal(len(leë_partye))} party(e) met 'n leë naam")

    sonder_muni, sonder_wyk, sonder_lys = [], [], []
    onafhanklik_met_party, onafhanklik_op_pv, party_sonder_id, onbekende_party = [], [], [], []
    for ry in rye:
        if not ry["muni_kode"]:
            sonder_muni.append(posisie(ry))
        if ry["stembrief"] == "wyk":
            if not ry["wyk_id"]:
                sonder_wyk.append(posisie(ry))
        else:
            if ry["lys_posisie"] is None or ry["lys_posisie"] < 1:
                sonder_lys.append(posisie(ry))
        if ry["onafhanklik"]:
            if ry["party_id"] is not None:
                onafhanklik_met_party.append(posisie(ry))
            if ry["stembrief"] != "wyk":
                onafhanklik_op_pv.append(posisie(ry))
        else:
            if ry["party_id"] is None:
                party_sonder_id.append(posisie(ry))
            elif ry["party_id"] not in party_ids:
                onbekende_party.append(posisie(ry))

    for lys, beskrywing in (
        (sonder_muni, "muni_kode ontbreek (geen 'KODE - Naam' in die munisipaliteit-sel)"),

        (sonder_wyk, "wyk-stembrief sonder wyk_id"),
        (sonder_lys, "PV-stembrief sonder 'n geldige lys_posisie"),
        (onafhanklik_met_party, "onafhanklike kandidaat met 'n party_id"),
        (onafhanklik_op_pv, "onafhanklike kandidaat op 'n PV-lys"),
        (party_sonder_id, "partykandidaat sonder party_id"),
        (onbekende_party, "party_id nie in stg_partye nie"),
    ):
        if lys:
            foute.append(f"{beskrywing}: {getal(len(lys))} — {_afkap(lys)}")

    duplikate = vind_duplikate(rye)
    if duplikate:
        beskryf = [" = ".join(posisie(r) for r in groep) for groep in duplikate]
        foute.append(
            f"duplikate op (muni_kode, stembrief, wyk_id, lys_posisie, volle_naam, van, party_id): "
            f"{getal(len(duplikate))} groep(e) — {_afkap(beskryf, 10)}"
        )
    return foute


def valideer_verwysings(rye: list[dict], munis: dict[str, dict], wyke: dict[str, str]) -> list[str]:
    """Checks against stg_munisipaliteite (kode -> {tipe, ...}) and stg_wyke (wyk_id ->
    muni_kode)."""
    foute: list[str] = []
    if not munis:
        foute.append("stg_munisipaliteite is leeg — laai eers laai_wyke.py")
    if not wyke:
        foute.append("stg_wyke is leeg — laai eers laai_wyke.py")
    if foute:
        return foute

    onbekende_muni: Counter[str] = Counter()
    onbekende_wyk: Counter[str] = Counter()
    verkeerde_muni: dict[str, tuple[str, str]] = {}
    verkeerde_stembrief: Counter[tuple[str, str, str]] = Counter()
    for ry in rye:
        kode = ry["muni_kode"]
        if kode and kode not in munis:
            onbekende_muni[kode] += 1
        elif kode:
            tipe = munis[kode].get("tipe")
            if ry["stembrief"] not in STEMBRIEWE_PER_TIPE.get(tipe, set()):
                verkeerde_stembrief[(kode, tipe, ry["stembrief"])] += 1
        wyk_id = ry["wyk_id"]
        if wyk_id:
            if wyk_id not in wyke:
                onbekende_wyk[wyk_id] += 1
            elif kode and wyke[wyk_id] != kode:
                verkeerde_muni[wyk_id] = (wyke[wyk_id], kode)

    if onbekende_muni:
        items = [f"{k} ({getal(n)} rye)" for k, n in sorted(onbekende_muni.items())]
        foute.append(f"muni_kode nie in stg_munisipaliteite nie: {getal(len(items))} — {_afkap(items)}")
    if onbekende_wyk:
        items = [f"{w} ({getal(n)} rye)" for w, n in sorted(onbekende_wyk.items())]
        foute.append(f"wyk_id nie in stg_wyke nie: {getal(len(items))} — {_afkap(items)}")
    if verkeerde_muni:
        items = [f"{w} hoort by {reg}, kandidaat staan in {kand}" for w, (reg, kand) in sorted(verkeerde_muni.items())]
        foute.append(f"wyk in 'n ander munisipaliteit: {getal(len(items))} — {_afkap(items)}")
    if verkeerde_stembrief:
        items = [
            f"{kode} ({tipe}) het {getal(n)} {stembrief}-rye"
            for (kode, tipe, stembrief), n in sorted(verkeerde_stembrief.items())
        ]
        foute.append(f"stembrief pas nie by die raadstipe nie (distrik = net pv_distrik): {_afkap(items)}")
    return foute


def valideer(rye: list[dict], partye: list[dict], munis: dict[str, dict], wyke: dict[str, str]) -> list[str]:
    return valideer_struktuur(rye, partye) + valideer_verwysings(rye, munis, wyke)


def tel_stembriewe(rye: list[dict]) -> dict[str, int]:
    wyk_party = sum(1 for r in rye if r["stembrief"] == "wyk" and not r["onafhanklik"])
    wyk_onafhanklik = sum(1 for r in rye if r["stembrief"] == "wyk" and r["onafhanklik"])
    pv_plaaslik = sum(1 for r in rye if r["stembrief"] == "pv_plaaslik")
    pv_distrik = sum(1 for r in rye if r["stembrief"] == "pv_distrik")
    return {
        "wyk_party": wyk_party,
        "wyk_onafhanklik": wyk_onafhanklik,
        "pv_plaaslik": pv_plaaslik,
        "pv_distrik": pv_distrik,
        "pv": pv_plaaslik + pv_distrik,
        "totaal": len(rye),
    }


def vergelyk_met_iec(tellings: dict[str, int]) -> list[str]:
    """Each count that differs from the OVK's published figure, as a decision for Piet —
    never an automatic failure (the OVK corrects its lists until 25 Sep)."""
    besluite: list[str] = []
    for sleutel, etiket, amptelik in (
        ("wyk_party", "wykkandidate (party)", IEC_WYK_PARTY),
        ("wyk_onafhanklik", "onafhanklike wykkandidate", IEC_WYK_ONAFHANKLIK),
        ("pv", "PV-kandidate (plaaslik + distrik)", IEC_PV),
        ("totaal", "totaal", IEC_TOTAAL),
    ):
        gekry = tellings.get(sleutel, 0)
        if gekry != amptelik:
            verskil = gekry - amptelik
            teken = "+" if verskil > 0 else "-"
            besluite.append(
                f"{etiket}: gelaai {getal(gekry)}, OVK {getal(amptelik)} (verskil {teken}{getal(abs(verskil))})"
            )
    return besluite


def waarskuwings(rye: list[dict], partye: list[dict], munis: dict[str, dict] | None, wyke: dict[str, str] | None) -> list[str]:
    """Not gates: things Piet should see before approving."""
    uit: list[str] = []

    posisies = Counter(
        (r["muni_kode"], r["stembrief"], r["party_id"], r["lys_posisie"]) for r in rye if r["lys_posisie"] is not None
    )
    dubbel = sorted((k for k, n in posisies.items() if n > 1), key=str)
    if dubbel:
        naam = {p["id"]: p["naam"] for p in partye}
        items = [f"{m} {s} {naam.get(p, p)} posisie {lp}" for m, s, p, lp in dubbel]
        uit.append(f"dieselfde lysposisie twee keer op een partylys: {getal(len(items))} — {_afkap(items)}")

    genormaliseer: dict[str, list[str]] = defaultdict(list)
    for p in partye:
        genormaliseer[re.sub(r"[^a-z0-9]", "", p["naam"].casefold())].append(p["naam"])
    amper = [" / ".join(v) for v in genormaliseer.values() if len(v) > 1]
    if amper:
        uit.append(f"partyname wat net in hoofletters/leestekens verskil: {_afkap(amper)}")

    if wyke:
        met_kandidaat = {r["wyk_id"] for r in rye if r["stembrief"] == "wyk" and r["wyk_id"]}
        sonder = sorted(set(wyke) - met_kandidaat)
        if sonder:
            per_muni = Counter(wyke[w] for w in sonder)
            items = [f"{m} ({n})" for m, n in sorted(per_muni.items())]
            uit.append(f"wyke sonder enige wykkandidaat: {getal(len(sonder))} — per munisipaliteit: {_afkap(items, 60)}")

    if munis:
        met = {r["muni_kode"] for r in rye}
        rade_sonder = sorted(k for k, m in munis.items() if k not in met)
        if rade_sonder:
            uit.append(
                f"rade/distrikte sonder enige kandidaat: {getal(len(rade_sonder))} — {_afkap(rade_sonder, 60)} "
                "(ontbreek 'n provinsie se lêer?)"
            )
    return uit


def per_groep(rye: list[dict], groep: Callable[[dict], str]) -> dict[str, dict[str, int]]:
    emmers: dict[str, list[dict]] = defaultdict(list)
    for r in rye:
        emmers[groep(r)].append(r)
    return {k: tel_stembriewe(v) for k, v in sorted(emmers.items())}


def skrop_verslag(teks: str) -> tuple[str, int]:
    """Replace every 6+ digit run that is not exactly 8 digits (a ward id) — returns the
    scrubbed text and how many runs were replaced."""
    vervang = 0

    def _vervang(m: re.Match) -> str:
        nonlocal vervang
        if len(m.group(0)) == 8:
            return m.group(0)
        vervang += 1
        return "[syfers weggelaat]"

    return ID_SKANS_PATROON.sub(_vervang, teks), vervang


def kontroleer_bronne(bronne: list[str], bestaan: Callable[[Path], bool]) -> list[str]:
    foute: list[str] = []
    if not bronne:
        foute.append("geen --bron-lêer gegee nie")
    name = Counter(Path(b).name for b in bronne)
    for naam, n in sorted(name.items()):
        if n > 1:
            foute.append(f"lêernaam {naam} kom {n} keer voor — elke bronlêer moet 'n unieke naam hê")
        if ID_SKANS_PATROON.search(naam):
            foute.append(
                f"lêernaam '{skrop_verslag(naam)[0]}' bevat 'n 6+-syferreeks (bron_lêer word gestoor) — "
                "hernoem na bv. kandidate-2026-WC.pdf"
            )
    for b in bronne:
        if not bestaan(Path(b)):
            foute.append(f"bronlêer nie gevind nie: {Path(b).name}")
    return foute


# ---------------------------------------------------------------------------------
# Database (injected into hoof so tests stay offline)
# ---------------------------------------------------------------------------------


def lees_verwysings() -> tuple[dict[str, dict], dict[str, str]]:
    from lib import supabase

    munis = {
        m["kode"]: m
        for m in supabase.kry_alles("stg_munisipaliteite", {"select": "kode,naam,tipe,provinsie"}, orde="kode")
    }
    wyke = {w["wyk_id"]: w["muni_kode"] for w in supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"}, orde="wyk_id")}
    return munis, wyke


def skryf_stg(partye: list[dict], rye: list[dict]) -> None:
    """Empty both stg_ tables, insert, then verify counts and that no id is null."""
    import httpx

    from lib import omgewing, supabase

    supabase.rpc("stg_leeg", {"tabel": "stg_kandidate"})
    supabase.rpc("stg_leeg", {"tabel": "stg_partye"})
    supabase.plaas_bondels("stg_partye", partye, grootte=500)
    supabase.plaas_bondels("stg_kandidate", rye, grootte=1000)

    waardes = omgewing.lees()
    with httpx.Client(
        base_url=waardes["url"].rstrip("/") + "/rest/v1/",
        headers={"apikey": waardes["sleutel"], "Authorization": f"Bearer {waardes['sleutel']}"},
        timeout=30.0,
    ) as klient:

        def tel(tabel: str, parameters: dict | None = None) -> int:
            resp = klient.get(
                tabel,
                params={"select": "id", **(parameters or {})},
                headers={"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"},
            )
            if resp.status_code >= 400:
                raise supabase.SupabaseFout(resp.text[:500])
            return int(resp.headers.get("content-range", "*/0").rsplit("/", 1)[-1])

        for tabel, verwag in (("stg_partye", len(partye)), ("stg_kandidate", len(rye))):
            gekry = tel(tabel)
            if gekry != verwag:
                raise supabase.SupabaseFout(f"{tabel}: {gekry} rye ná laai, verwag {verwag}")
            nul = tel(tabel, {"id": "is.null"})
            if nul:
                raise supabase.SupabaseFout(f"{tabel}: {nul} rye met 'n nul id ná laai")


# ---------------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------------


def bou_verslag(**kw) -> str:
    r: list[str] = []
    r.append("# Kandidaatlys-verslag")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}  ")
    r.append(f"Modus: **{kw['modus']}**")
    r.append("")

    foute: list[str] = kw["foute"]
    r.append("## Uitkoms")
    if foute:
        r.append(f"**GEFAAL — {kw['skryf_status']}**")
        r.append("")
        for f in foute:
            r.append(f"- {f}")
    else:
        r.append(f"**Alle hekke geslaag — {kw['skryf_status']}**")
    r.append("")

    if kw.get("sonder_naam"):
        r.append(f"## Sonder naam of van in die OVK-lys — behou, werf wys 'naam nie in die lys nie' ({getal(len(kw['sonder_naam']))})")
        r.extend(f"- {w}" for w in kw["sonder_naam"])
        r.append("")
    herhaal = herhaal_op_lys(kw.get("rye") or [])
    if herhaal:
        r.append(f"## Herhaal op dieselfde partylys — behou soos gepubliseer ({getal(len(herhaal))})")
        r.extend("- " + " = ".join(f"{posisie(x)} (posisie {x['lys_posisie']})" for x in g) for g in herhaal)
        r.append("")

    r.append("## Bronlêers")
    for naam, n in kw.get("per_lêer", {}).items():
        weg = kw.get("ander_provinsie", {}).get(naam, 0)
        r.append(f"- `{naam}`: {getal(n)} kandidate" + (f" ({getal(weg)} rye van 'n ander provinsie weggelaat)" if weg else ""))
    if not kw.get("per_lêer"):
        r.append("- (niks ontleed nie)")
    r.append(f"- Ontleedtyd: {kw.get('ontleedtyd', 0):.1f}s")
    r.append("")

    rye: list[dict] = kw.get("rye") or []
    partye: list[dict] = kw.get("partye") or []
    if not rye:
        return "\n".join(r)

    t = tel_stembriewe(rye)
    r.append("## Tellings")
    r.append(f"- Kandidate (rye): **{getal(t['totaal'])}**")
    r.append(f"- Partye: **{getal(len(partye))}** (id 1–{getal(len(partye))}, gesorteer op naam)")
    r.append(f"- Onafhanklikes: **{getal(t['wyk_onafhanklik'])}** (net op wykstembriewe, geen party_id)")
    r.append("")
    r.append("| Stembrief | Rye |")
    r.append("|---|---:|")
    r.append(f"| wyk (party) | {getal(t['wyk_party'])} |")
    r.append(f"| wyk (onafhanklik) | {getal(t['wyk_onafhanklik'])} |")
    r.append(f"| pv_plaaslik | {getal(t['pv_plaaslik'])} |")
    r.append(f"| pv_distrik | {getal(t['pv_distrik'])} |")
    r.append(f"| **totaal** | **{getal(t['totaal'])}** |")
    r.append("")

    r.append("## Teen die OVK se gepubliseerde totale")
    r.append("| | Gelaai | OVK | Verskil |")
    r.append("|---|---:|---:|---:|")
    for sleutel, etiket, amptelik in (
        ("wyk_party", "wyk (party)", IEC_WYK_PARTY),
        ("wyk_onafhanklik", "wyk (onafhanklik)", IEC_WYK_ONAFHANKLIK),
        ("pv", "PV (plaaslik + distrik)", IEC_PV),
        ("totaal", "totaal", IEC_TOTAAL),
    ):
        r.append(f"| {etiket} | {getal(t[sleutel])} | {getal(amptelik)} | {getal(t[sleutel] - amptelik)} |")
    r.append("")
    besluite = vergelyk_met_iec(t)
    if besluite:
        r.append(
            f"**Besluit nodig (nie 'n outomatiese fout nie — die OVK korrigeer tot {IEC_REGSTELLING_TOT}):**"
        )
        for b in besluite:
            r.append(f"- {b}")
        r.append(
            "- Let wel: die OVK se syfers tel kandidaatskappe. Iemand wat op 'n wyk- én 'n PV-lys "
            "staan, is hier twee rye — soos in die OVK-lys self."
        )
    else:
        r.append("Presies gelyk aan die OVK se syfers.")
    r.append("")

    munis: dict[str, dict] | None = kw.get("munis")
    if munis:
        r.append("## Per provinsie")
        r.append("| Provinsie | wyk (party) | onafhanklik | pv_plaaslik | pv_distrik | totaal |")
        r.append("|---|---:|---:|---:|---:|---:|")
        for prov, pt in per_groep(rye, lambda x: munis.get(x["muni_kode"], {}).get("provinsie") or "ONBEKEND").items():
            r.append(
                f"| {prov} | {getal(pt['wyk_party'])} | {getal(pt['wyk_onafhanklik'])} | "
                f"{getal(pt['pv_plaaslik'])} | {getal(pt['pv_distrik'])} | {getal(pt['totaal'])} |"
            )
        r.append("")
    else:
        r.append("## Per provinsie")
        r.append("- Nie beskikbaar in `--net-ontleed` nie (vereis stg_munisipaliteite).")
        r.append("")

    r.append("## Per munisipaliteit")
    r.append("| Kode | Naam | wyk (party) | onafhanklik | pv_plaaslik | pv_distrik | totaal |")
    r.append("|---|---|---:|---:|---:|---:|---:|")
    for kode, pt in per_groep(rye, lambda x: x["muni_kode"] or "?").items():
        naam = (munis or {}).get(kode, {}).get("naam", "")
        r.append(
            f"| {kode} | {naam} | {getal(pt['wyk_party'])} | {getal(pt['wyk_onafhanklik'])} | "
            f"{getal(pt['pv_plaaslik'])} | {getal(pt['pv_distrik'])} | {getal(pt['totaal'])} |"
        )
    r.append("")

    r.append("## Partye")
    per_party = Counter(x["party_id"] for x in rye if x["party_id"] is not None)
    r.append("| id | Naam | Kandidate |")
    r.append("|---:|---|---:|")
    for p in partye:
        r.append(f"| {p['id']} | {p['naam']} | {getal(per_party.get(p['id'], 0))} |")
    r.append("")

    r.append("## Waarskuwings (geen hek nie)")
    ws = kw.get("waarskuwings") or []
    if ws:
        for w in ws:
            r.append(f"- {w}")
    else:
        r.append("- Geen.")
    r.append("")

    r.append("## Ontledingsreëls soos toegepas")
    r.append(
        "- Kolomme word per bladsy uit die kop-ry herken (Municipality, Party, Ward\\List, "
        "ID-nommer, Full name, Surname); die ID-kolom se waarde word nooit gelees nie."
    )
    r.append(
        f"- 'n Presies-8-syfer Ward\\List-waarde is 'n wykkandidaat ({getal(t['wyk_party'] + t['wyk_onafhanklik'])} rye); "
        f"enige ander heelgetal is 'n lysposisie ({getal(t['pv'])} rye)."
    )
    r.append(
        f"- 'n Munisipaliteit-sel wat met 'DC' begin of 'District' bevat, maak 'n lysposisie "
        f"pv_distrik ({getal(t['pv_distrik'])} rye); die laaier kontroleer dit ook teen "
        "stg_munisipaliteite.tipe."
    )
    r.append(
        f"- Party 'INDEPENDENT' (hoofletter-onsensitief) = onafhanklik ({getal(t['wyk_onafhanklik'])} rye); "
        "hulle kry geen party-ry nie."
    )
    r.append("- 'n Leë munisipaliteit- of party-sel stop die ontleding; niks word van 'n vorige ry oorgedra nie.")
    r.append(
        "- Hierdie reëls is op die 2021 Wes-Kaap-lys bevestig. Is die bron 'n 2026-lêer, "
        "bevestig die tellings hierbo teen die OVK s'n voordat Piet goedkeur."
    )
    r.append("")

    r.append("## Tydsberekening")
    r.append(f"- Ontleding: {kw.get('ontleedtyd', 0):.1f}s")
    r.append(f"- Validering: {kw.get('valideertyd', 0):.1f}s")
    r.append(f"- Skryf: {kw.get('skryftyd', 0):.1f}s")
    r.append("")
    return "\n".join(r)


# ---------------------------------------------------------------------------------
# Hoof
# ---------------------------------------------------------------------------------


def hoof(
    argv: list[str] | None = None,
    *,
    ontleed: Callable[[Path], Iterator[ko.Kandidaat]] = ko.ontleed,
    lees_verwysings: Callable[[], tuple[dict, dict]] = lees_verwysings,
    skryf_stg: Callable[[list[dict], list[dict]], None] = skryf_stg,
    bestaan: Callable[[Path], bool] = Path.exists,
    verslag_pad: Path = VERSLAG_PAD,
) -> int:
    parser = argparse.ArgumentParser(description="Laai die OVK-kandidaatlys(te) na stg_partye en stg_kandidate.")
    parser.add_argument("--bron", nargs="+", required=True, help="een of meer kandidaatlys-PDF's")
    modus_groep = parser.add_mutually_exclusive_group()
    modus_groep.add_argument("--net-ontleed", action="store_true", help="ontleed en rapporteer; geen databasis nie")
    modus_groep.add_argument("--droogloop", action="store_true", help="ontleed en valideer teen stg_ (lees-alleen); skryf niks")
    ns = parser.parse_args(argv)

    modus = "net-ontleed" if ns.net_ontleed else "droogloop" if ns.droogloop else "laai"
    konteks: dict = {
        "tydstempel": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "modus": modus,
        "foute": [],
        "skryf_status": "NIKS GESKRYF NIE",
    }
    foute: list[str] = konteks["foute"]

    def klaar(kode: int) -> int:
        teks, vervang = skrop_verslag(bou_verslag(**konteks))
        if vervang:
            # Should be impossible after the row guard; if it happens the run fails.
            teks += f"\n\n**ID-skans op die verslag self: {vervang} syferreeks(e) weggelaat — die lopie het gefaal.**\n"
            kode = 1
        verslag_pad.parent.mkdir(parents=True, exist_ok=True)
        verslag_pad.write_text(teks)
        t = tel_stembriewe(konteks.get("rye") or [])
        print(
            f"[{modus}] kandidate: {getal(t['totaal'])} (wyk party {getal(t['wyk_party'])}, "
            f"onafhanklik {getal(t['wyk_onafhanklik'])}, pv {getal(t['pv'])}); "
            f"partye: {getal(len(konteks.get('partye') or []))}"
        )
        for f in konteks["foute"]:
            print(f"  FOUT: {skrop_verslag(f)[0]}", file=sys.stderr)
        print(f"{konteks['skryf_status']}. Verslag: {verslag_pad}")
        return kode

    # --- 1. bronne + ontleding --------------------------------------------------------
    foute.extend(kontroleer_bronne(ns.bron, bestaan))
    if foute:
        return klaar(1)

    begin = time.monotonic()
    kandidate: list[ko.Kandidaat] = []
    per_lêer: dict[str, int] = {}
    for bron in ns.bron:
        pad = Path(bron)
        try:
            uit_lêer = list(ontleed(pad))
        except ko.KandidaatOntledingFout as fout:
            foute.append(f"ontleding van {pad.name} het misluk: {fout}")
            break
        except Exception as fout:  # corrupt PDF etc. — type and scrubbed message only
            foute.append(f"ontleding van {pad.name} het misluk: {type(fout).__name__}: {skrop_verslag(str(fout)[:300])[0]}")
            break
        uit_lêer, weggelaat = hou_eie_provinsie(uit_lêer, pad.name)
        if weggelaat:
            konteks.setdefault("ander_provinsie", {})[pad.name] = weggelaat
        if not uit_lêer:
            foute.append(f"{pad.name}: 0 kandidate ontleed")
        per_lêer[pad.name] = len(uit_lêer)
        kandidate.extend(uit_lêer)
    konteks["per_lêer"] = per_lêer
    konteks["ontleedtyd"] = time.monotonic() - begin
    if foute:
        return klaar(1)
    konteks["sonder_naam"] = sonder_naam_posisies(kandidate)

    # --- 2-3. rye bou ------------------------------------------------------------------
    partye = bou_partye(kandidate)
    rye = bou_kandidaat_rye(kandidate, partye)
    konteks["partye"] = partye
    konteks["rye"] = rye

    # --- 4. hekke (voor enige skryf) ----------------------------------------------------
    begin = time.monotonic()
    foute.extend(kontroleer_id_skans(rye, partye))
    foute.extend(valideer_struktuur(rye, partye))
    munis: dict | None = None
    wyke: dict | None = None
    if modus != "net-ontleed":
        try:
            munis, wyke = lees_verwysings()
        except Exception as fout:  # SupabaseFout / OmgewingFout / httpx — message never carries headers
            foute.append(f"kon nie stg_munisipaliteite/stg_wyke lees nie: {type(fout).__name__}: {str(fout)[:300]}")
        else:
            konteks["munis"] = munis
            foute.extend(valideer_verwysings(rye, munis, wyke))
    konteks["waarskuwings"] = waarskuwings(rye, partye, munis, wyke)
    konteks["valideertyd"] = time.monotonic() - begin
    if foute:
        return klaar(1)

    if modus != "laai":
        konteks["skryf_status"] = f"NIKS GESKRYF NIE ({modus})"
        return klaar(0)

    # --- 5. skryf -------------------------------------------------------------------------
    begin = time.monotonic()
    try:
        skryf_stg(partye, rye)
    except Exception as fout:
        konteks["skryftyd"] = time.monotonic() - begin
        konteks["skryf_status"] = (
            "SKRYF HET MISLUK — stg_partye/stg_kandidate kan leeg of gedeeltelik wees; "
            "moenie publiseer nie, herlaai"
        )
        foute.append(f"skryf: {type(fout).__name__}: {str(fout)[:300]}")
        return klaar(1)
    konteks["skryftyd"] = time.monotonic() - begin
    konteks["skryf_status"] = (
        f"GESKRYF: stg_partye {getal(len(partye))}, stg_kandidate {getal(len(rye))} (tellings en nie-nul id's ná laai bevestig)"
    )
    return klaar(0)


if __name__ == "__main__":
    raise SystemExit(hoof())
