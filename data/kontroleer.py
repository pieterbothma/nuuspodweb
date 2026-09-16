"""Task 8: combined check report for Verkiesing Fase 2a.

Reads every stg_ table loaded by Tasks 1-7 (plus the currently-published public
tables, for the §5.3 diff) via PostgREST, runs the ward self-test
(`rpc/kontroleer_wyke`) and the §5.3/§8 place-search smoke tests, and writes one
combined `data/uitvoer/kontroleverslag.md` so Piet can say "publiseer".

Read-only: this script never writes to Supabase. There is no search RPC yet (that's
Fase 2b), so the smoke tests are implemented as plain REST lookups: resolve a name
through `stg_plek_aliasse` first (exact match), else `stg_plekke.naam_soek` (prefix
match), then `stg_plek_wyke` for the resulting ward count. The `authenticator` role's
8s `statement_timeout` means any of those calls can time out; a timeout is recorded
as a failed smoke test, not raised — one slow name must never crash the whole report.

Every *gathering* section (wards, municipalities, stations, places, 2021 seats, the
"not yet loaded" tables, the published-version diff, the 4 rural places) is wrapped
in `veilig()`: a `SupabaseFout`/`httpx.HTTPError` there is recorded in `hard_gefaal`
and rendered inline as "kon nie gekontroleer word nie: <kort fout>" for that section
only — it never stops the rest of the report from being gathered, and the report is
always written, even when `hoof()` ultimately returns 1. The error text is always
`SupabaseFout`'s own message (the response body, truncated, never headers) or
`str(httpx.HTTPError)` (which httpx never populates with request headers), so it
never carries the secret key.

Fase 2b (Task 10) adds a candidate section (counts vs the OVK's published totals, per
province, unknown wards, duplicates, empty names, ID-shaped fields, wards without a
ward candidate) with hard gates that apply only once stg_kandidate has rows, and turns
the published-version section into a real diff of every stg_ table against its public
table (DIFF_SPEK). Candidate checks reuse `laai_kandidate`'s own helpers.

Run: cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest python kontroleer.py
"""

from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

import httpx

import laai_kandidate as lk
from lib import omgewing, supabase, teks

BASIS_PAD = Path(__file__).parent
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "kontroleverslag.md"
ALIASSE_CSV_PAD = BASIS_PAD / "aliasse.csv"

VERWAG_WYKE = 4488  # official IEC total (reported, not gated — the MDB file lacks 3 FS wards)
VERWAG_VRYSTAAT_WYKE = 311

# --- Hard gates (exit 1 when any fails; the report is still written) ---------------
VERWAG_WYKE_GELAAI = 4485  # every ward in MDBWards2026, NC451 recovered
VERWAG_MUNISIPALITEITE = 213  # 8 metros + 205 locals
VERWAG_DISTRIKTE = 44
VERWAG_RADE_2021 = 213  # rows in stg_raad_grootte_2021
MAKS_STASIES_MET_ONBEKENDE_WYK = 0
MAKS_PLEKKE_SONDER_WYK = 3
# The only places allowed to have no ward: harbour slivers entirely in the sea.
BEKENDE_HAWE_SP_KODES = frozenset({"199056003", "199057014", "199063016"})

# Publish diff: every public table against its stg_ twin, as {table: (natural key,
# compared columns)}. Geometry is not compared (too heavy over REST; a geometry-only
# change shows as "in pas"), and plek_aliasse.id is left out because the public id is
# generated on publish. partye/kandidate ids ARE compared: the loader assigns them and
# publiseer_tabel keeps them.
DIFF_SPEK: dict[str, tuple[tuple[str, ...], str]] = {
    "munisipaliteite": (("kode",), "kode,naam,tipe,distrik_kode,provinsie"),
    "wyke": (("wyk_id",), "wyk_id,wyk_nr,muni_kode"),
    "stemstasies": (
        ("vd_nommer",),
        "vd_nommer,naam,naam_soek,adres,adres_soek,wyk_id,muni_kode,bron_lêer,bron_ry",
    ),
    "plekke": (("sp_kode",), "sp_kode,naam,naam_soek,mp_naam,mp_naam_soek,landelik"),
    "plek_wyke": (("sp_kode", "wyk_id"), "sp_kode,wyk_id,oorvleueling"),
    "plek_aliasse": (("alias", "sp_kode"), "alias,sp_kode,muni_kode"),
    "raad_uitslae_2021": (("muni_kode", "party_naam"), "muni_kode,party_naam,setels_wyk,setels_pv,setels_totaal"),
    "raad_grootte_2021": (("muni_kode",), "muni_kode,raadsgrootte_totaal,onafhanklike_setels"),
    "partye": (("id",), "id,naam,afkorting"),
    "kandidate": (
        ("id",),
        "id,muni_kode,stembrief,wyk_id,lys_posisie,party_id,onafhanklik,volle_naam,van,bron_lêer,bron_ry",
    ),
    "stembrief_volgorde": (("muni_kode", "stembrief", "party_id"), "muni_kode,stembrief,party_id,posisie"),
    "wyk_2021_opsomming": (
        ("wyk_id",),
        "wyk_id,wyk_id_2021,wyk_nr_2021,geregistreer,geldige_stemme,bedorwe_stemme,stemdistrikte",
    ),
    "wyk_uitslae_2021": (("wyk_id", "party_naam"), "wyk_id,party_naam,stemme"),
}
PUBLIEKE_TABELLE = tuple(DIFF_SPEK)

# Candidates: list wards without a ward candidate individually only when there are few.
MAKS_WYKE_SONDER_KANDIDAAT_LYS = 50

# Besluite-item #3: die 4 groot plattelandse plekke wat selfs een-op-'n-slag oor
# PostgREST se 8s statement_timeout val (Task 5) — sp_kode's direk gegee (soos die
# fix-round-1-opdrag toelaat), nie deur naam opgesoek nie. Kommentaar dra die brief
# se spelling ter vergelyking met die bronshapefile s'n.
LANDELIKE_PLEK_KODES: tuple[str, ...] = (
    "271002001",  # brief: "Mnquma" — die bronshapefile self spel dit "Mnquna"
    "290003001",  # Ngquza Hill
    "292002001",  # Nyandeni
    "966002001",  # Thulamela
)

# Aliases removed from aliasse.csv in the final-review fix round because no single
# Stats SA name/main place is the right target — each needs a curated sub-place list,
# which is an owner decision for Fase 2b. Listed under "Besluite nodig".
ALIASSE_WAT_KURERING_NODIG: tuple[tuple[str, str], ...] = (
    ("Johannesburg-Suid", "pas op geen Stats SA-subplek of hoofplek nie"),
    ("Kaapse Vlakte", "pas op geen Stats SA-subplek of hoofplek nie"),
    ("Pretoria-Oos", "die enigste beskikbare teiken was die hele hoofplek Pretoria (173 subplekke)"),
)

# Spec §5.3 (line 112) se vyf name eerste — Brooklyn en Waterkloof is die bekende
# veelvuldige-munisipaliteit-botsings (spec §8: Brooklyn moet >=2 munisipaliteite
# insluitend Tshwane en Kaapstad gee, Waterkloof moet Tshwane insluit) — dan die
# ekstra name hierdie taak self bygevoeg het (groot metro's, 'n hoofstad, 'n dorpie,
# en doelbewus die huidige amptelike spelling "Mahikeng" om te kyk of die bron dit
# ken — dit ken nie, sien §Smoke-toetse in die verslag).
SMOKE_NAME = (
    "Brooklyn",
    "Waterkloof",
    "Stellenbosch",
    "Kaapstad",
    "Moreleta Park",
    "Strand",
    "Soweto",
    "Bloemfontein",
    "Mahikeng",
    "Riebeek-Kasteel",
)


# ---------------------------------------------------------------------------------
# Pure helpers (network-free — covered by data/tests/test_kontroleer.py)
# ---------------------------------------------------------------------------------


def ontleed_inhoud_reeks(header: str) -> int:
    """Parse a PostgREST `Content-Range` header to its total count.

    PostgREST prints e.g. "0-0/4485" when the (filtered) result has rows, or "*/0"
    when it's empty — both end in "/<totaal>", which is all this needs.
    """
    return int(header.rsplit("/", 1)[-1])


def bereken_geen_meerderheid(uitslae: list[dict], raadsgroottes: dict[str, dict]) -> list[dict]:
    """Councils where no party holds a strict majority of the *full* council.

    "Full council" is `raadsgrootte_totaal` from `stg_raad_grootte_2021` (party seats
    + independent ward councillors), not the sum of party seats in `uitslae` — a
    council with independents can look like it has no majority-holder by the party
    sum alone when it actually does, or vice versa. Returns one entry per such
    council, sorted by muni_kode: {muni_kode, raadsgrootte_totaal, grootste_party,
    setels}.
    """
    grootste_party: dict[str, tuple[str, int]] = {}
    for ry in uitslae:
        mk = ry["muni_kode"]
        huidige = grootste_party.get(mk)
        if huidige is None or ry["setels_totaal"] > huidige[1]:
            grootste_party[mk] = (ry["party_naam"], ry["setels_totaal"])

    geen_meerderheid = []
    for mk, grootte in raadsgroottes.items():
        totaal = grootte["raadsgrootte_totaal"]
        party, setels = grootste_party.get(mk, (None, 0))
        if setels <= totaal / 2:
            geen_meerderheid.append(
                {
                    "muni_kode": mk,
                    "raadsgrootte_totaal": totaal,
                    "grootste_party": party,
                    "setels": setels,
                }
            )
    geen_meerderheid.sort(key=lambda r: r["muni_kode"])
    return geen_meerderheid


def tel_per_sleutel(waardes: list[str], opsoek: dict[str, str]) -> dict[str, int]:
    """Count `waardes` (e.g. muni_kode per row) grouped by `opsoek[waarde]` (e.g.
    muni_kode -> provinsie), sorted by key. Unmapped values fall under "ONBEKEND".
    """
    telling = Counter(opsoek.get(w, "ONBEKEND") for w in waardes)
    return dict(sorted(telling.items()))


def vind_ontbrekende(alles: set[str], teenwoordig: set[str]) -> list[str]:
    """`alles - teenwoordig`, sorted — used for both "wyke sonder geom" style diffs
    and "plekke sonder wyk"."""
    return sorted(alles - teenwoordig)


def formatteer_telling_reël(etiket: str, gekry: int, verwag: int | None = None) -> str:
    """One Markdown bullet: "- {etiket}: **{gekry}**" (+ " (verwag {verwag})" when a
    mismatch matters)."""
    if verwag is None or gekry == verwag:
        return f"- {etiket}: **{gekry}**" + ("" if verwag is None else f" (verwag {verwag})")
    return f"- {etiket}: **{gekry}** (verwag {verwag}, verskil {gekry - verwag})"


def formatteer_afdeling_fout(sectie: str, sectie_foute: dict[str, str]) -> str | None:
    """The one line to render instead of `sectie`'s normal content when it failed to
    gather: "kon nie gekontroleer word nie: <kort fout>". Returns None when `sectie`
    isn't in `sectie_foute` (i.e. it succeeded), so callers render normally."""
    if sectie not in sectie_foute:
        return None
    return f"kon nie gekontroleer word nie: {sectie_foute[sectie]}"


def kontroleer_veelvuldige_munisipaliteite(
    munisipaliteite: list[str], moet_bevat: tuple[str, ...], min_aantal: int = 1
) -> str | None:
    """Spec §8's Brooklyn/Waterkloof expectation, generalised: `munisipaliteite`
    (already-resolved names) must number at least `min_aantal` and include a name
    containing each substring in `moet_bevat`. Returns None when satisfied, else a
    short Afrikaans description of what's missing (never raises — a failed
    expectation is data for the report, not an exception)."""
    ontbrekend = []
    if len(munisipaliteite) < min_aantal:
        ontbrekend.append(f"minder as {min_aantal} munisipaliteit(e) ({len(munisipaliteite)})")
    for stuk in moet_bevat:
        if not any(stuk in m for m in munisipaliteite):
            ontbrekend.append(f"geen '{stuk}' nie")
    return "; ".join(ontbrekend) if ontbrekend else None


def lees_alias_name(pad: Path) -> list[str]:
    """Alias names from `aliasse.csv`, in file order (duplicates collapsed)."""
    with pad.open(newline="", encoding="utf-8") as f:
        return list(dict.fromkeys(ry["alias"] for ry in csv.DictReader(f)))


def bou_alias_opsomming(
    csv_aliasse: list[str],
    alias_rye: list[dict],
    plek_wyke_rye: list[dict],
    wyk_muni: dict[str, str],
    muni_naam: dict[str, str],
) -> dict[str, dict]:
    """Per alias: how many sub places it resolves to in stg_plek_aliasse, and the
    municipalities those sub places fall in (via stg_plek_wyke -> stg_wyke.muni_kode).

    Every alias in `csv_aliasse` gets an entry even when it has no rows (subplekke=0),
    so a CSV alias that resolved to nothing is visible and can be gated on. Aliases
    present in the table but not in the CSV are included too (stale load). Sorted by
    alias. Municipality names fall back to the code when unknown.
    """
    sp_per_alias: dict[str, set[str]] = defaultdict(set)
    for ry in alias_rye:
        sp_per_alias[ry["alias"]].add(ry["sp_kode"])

    wyke_per_sp: dict[str, set[str]] = defaultdict(set)
    for ry in plek_wyke_rye:
        wyke_per_sp[ry["sp_kode"]].add(ry["wyk_id"])

    opsomming: dict[str, dict] = {}
    for alias in sorted(set(csv_aliasse) | set(sp_per_alias)):
        sp_kodes = sp_per_alias.get(alias, set())
        munikodes = {wyk_muni[w] for sp in sp_kodes for w in wyke_per_sp.get(sp, ()) if w in wyk_muni}
        opsomming[alias] = {
            "subplekke": len(sp_kodes),
            "munisipaliteite": sorted({muni_naam.get(k, k) for k in munikodes}),
            "in_csv": alias in csv_aliasse,
        }
    return opsomming


def vind_duplikate(waardes: list) -> list:
    """Values occurring more than once, sorted (by their string form)."""
    return sorted((w for w, n in Counter(waardes).items() if n > 1), key=str)


def evalueer_harde_hekke(
    muni_res: dict | None,
    wyke_res: dict | None,
    stasies_res: dict | None,
    plekke_res: dict | None,
    raad_res: dict | None,
) -> list[str]:
    """Every hard-gate failure as a short Afrikaans message (empty list = all pass).

    A section that is None failed to gather — `veilig()` has already recorded that in
    hard_gefaal, so it is skipped here rather than double-reported.
    """
    foute: list[str] = []

    if muni_res is not None:
        munis = muni_res["metro"] + muni_res["plaaslik"]
        if munis != VERWAG_MUNISIPALITEITE:
            foute.append(f"munisipaliteite: {munis}, verwag {VERWAG_MUNISIPALITEITE}")
        if muni_res["distrik"] != VERWAG_DISTRIKTE:
            foute.append(f"distrikte: {muni_res['distrik']}, verwag {VERWAG_DISTRIKTE}")
        duplikate = vind_duplikate(muni_res["kodes"])
        if duplikate:
            foute.append(f"stg_munisipaliteite: duplikaat kode(s) {duplikate[:20]}")

    if wyke_res is not None:
        if wyke_res["totaal"] != VERWAG_WYKE_GELAAI:
            foute.append(f"wyke: {wyke_res['totaal']}, verwag {VERWAG_WYKE_GELAAI}")
        duplikate = vind_duplikate(wyke_res["wyk_ids"])
        if duplikate:
            foute.append(f"stg_wyke: duplikaat wyk_id(s) {duplikate[:20]}")

    if stasies_res is not None:
        if stasies_res["totaal"] == 0:
            foute.append("stg_stemstasies is leeg")
        onbekend = stasies_res["onbekende_wyk"]
        if len(onbekend) > MAKS_STASIES_MET_ONBEKENDE_WYK:
            foute.append(f"stemlokale met onbekende wyk: {len(onbekend)} wyk_id(s) {onbekend[:20]}")
        duplikate = vind_duplikate(stasies_res["vd_nommers"])
        if duplikate:
            foute.append(f"stg_stemstasies: duplikaat vd_nommer(s) {duplikate[:20]}")

    if plekke_res is not None:
        if plekke_res["totaal"] == 0:
            foute.append("stg_plekke is leeg")
        if plekke_res["plek_wyke_totaal"] == 0:
            foute.append("stg_plek_wyke is leeg")
        if plekke_res["alias_totaal"] == 0:
            foute.append("stg_plek_aliasse is leeg")
        sonder_wyk = {p["sp_kode"] for p in plekke_res["sonder_wyk"]}
        if len(sonder_wyk) > MAKS_PLEKKE_SONDER_WYK or sonder_wyk != BEKENDE_HAWE_SP_KODES:
            foute.append(
                f"plekke sonder wyk: {sorted(sonder_wyk)[:20]} ({len(sonder_wyk)}), verwag presies "
                f"die {len(BEKENDE_HAWE_SP_KODES)} hawe-snippers {sorted(BEKENDE_HAWE_SP_KODES)}"
            )
        duplikate = vind_duplikate(plekke_res["sp_kodes"])
        if duplikate:
            foute.append(f"stg_plekke: duplikaat sp_kode(s) {duplikate[:20]}")
        duplikate = vind_duplikate(plekke_res["plek_wyk_pare"])
        if duplikate:
            foute.append(f"stg_plek_wyke: duplikaat (sp_kode, wyk_id)-pare {duplikate[:20]}")
        leeg = [a for a, inl in plekke_res["alias_opsomming"].items() if inl["in_csv"] and inl["subplekke"] == 0]
        if leeg:
            foute.append(f"aliasse wat na 0 subplekke oplos: {leeg}")

    if raad_res is not None:
        if raad_res["uitslae_totaal"] == 0:
            foute.append("stg_raad_uitslae_2021 is leeg")
        if raad_res["grootte_totaal"] != VERWAG_RADE_2021:
            foute.append(f"rade (stg_raad_grootte_2021): {raad_res['grootte_totaal']}, verwag {VERWAG_RADE_2021}")

    return foute


def ontleed_kandidate(
    rye: list[dict], partye: list[dict], wyk_muni: dict[str, str], muni_provinsie: dict[str, str]
) -> dict:
    """Candidate checks over rows read back from stg_kandidate / stg_partye (pure).

    Reuses the loader's own counting, duplicate key and personal-data guard, so the
    report and the loader can never disagree about what a duplicate or an ID-shaped
    field is.
    """
    tellings = lk.tel_stembriewe(rye)
    onbekende_wyk = sorted({r["wyk_id"] for r in rye if r.get("wyk_id") and r["wyk_id"] not in wyk_muni})
    met_kandidaat = {r["wyk_id"] for r in rye if r.get("stembrief") == "wyk" and r.get("wyk_id")}
    wyke_sonder: dict[str, list[str]] = defaultdict(list)
    for wyk_id in sorted(set(wyk_muni) - met_kandidaat):
        wyke_sonder[wyk_muni[wyk_id]].append(wyk_id)
    return {
        "gelaai": True,
        "totaal": len(rye),
        "partye_totaal": len(partye),
        "tellings": tellings,
        "per_provinsie": lk.per_groep(rye, lambda r: muni_provinsie.get(r.get("muni_kode"), "ONBEKEND")),
        "onbekende_wyk": onbekende_wyk,
        "duplikate": len(lk.vind_duplikate(rye)),
        "leë_name": sum(1 for r in rye if not (r.get("volle_naam") or "").strip() or not (r.get("van") or "").strip()),
        "id_vorm": lk.kontroleer_id_skans(rye, partye),
        "id_foute": lk.kontroleer_ids(rye, "stg_kandidate") + lk.kontroleer_ids(partye, "stg_partye"),
        "wyke_sonder_kandidaat": dict(sorted(wyke_sonder.items())),
        "iec_besluite": lk.vergelyk_met_iec(tellings),
    }


def evalueer_kandidaat_hekke(res: dict | None) -> list[str]:
    """Candidate hard gates. Not loaded (or failed to gather — already in hard_gefaal
    via veilig()) is never a failure. A total that differs from the OVK's figures is a
    decision in the report, not a gate."""
    if not res or not res.get("gelaai"):
        return []
    foute: list[str] = []
    if res["onbekende_wyk"]:
        foute.append(
            f"kandidate: {len(res['onbekende_wyk'])} wyk_id(s) nie in stg_wyke nie {res['onbekende_wyk'][:20]}"
        )
    if res["id_vorm"]:
        foute.append(f"kandidate: {len(res['id_vorm'])} ID-vormige veld(e) (moet 0 wees) — sien die kandidaat-afdeling")
    if res["duplikate"]:
        foute.append(f"kandidate: {res['duplikate']} duplikaatgroep(e)")
    # Rows without a name are kept as the OVK published them (Piet, 2026-09-16) and only
    # counted in the report; the site shows a "no name in the list" placeholder.
    foute.extend(f"kandidate: {f}" for f in res["id_foute"])
    if res["partye_totaal"] == 0:
        foute.append("kandidate gelaai maar stg_partye is leeg")
    return foute


def formatteer_kandidaat_afdeling(res: dict | None, sectie_foute: dict[str, str]) -> list[str]:
    """Markdown lines for the candidate section (pure)."""
    fout = formatteer_afdeling_fout("kandidate", sectie_foute)
    if fout:
        return [f"- {fout}"]
    if not res or not res.get("gelaai"):
        partye = (res or {}).get("partye_totaal", 0)
        return [
            "- stg_kandidate: **nog nie gelaai nie** (0 rye) — geen kandidaat-hek is van toepassing nie.",
            f"- stg_partye: {partye} rye" + ("" if partye == 0 else " (ONVERWAGS: partye sonder kandidate)"),
        ]

    t = res["tellings"]
    g = lk.getal
    r: list[str] = [
        f"- stg_kandidate: **{g(res['totaal'])}** rye; stg_partye: **{g(res['partye_totaal'])}**; "
        f"onafhanklikes: **{g(t['wyk_onafhanklik'])}**",
        "",
        "| Stembrief | Gelaai | OVK | Verskil |",
        "|---|---:|---:|---:|",
        f"| wyk (party) | {g(t['wyk_party'])} | {g(lk.IEC_WYK_PARTY)} | {g(t['wyk_party'] - lk.IEC_WYK_PARTY)} |",
        f"| wyk (onafhanklik) | {g(t['wyk_onafhanklik'])} | {g(lk.IEC_WYK_ONAFHANKLIK)} | "
        f"{g(t['wyk_onafhanklik'] - lk.IEC_WYK_ONAFHANKLIK)} |",
        f"| PV (pv_plaaslik {g(t['pv_plaaslik'])} + pv_distrik {g(t['pv_distrik'])}) | {g(t['pv'])} | "
        f"{g(lk.IEC_PV)} | {g(t['pv'] - lk.IEC_PV)} |",
        f"| **totaal** | **{g(t['totaal'])}** | **{g(lk.IEC_TOTAAL)}** | {g(t['totaal'] - lk.IEC_TOTAAL)} |",
        "",
    ]
    if res["iec_besluite"]:
        r.append(
            f"**Besluit nodig** (geen outomatiese fout nie — die OVK korrigeer tot {lk.IEC_REGSTELLING_TOT}): "
            + "; ".join(res["iec_besluite"])
        )
    else:
        r.append("Presies gelyk aan die OVK se gepubliseerde totale.")
    r.append("")
    r.append("### Kandidate per provinsie")
    r.append("| Provinsie | wyk (party) | onafhanklik | pv_plaaslik | pv_distrik | totaal |")
    r.append("|---|---:|---:|---:|---:|---:|")
    for prov, pt in res["per_provinsie"].items():
        r.append(
            f"| {prov} | {g(pt['wyk_party'])} | {g(pt['wyk_onafhanklik'])} | {g(pt['pv_plaaslik'])} | "
            f"{g(pt['pv_distrik'])} | {g(pt['totaal'])} |"
        )
    r.append("")
    r.append("### Kandidaat-hekke")
    r.append(f"- wyk_id nie in stg_wyke nie: **{len(res['onbekende_wyk'])}**")
    for wyk_id in res["onbekende_wyk"][:50]:
        r.append(f"  - `{wyk_id}`")
    r.append(f"- duplikaatgroepe (muni_kode, stembrief, wyk_id, lys_posisie, volle_naam, van, party_id): **{res['duplikate']}**")
    r.append(f"- sonder naam of van in die OVK-lys (behou, plekhouer op die werf): **{res['leë_name']}**")
    r.append(f"- ID-vormige velde (6+-syferreeks, wyk_id nie 8 syfers, ens.; moet 0 wees): **{len(res['id_vorm'])}**")
    for f in res["id_vorm"][:20]:
        r.append(f"  - {f}")
    r.append(f"- nul/duplikaat id's: **{len(res['id_foute'])}**")
    for f in res["id_foute"]:
        r.append(f"  - {f}")
    r.append("")
    sonder = res["wyke_sonder_kandidaat"]
    totaal_sonder = sum(len(v) for v in sonder.values())
    r.append(f"### Wyke sonder 'n wykkandidaat: {g(totaal_sonder)}")
    if totaal_sonder and totaal_sonder <= MAKS_WYKE_SONDER_KANDIDAAT_LYS:
        for muni, wyke in sonder.items():
            r.append(f"- {muni}: " + ", ".join(f"`{w}`" for w in wyke))
    elif totaal_sonder:
        r.append("Te veel om te lys — per munisipaliteit: " + ", ".join(f"{m} ({len(w)})" for m, w in sonder.items()))
    return r


def formatteer_nie_gelaai(ng: dict) -> list[str]:
    """The "not yet loaded" lines: candidates drop out once loaded; ballot order stays
    listed until it is loaded (OVK ballot draw, 23 Sep)."""
    r: list[str] = []
    if ng["kandidate_totaal"] == 0:
        r.append("- stg_kandidate: 0 rye (soos verwag tot die OVK die finale lys publiseer — `laai_kandidate.py`)")
    if ng["stembrief_volgorde_totaal"] == 0:
        r.append("- stg_stembrief_volgorde: 0 rye (soos verwag tot die stembrieftrekking op 23 Sep)")
    else:
        r.append(f"- stg_stembrief_volgorde: {ng['stembrief_volgorde_totaal']} rye — gelaai (volgorde 23 Sep)")
    return r


def vergelyk_tabelle(stg_rye: list[dict], publieke_rye: list[dict], sleutel: tuple[str, ...]) -> dict:
    """Rows added / removed / changed between a stg_ table and its public table, matched
    on the natural `sleutel` (pure). Up to 5 example keys per kind."""

    def k(ry: dict) -> str:
        return "|".join(str(ry.get(s)) for s in sleutel)

    stg = {k(r): r for r in stg_rye}
    pub = {k(r): r for r in publieke_rye}
    toegevoeg = sorted(set(stg) - set(pub))
    verwyder = sorted(set(pub) - set(stg))
    verander = sorted(x for x in set(stg) & set(pub) if stg[x] != pub[x])
    # A duplicate natural key on either side would hide rows; count it as a change.
    dubbel = (len(stg_rye) - len(stg)) + (len(publieke_rye) - len(pub))
    return {
        "stg": len(stg_rye),
        "publiek": len(publieke_rye),
        "toegevoeg": len(toegevoeg),
        "verwyder": len(verwyder),
        "verander": len(verander) + dubbel,
        "gelyk": not (toegevoeg or verwyder or verander or dubbel),
        "voorbeelde": {"toegevoeg": toegevoeg[:5], "verwyder": verwyder[:5], "verander": verander[:5]},
    }


def formatteer_landelike_plekke(per_plek: dict[str, dict]) -> str:
    """"Naam (n), Naam (n), ... = totaal rye" for Besluite-item #3 — measured live
    from stg_plek_wyke, not a static "34+32+32+58=156"."""
    dele = [f"{p['naam_in_bron']} ({p['wyktal']})" for p in per_plek.values()]
    totaal = sum(p["wyktal"] for p in per_plek.values())
    return ", ".join(dele) + f" = {totaal} rye"


# ---------------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------------


def _bou_klient() -> httpx.Client:
    """Own httpx.Client (mirrors `lib.supabase._bou_klient`) rather than changing
    `lib/supabase.py` — this task only needs plain GETs with a `Prefer: count=exact`
    header, which that module doesn't expose, and that file is out of scope here
    (same pattern `laai_plekke.py` uses for its own REST DELETE)."""
    omgewing_waardes = omgewing.lees()
    basis_url = omgewing_waardes["url"].rstrip("/") + "/rest/v1/"
    koptekste = {
        "apikey": omgewing_waardes["sleutel"],
        "Authorization": f"Bearer {omgewing_waardes['sleutel']}",
    }
    return httpx.Client(base_url=basis_url, headers=koptekste, timeout=30.0)


def veilig(hard_gefaal: list[str], sectie_foute: dict[str, str], sectie: str, funksie: Callable[[], dict]):
    """Run a zero-arg gathering `funksie` for `sectie`; on `SupabaseFout` or
    `httpx.HTTPError`, record a short message (never headers or the key —
    `SupabaseFout`'s message is already the truncated response body, and httpx never
    puts headers in its exception text) in both `hard_gefaal` and `sectie_foute`, and
    return None instead of letting the exception propagate.

    This is what makes one failing PostgREST call affect only its own section of the
    report rather than aborting `skryf_verslag()` for everything — the CRITICAL fix
    from Task 8 review round 1.
    """
    try:
        return funksie()
    except (supabase.SupabaseFout, httpx.HTTPError) as fout:
        boodskap = str(fout)[:500]
        hard_gefaal.append(f"{sectie}: {boodskap}")
        sectie_foute[sectie] = boodskap
        return None


def telling(klient: httpx.Client, tabel: str, parameters: dict[str, str] | None = None) -> int:
    """GET tabel (optioneel gefiltreer) met `Prefer: count=exact`, `Range: 0-0` —
    gee net die totaal terug (nooit die rye self nie, vinnig selfs vir groot tabelle).
    """
    resp = klient.get(
        tabel,
        params=dict(parameters or {}),
        headers={"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"},
    )
    if resp.status_code >= 400:
        raise supabase.SupabaseFout(resp.text[:500])
    return ontleed_inhoud_reeks(resp.headers.get("content-range", "*/0"))


def smoke_toets_plek(
    klient: httpx.Client, naam: str, muni_naam: dict[str, str], tydsuit_s: float = 7.5
) -> dict:
    """Resolve `naam` -> ward count and resolved municipalities.

    Volgorde: (1) `stg_plek_aliasse` presiese (case-insensitive) treffer, anders
    (2) `stg_plekke.naam_soek` voorvoegsel-treffer; dan altyd `stg_plek_wyke` vir die
    wyktal, en (as daar wyke is) `stg_wyke` vir die munisipaliteite waaraan daardie
    wyke behoort — spec §8 verwag Brooklyn/Waterkloof oor >1 munisipaliteit uit te
    wys, dus moet die verslag dit kan wys. 'n Tydverstreke of PostgREST-fout op enige
    stap word as 'n gefaalde steekproef aangeteken, nie 'n uitsondering nie — een
    stadige naam mag nooit die hele verslag laat val nie.
    """
    naam_soek = teks.normaliseer(naam)
    try:
        alias_resp = klient.get(
            "stg_plek_aliasse",
            params={"select": "sp_kode", "alias": f"ilike.{naam}"},
            timeout=tydsuit_s,
        )
        if alias_resp.status_code >= 400:
            return {"naam": naam, "gevind": False, "fout": alias_resp.text[:200]}
        sp_kodes = [r["sp_kode"] for r in alias_resp.json()]
        bron = "alias" if sp_kodes else None

        if not sp_kodes:
            plek_resp = klient.get(
                "stg_plekke",
                params={"select": "sp_kode", "naam_soek": f"ilike.{naam_soek}%"},
                timeout=tydsuit_s,
            )
            if plek_resp.status_code >= 400:
                return {"naam": naam, "gevind": False, "fout": plek_resp.text[:200]}
            sp_kodes = [r["sp_kode"] for r in plek_resp.json()]
            bron = "naam" if sp_kodes else None

        if not sp_kodes:
            return {
                "naam": naam,
                "gevind": False,
                "plekke": 0,
                "wyke": 0,
                "munisipaliteite": [],
                "bron": None,
            }

        lys = ",".join(sp_kodes)
        wyk_resp = klient.get(
            "stg_plek_wyke",
            params={"select": "wyk_id", "sp_kode": f"in.({lys})"},
            timeout=tydsuit_s,
        )
        if wyk_resp.status_code >= 400:
            return {
                "naam": naam,
                "gevind": True,
                "plekke": len(sp_kodes),
                "bron": bron,
                "fout": wyk_resp.text[:200],
            }
        wyke = {r["wyk_id"] for r in wyk_resp.json()}

        munisipaliteite: list[str] = []
        if wyke:
            lys_w = ",".join(wyke)
            muni_resp = klient.get(
                "stg_wyke",
                params={"select": "muni_kode", "wyk_id": f"in.({lys_w})"},
                timeout=tydsuit_s,
            )
            if muni_resp.status_code < 400:
                munikodes = {r["muni_kode"] for r in muni_resp.json()}
                munisipaliteite = sorted({muni_naam.get(k, k) for k in munikodes})

        return {
            "naam": naam,
            "gevind": True,
            "plekke": len(sp_kodes),
            "wyke": len(wyke),
            "munisipaliteite": munisipaliteite,
            "bron": bron,
        }
    except httpx.HTTPError:
        return {"naam": naam, "gevind": False, "fout": f"PostgREST-tydverstreke/fout (> {tydsuit_s}s)"}


# ---------------------------------------------------------------------------------
# Gathering (each of these runs entirely inside one `veilig()` call in hoof())
# ---------------------------------------------------------------------------------


def gather_munisipaliteite(klient: httpx.Client) -> dict:
    metro = telling(klient, "stg_munisipaliteite", {"tipe": "eq.metro"})
    plaaslik = telling(klient, "stg_munisipaliteite", {"tipe": "eq.plaaslik"})
    distrik = telling(klient, "stg_munisipaliteite", {"tipe": "eq.distrik"})
    munis = supabase.kry_alles("stg_munisipaliteite", {"select": "kode,naam,provinsie"}, orde="kode", klient=klient)
    return {
        "metro": metro,
        "plaaslik": plaaslik,
        "distrik": distrik,
        "muni_provinsie": {m["kode"]: m["provinsie"] for m in munis},
        "muni_naam": {m["kode"]: m["naam"] for m in munis},
        "kodes": [m["kode"] for m in munis],
    }


def gather_wyke(klient: httpx.Client, muni_provinsie: dict[str, str]) -> dict:
    totaal = telling(klient, "stg_wyke")
    sonder_geom_totaal = telling(klient, "stg_wyke", {"geom": "is.null"})
    sonder_geom_lys: list[str] = []
    if sonder_geom_totaal:
        resp = klient.get("stg_wyke", params={"select": "wyk_id", "geom": "is.null"})
        if resp.status_code >= 400:
            raise supabase.SupabaseFout(resp.text[:500])
        sonder_geom_lys = [r["wyk_id"] for r in resp.json()]

    wyk_munis = supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"}, orde="wyk_id", klient=klient)
    per_provinsie = tel_per_sleutel([w["muni_kode"] for w in wyk_munis], muni_provinsie)

    return {
        "totaal": totaal,
        "sonder_geom_totaal": sonder_geom_totaal,
        "sonder_geom_lys": sonder_geom_lys,
        "per_provinsie": per_provinsie,
        "wyk_ids": [w["wyk_id"] for w in wyk_munis],
    }


def gather_wyk_selftoets(klient: httpx.Client) -> dict:
    rye = supabase.rpc("kontroleer_wyke", {}, klient=klient)
    return rye[0] if isinstance(rye, list) else rye


def gather_stemstasies(klient: httpx.Client, muni_provinsie: dict[str, str]) -> dict:
    totaal = telling(klient, "stg_stemstasies")
    stasies = supabase.kry_alles(
        "stg_stemstasies", {"select": "vd_nommer,muni_kode,wyk_id"}, orde="vd_nommer", klient=klient
    )
    per_provinsie = tel_per_sleutel([r["muni_kode"] for r in stasies], muni_provinsie)

    wyk_ids = {r["wyk_id"] for r in supabase.kry_alles("stg_wyke", {"select": "wyk_id"}, orde="wyk_id", klient=klient)}
    stasie_wyk_ids = {r["wyk_id"] for r in stasies}
    onbekende_wyk = vind_ontbrekende(stasie_wyk_ids, wyk_ids)

    leë_adres_resp = klient.get(
        "stg_stemstasies",
        params={"select": "vd_nommer,naam,adres,muni_kode,wyk_id", "adres": "eq."},
    )
    if leë_adres_resp.status_code >= 400:
        raise supabase.SupabaseFout(leë_adres_resp.text[:500])

    return {
        "totaal": totaal,
        "per_provinsie": per_provinsie,
        "onbekende_wyk": onbekende_wyk,
        "leë_adres": leë_adres_resp.json(),
        "vd_nommers": [r["vd_nommer"] for r in stasies],
    }


def gather_plekke(klient: httpx.Client, muni_naam: dict[str, str]) -> dict:
    totaal = telling(klient, "stg_plekke")
    plek_wyke_totaal = telling(klient, "stg_plek_wyke")
    alias_totaal = telling(klient, "stg_plek_aliasse")

    alle_plekke = supabase.kry_alles("stg_plekke", {"select": "sp_kode,naam,mp_naam"}, orde="sp_kode", klient=klient)
    plek_wyke_rye = supabase.kry_alles(
        "stg_plek_wyke", {"select": "sp_kode,wyk_id"}, orde="sp_kode,wyk_id", klient=klient
    )
    met_wyk = {r["sp_kode"] for r in plek_wyke_rye}
    by_kode = {r["sp_kode"]: r for r in alle_plekke}
    sonder_wyk = [by_kode[k] for k in vind_ontbrekende({r["sp_kode"] for r in alle_plekke}, met_wyk)]

    alias_rye = supabase.kry_alles(
        "stg_plek_aliasse", {"select": "alias,sp_kode"}, orde="alias,sp_kode", klient=klient
    )
    alias_tellings = dict(sorted(Counter(r["alias"] for r in alias_rye).items()))
    wyk_muni = {
        r["wyk_id"]: r["muni_kode"]
        for r in supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"}, orde="wyk_id", klient=klient)
    }
    alias_opsomming = bou_alias_opsomming(
        lees_alias_name(ALIASSE_CSV_PAD), alias_rye, plek_wyke_rye, wyk_muni, muni_naam
    )

    return {
        "totaal": totaal,
        "plek_wyke_totaal": plek_wyke_totaal,
        "alias_totaal": alias_totaal,
        "sonder_wyk": sonder_wyk,
        "alias_tellings": alias_tellings,
        "alias_opsomming": alias_opsomming,
        "sp_kodes": [r["sp_kode"] for r in alle_plekke],
        "plek_wyk_pare": [(r["sp_kode"], r["wyk_id"]) for r in plek_wyke_rye],
    }


def gather_raadsetels(klient: httpx.Client) -> dict:
    uitslae_totaal = telling(klient, "stg_raad_uitslae_2021")
    grootte_totaal = telling(klient, "stg_raad_grootte_2021")
    uitslae_rye = supabase.kry_alles(
        "stg_raad_uitslae_2021",
        {"select": "muni_kode,party_naam,setels_totaal"},
        orde="muni_kode,party_naam",
        klient=klient,
    )
    grootte_rye = supabase.kry_alles(
        "stg_raad_grootte_2021",
        {"select": "muni_kode,raadsgrootte_totaal,onafhanklike_setels"},
        orde="muni_kode",
        klient=klient,
    )
    grootte_by_kode = {r["muni_kode"]: r for r in grootte_rye}
    return {
        "uitslae_totaal": uitslae_totaal,
        "grootte_totaal": grootte_totaal,
        "geen_meerderheid": bereken_geen_meerderheid(uitslae_rye, grootte_by_kode),
    }


def gather_nie_gelaai(klient: httpx.Client) -> dict:
    return {
        "kandidate_totaal": telling(klient, "stg_kandidate"),
        "stembrief_volgorde_totaal": telling(klient, "stg_stembrief_volgorde"),
    }


def gather_kandidate(klient: httpx.Client, muni_provinsie: dict[str, str]) -> dict:
    """Candidate section. Reads the full rows only once candidates are loaded; the rows
    are handed back (`_rye`) so the publish diff need not read stg_kandidate twice."""
    totaal = telling(klient, "stg_kandidate")
    partye_totaal = telling(klient, "stg_partye")
    if totaal == 0:
        return {"gelaai": False, "totaal": 0, "partye_totaal": partye_totaal}
    rye = supabase.kry_alles(
        "stg_kandidate", {"select": DIFF_SPEK["kandidate"][1]}, orde="id,bron_lêer,bron_ry", klient=klient
    )
    partye = supabase.kry_alles("stg_partye", {"select": DIFF_SPEK["partye"][1]}, orde="naam", klient=klient)
    wyk_muni = {
        r["wyk_id"]: r["muni_kode"]
        for r in supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"}, orde="wyk_id", klient=klient)
    }
    res = ontleed_kandidate(rye, partye, wyk_muni, muni_provinsie)
    res["_rye"] = {"stg_kandidate": rye, "stg_partye": partye}
    return res


def gather_publieke_diff(klient: httpx.Client, voorafgelees: dict[str, list[dict]] | None = None) -> dict:
    """Compare every stg_ table with its public table (DIFF_SPEK). Two empty sides are
    counted, not read."""
    voorafgelees = voorafgelees or {}
    tabelle: dict[str, dict] = {}
    for tabel, (sleutel, kolomme) in DIFF_SPEK.items():
        stg_n = telling(klient, f"stg_{tabel}")
        pub_n = telling(klient, tabel)
        if stg_n == 0 and pub_n == 0:
            tabelle[tabel] = vergelyk_tabelle([], [], sleutel)
            continue
        orde = ",".join(sleutel)
        stg_rye = voorafgelees.get(f"stg_{tabel}")
        if stg_rye is None:
            stg_rye = supabase.kry_alles(f"stg_{tabel}", {"select": kolomme}, orde=orde, klient=klient) if stg_n else []
        pub_rye = supabase.kry_alles(tabel, {"select": kolomme}, orde=orde, klient=klient) if pub_n else []
        tabelle[tabel] = vergelyk_tabelle(stg_rye, pub_rye, sleutel)
    return {"tabelle": tabelle}


def gather_landelike_plekke(klient: httpx.Client) -> dict:
    """Live per-place ward-overlap counts for the 4 rural places (Besluite-item #3) —
    measured fresh every run from `stg_plek_wyke`, since a bare full `laai_plekke.py`
    reload wipes the direct-SQL fix (Task 5) and would otherwise leave this report
    quoting a stale static total."""
    lys = ",".join(LANDELIKE_PLEK_KODES)
    plek_resp = klient.get("stg_plekke", params={"select": "sp_kode,naam", "sp_kode": f"in.({lys})"})
    if plek_resp.status_code >= 400:
        raise supabase.SupabaseFout(plek_resp.text[:500])
    naam_by_kode = {r["sp_kode"]: r["naam"] for r in plek_resp.json()}

    wyk_resp = klient.get("stg_plek_wyke", params={"select": "sp_kode,wyk_id", "sp_kode": f"in.({lys})"})
    if wyk_resp.status_code >= 400:
        raise supabase.SupabaseFout(wyk_resp.text[:500])
    wyke_by_kode: dict[str, set[str]] = defaultdict(set)
    for r in wyk_resp.json():
        wyke_by_kode[r["sp_kode"]].add(r["wyk_id"])

    per_plek = {
        kode: {
            "sp_kode": kode,
            "naam_in_bron": naam_by_kode.get(kode, "?"),
            "wyktal": len(wyke_by_kode.get(kode, set())),
        }
        for kode in LANDELIKE_PLEK_KODES
    }
    return {"per_plek": per_plek, "totaal": sum(p["wyktal"] for p in per_plek.values())}


# ---------------------------------------------------------------------------------
# Verslag
# ---------------------------------------------------------------------------------


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)
    r: list[str] = []
    sectie_foute: dict[str, str] = kw["sectie_foute"]

    r.append("# Kontroleverslag — Verkiesing Fase 2a (Task 8)")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}")
    r.append("")
    r.append(
        "Lees-alleen: hierdie verslag skryf geen rye nie. Dit dek alles wat §5.3 op "
        "hierdie stadium vereis (kandidate en stembriefvolgorde is nog nie gelaai nie — "
        "sien daardie afdeling hieronder). Piet lees dit en sê \"publiseer\" — "
        "`data/publiseer.py` (later taak) doen die werklike swap. 'n Afdeling wat nie "
        "gekontroleer kon word nie (PostgREST-fout) wys dit eksplisiet — die res van "
        "die verslag word steeds volledig geskryf."
    )
    r.append("")

    # --- Harde hekke ------------------------------------------------------------------
    r.append("## Harde hekke")
    hard_gefaal: list[str] = kw["hard_gefaal"]
    r.append(
        f"Gekontroleer: wyke = {VERWAG_WYKE_GELAAI}, munisipaliteite = {VERWAG_MUNISIPALITEITE}, "
        f"distrikte = {VERWAG_DISTRIKTE}, rade 2021 = {VERWAG_RADE_2021}, stemlokale met "
        f"onbekende wyk <= {MAKS_STASIES_MET_ONBEKENDE_WYK}, plekke sonder wyk <= "
        f"{MAKS_PLEKKE_SONDER_WYK} en presies die bekende hawe-snippers, geen duplikaat "
        "natuurlike sleutels nie, geen alias met 0 subplekke nie, wyk-selftoets, 4 "
        "plattelandse plekke, Brooklyn/Waterkloof. Sodra kandidate gelaai is ook: geen "
        "kandidaat-wyk_id buite stg_wyke nie, geen ID-vormige veld nie, geen duplikate, leë "
        "name of nul/duplikaat id's nie (die OVK-totaal is 'n besluit, nie 'n hek nie)."
    )
    r.append("")
    if hard_gefaal:
        r.append(f"**GEFAAL ({len(hard_gefaal)}):**")
        for reël in hard_gefaal:
            r.append(f"- {reël}")
    else:
        r.append("**Alle harde hekke geslaag.**")
    r.append("")

    # --- Munisipaliteite ------------------------------------------------------------
    r.append("## Munisipaliteite en distrikte")
    fout = formatteer_afdeling_fout("munisipaliteite", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        muni = kw["muni_res"]
        r.append(
            formatteer_telling_reël(
                "stg_munisipaliteite (metro + plaaslik)",
                muni["metro"] + muni["plaaslik"],
                VERWAG_MUNISIPALITEITE,
            )
        )
        r.append(f"  - metro's: **{muni['metro']}**, plaaslik: **{muni['plaaslik']}**")
        r.append(formatteer_telling_reël("distrikte", muni["distrik"], VERWAG_DISTRIKTE))
    r.append("")

    # --- Wyke ---------------------------------------------------------------------
    r.append("## Wyke")
    fout = formatteer_afdeling_fout("wyke", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        wyke = kw["wyke_res"]
        r.append(formatteer_telling_reël("stg_wyke", wyke["totaal"], VERWAG_WYKE_GELAAI))
        r.append(f"  - amptelike IEC-totaal: {VERWAG_WYKE} (verskil {wyke['totaal'] - VERWAG_WYKE})")
        r.append(f"- sonder geometrie: **{wyke['sonder_geom_totaal']}**")
        for wid in wyke["sonder_geom_lys"]:
            r.append(f"  - `{wid}`")
        r.append("")
        r.append("### Wyke per provinsie")
        r.append("| Provinsie | stg_wyke |")
        r.append("|---|---:|")
        for prov, n in wyke["per_provinsie"].items():
            r.append(f"| {prov} | {n} |")
        r.append("")
        r.append(
            f"Vrystaat: {wyke['per_provinsie'].get('Free State', 0)} teenoor die amptelike "
            f"{VERWAG_VRYSTAAT_WYKE} (verskil "
            f"{wyke['per_provinsie'].get('Free State', 0) - VERWAG_VRYSTAAT_WYKE}) — sien "
            "**Besluite nodig #1** hieronder."
        )
    r.append("")

    # --- Wyk-selftoets ---------------------------------------------------------------
    r.append("## Wyk-selftoets (`rpc/kontroleer_wyke`)")
    fout = formatteer_afdeling_fout("wyk_selftoets", sectie_foute)
    st = kw["selftoets"]
    if fout:
        r.append(f"- {fout}")
    elif st is None:
        r.append("- **rpc/kontroleer_wyke het misluk** — sien Kommentaar/foute hieronder.")
    else:
        r.append(f"- wyke_totaal: {st['wyke_totaal']}")
        r.append(f"- met_geom: {st['met_geom']}")
        r.append(f"- sonder_geom: {st['sonder_geom']}")
        r.append(f"- selftoets_geslaag: {st['selftoets_geslaag']}")
        r.append(f"- selftoets_gefaal: {st['selftoets_gefaal']}")
        if st.get("gefaalde_ids"):
            r.append(f"- gefaalde_ids: {st['gefaalde_ids']}")
        if st["selftoets_gefaal"] == 0:
            r.append(f"\n**Selftoets geslaag: {st['selftoets_geslaag']} / {st['wyke_totaal']}.**")
        else:
            r.append(
                f"\n**Selftoets: {st['selftoets_geslaag']} geslaag, {st['selftoets_gefaal']} gefaal "
                f"van {st['wyke_totaal']}.**"
            )
    r.append("")

    # --- Stemstasies -----------------------------------------------------------------
    r.append("## Stemlokale")
    fout = formatteer_afdeling_fout("stemlokale", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        st_res = kw["stasies_res"]
        r.append(f"- stg_stemstasies: **{st_res['totaal']}**")
        r.append(f"- wyk_id nie in stg_wyke nie: **{len(st_res['onbekende_wyk'])}**")
        for wid in st_res["onbekende_wyk"]:
            r.append(f"  - `{wid}`")
        r.append(f"- leë adresveld: **{len(st_res['leë_adres'])}**")
        for stasie in st_res["leë_adres"]:
            r.append(
                f"  - `{stasie['vd_nommer']}` {stasie['naam']} — {stasie['muni_kode']}, "
                f"wyk `{stasie['wyk_id']}`"
            )
        r.append("")
        r.append("### Stemlokale per provinsie")
        r.append("| Provinsie | stg_stemstasies |")
        r.append("|---|---:|")
        for prov, n in st_res["per_provinsie"].items():
            r.append(f"| {prov} | {n} |")
    r.append("")

    # --- Plekke ----------------------------------------------------------------------
    r.append("## Plekke, oorvleuelings, aliasse")
    fout = formatteer_afdeling_fout("plekke", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        pl = kw["plekke_res"]
        r.append(f"- stg_plekke: **{pl['totaal']}**")
        r.append(f"- stg_plek_wyke: **{pl['plek_wyke_totaal']}**")
        r.append(f"- stg_plek_aliasse: **{pl['alias_totaal']}**")
        r.append(f"- plekke sonder enige wyk (0 oorvleuelings): **{len(pl['sonder_wyk'])}**")
        for plek in pl["sonder_wyk"]:
            r.append(f"  - `{plek['sp_kode']}` {plek['naam']} ({plek['mp_naam']})")
        r.append("")
        r.append("### Aliasse — uitwaaiering (rye per alias in stg_plek_aliasse)")
        r.append(
            "Munisipaliteite = waar die alias se subplekke se 2026-wyke val "
            "(stg_plek_aliasse -> stg_plek_wyke -> stg_wyke)."
        )
        r.append("")
        r.append("| Alias | Subplekke | Munisipaliteite |")
        r.append("|---|---:|---|")
        for alias, inligting in pl["alias_opsomming"].items():
            munis_lys = ", ".join(inligting["munisipaliteite"]) or "—"
            etiket = alias if inligting["in_csv"] else f"{alias} (nie meer in aliasse.csv nie)"
            r.append(f"| {etiket} | {inligting['subplekke']} | {munis_lys} |")
    r.append("")

    # --- 2021 raadsetels ---------------------------------------------------------------
    r.append("## Raadsetels 2021")
    fout = formatteer_afdeling_fout("raadsetels_2021", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        raad = kw["raad_res"]
        r.append(f"- stg_raad_uitslae_2021 (party-rye): **{raad['uitslae_totaal']}**")
        r.append(f"- stg_raad_grootte_2021 (een per raad): **{raad['grootte_totaal']}**")
        r.append(
            "- rade sonder meerderheid (teen die volle raadsgrootte, party + onafhanklikes): "
            f"**{len(raad['geen_meerderheid'])}**"
        )
        r.append("")
        r.append("| Munisipaliteit | Raadsgrootte | Grootste party | Setels |")
        r.append("|---|---:|---|---:|")
        for ry in raad["geen_meerderheid"]:
            r.append(
                f"| {ry['muni_kode']} | {ry['raadsgrootte_totaal']} | {ry['grootste_party']} | {ry['setels']} |"
            )
    r.append("")

    # --- Smoke tests ---------------------------------------------------------------------
    r.append("## Plek-soek steekproewe (smoke tests)")
    r.append(
        "Daar is nog geen soek-RPC nie (dis Fase 2b) — hierdie is eenvoudige REST-opsoeke: "
        "alias eers, anders `naam_soek`-voorvoegsel, dan `stg_plek_wyke` vir die wyktal en "
        "`stg_wyke` vir die munisipaliteite. Eerste vyf name is spec §5.3 se lys; die res "
        "is ekstra steekproewe hierdie taak bygevoeg het."
    )
    r.append("")
    r.append("| Naam | Gevind? | Bron | Plekke | Unieke wyke | Munisipaliteite | Fout |")
    r.append("|---|---|---|---:|---:|---|---|")
    for res in kw["smoke_resultate"]:
        munis_lys = ", ".join(res.get("munisipaliteite") or []) or "—"
        r.append(
            f"| {res['naam']} | {'ja' if res.get('gevind') else 'nee'} | {res.get('bron') or '—'} | "
            f"{res.get('plekke', '—')} | {res.get('wyke', '—')} | {munis_lys} | {res.get('fout', '')} |"
        )
    r.append("")
    if kw.get("brooklyn_probleem"):
        r.append(
            f"**Let op — Brooklyn voldoen nie aan spec §8 se verwagting nie:** {kw['brooklyn_probleem']}."
        )
    else:
        r.append(
            "Brooklyn voldoen aan spec §8: >=2 munisipaliteite, insluitend Tshwane en Kaapstad."
        )
    if kw.get("waterkloof_probleem"):
        r.append(
            f"**Let op — Waterkloof voldoen nie aan spec §8 se verwagting nie:** {kw['waterkloof_probleem']}."
        )
    else:
        r.append("Waterkloof voldoen aan spec §8: sluit Tshwane in.")
    r.append("")
    r.append(
        "Let wel: \"Mahikeng\" (die huidige amptelike spelling) kom glad nie in `stg_plekke` "
        "of `stg_munisipaliteite` voor nie — die bron gebruik deurgaans die ouer spelling "
        "\"Mafikeng\" (7 subplekke, munisipaliteitskode NW383). 'n 2b-soek-alias vir "
        "\"Mahikeng\" → Mafikeng sal nodig wees."
    )
    r.append("")

    # --- Nog nie gelaai nie ---------------------------------------------------------------
    r.append("## Kandidate")
    r.extend(formatteer_kandidaat_afdeling(kw["kandidate_res"], sectie_foute))
    r.append("")

    r.append("## Nog nie gelaai nie")
    fout = formatteer_afdeling_fout("nog_nie_gelaai", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        r.extend(formatteer_nie_gelaai(kw["nie_gelaai_res"]))
    r.append("")

    # --- Diff teen gepubliseerde weergawe ---------------------------------------------------
    r.append("## Diff teen tans gepubliseerde weergawe")
    fout = formatteer_afdeling_fout("gepubliseerde_weergawe", sectie_foute)
    if fout:
        r.append(f"- {fout}")
    else:
        tabelle = kw["publiek_res"]["tabelle"]
        r.append(
            "Elke `stg_`-tabel teen sy publieke tabel, gepaar op die natuurlike sleutel: wat 'n "
            "publiseer sou byvoeg, verwyder of verander. Geometrie (`wyke.geom`, `plekke.geom`) "
            "en `plek_aliasse.id` word nie vergelyk nie. Geen hek nie — verskille is die punt "
            "van 'n publiseer."
        )
        r.append("")
        r.append("| Tabel | stg_ | publiek | toegevoeg | verwyder | verander | Stand |")
        r.append("|---|---:|---:|---:|---:|---:|---|")
        for tabel, d in tabelle.items():
            if d["stg"] == 0 and d["publiek"] == 0:
                stand = "albei leeg"
            elif d["gelyk"]:
                stand = "in pas"
            else:
                stand = "**verskil**"
            r.append(
                f"| {tabel} | {d['stg']} | {d['publiek']} | {d['toegevoeg']} | {d['verwyder']} | "
                f"{d['verander']} | {stand} |"
            )
        for tabel, d in tabelle.items():
            for soort, sleutels in d["voorbeelde"].items():
                if sleutels:
                    r.append(f"- `{tabel}` {soort}, bv.: " + ", ".join(f"`{x}`" for x in sleutels))
    r.append("")

    # --- Besluite nodig -------------------------------------------------------------------
    r.append("## Besluite nodig")

    fout = formatteer_afdeling_fout("wyke", sectie_foute)
    if fout:
        r.append(f"1. **3 Vrystaat-wyke** — {fout}.")
    else:
        wyke_totaal = kw["wyke_res"]["totaal"]
        r.append(
            f"1. **3 Vrystaat-wyke ontbreek in die MDB-lêer** ({wyke_totaal} vs amptelike "
            f"{VERWAG_WYKE}) en het ook geen stemstasies in die OVK-lys nie (bevestig: geen "
            "IEC-stemlokaal verwys na een van daardie 3 wyke nie) — is "
            f"{VERWAG_WYKE} dalk verouderd? Voorstel: publiseer met "
            f"{wyke_totaal} en vra die OVK/MDB."
        )

    fout = formatteer_afdeling_fout("plekke", sectie_foute)
    if fout:
        r.append(f"2. **Alias-uitwaaiering** — {fout}.")
    else:
        kaapstad_n = kw["plekke_res"]["alias_tellings"].get("Kaapstad", 0)
        kaapstad_res = next((s for s in kw["smoke_resultate"] if s["naam"] == "Kaapstad"), {})
        kaapstad_wyke = kaapstad_res.get("wyke", "?")
        r.append(
            f"2. **Alias-uitwaaiering**: \"Kaapstad\" wys na {kaapstad_n} subplekke (oor "
            f"{kaapstad_wyke} unieke 2026-wyke) — soektog in 2b moet saamvoeg per "
            f"hoofplek/munisipaliteit, nie {kaapstad_n} los resultate wys nie."
        )

    fout = formatteer_afdeling_fout("landelike_plekke", sectie_foute)
    if fout:
        r.append(f"3. **4 groot plattelandse plekke** — {fout}.")
    else:
        landelik = kw["landelik_res"]
        beskrywing = formatteer_landelike_plekke(landelik["per_plek"])
        r.append(
            "3. **4 groot plattelandse plekke** (Mnquma/Mnquna, Ngquza Hill, Nyandeni, "
            "Thulamela — let wel: die bronshapefile self spel die eerste \"Mnquna\", nie "
            f"\"Mnquma\" nie) se wyk-oorvleuelings ({beskrywing}, lewendig hierbo gemeet uit "
            "stg_plek_wyke) is met direkte SQL bereken omdat elke PostgREST-oproep na 8s "
            "uitval, selfs vir een plek op 'n slag. 'n Volle herlaai van `laai_plekke.py` "
            "(sonder `--net-oorvleueling-vir`) vee dit uit — die publiseer-draaiboek moet dit "
            "weer met direkte SQL doen (stappe in `data/README.md`)."
        )

    fout = formatteer_afdeling_fout("raadsetels_2021", sectie_foute)
    if fout:
        r.append(f"4. **2021 se geen-meerderheid-telling** — {fout}.")
    else:
        n = len(kw["raad_res"]["geen_meerderheid"])
        r.append(
            f"4. **2021: {n} rade sonder 'n meerderheidsparty** "
            "(vergeleke met die volle raadsgrootte uit stg_raad_grootte_2021, insluitend "
            "onafhanklikes; was verkeerd 67 voor die raadsgrootte-fix). Bevestig dat dit die "
            "regte maatstaf is (volle raad, nie net die som van party-setels nie)."
        )

    fout = formatteer_afdeling_fout("plekke", sectie_foute)
    if fout:
        r.append(f"5. **Hawe-snippers** — {fout}.")
    else:
        sonder_wyk = kw["plekke_res"]["sonder_wyk"]
        hawe_lys = ", ".join(f"{p['naam']}" for p in sonder_wyk)
        r.append(
            f"5. **{len(sonder_wyk)} hawe-snippers** ({hawe_lys}) het geen wyk nie "
            "— voorstel: sluit uit van soektog (of wys 'n \"geen wyk gevind nie\"-boodskap eerder "
            "as 'n leë resultaat)."
        )

    volgende = 6
    fout = formatteer_afdeling_fout("stemlokale", sectie_foute)
    if fout:
        r.append(f"{volgende}. **Stemlokale met leë adres** — {fout}.")
        volgende += 1
    else:
        leë_adres = kw["stasies_res"]["leë_adres"]
        if leë_adres:
            vd_lys = ", ".join(s["vd_nommer"] for s in leë_adres)
            r.append(
                f"{volgende}. **{len(leë_adres)} stemlokale het 'n leë adresveld** "
                f"(VD {vd_lys}, albei in {leë_adres[0]['muni_kode']}) — die OVK-PDF self dra "
                "geen adres vir hierdie rye nie (bronprobleem, nie 'n ontledingsfout nie). "
                "Voorstel: wys net die stasienaam op `/wyk/[wykId]` wanneer die adres leeg is."
            )
            volgende += 1

    kurering = "; ".join(f"\"{alias}\" ({rede})" for alias, rede in ALIASSE_WAT_KURERING_NODIG)
    r.append(
        f"{volgende}. **Aliasse wat 'n gekureerde teiken nodig het** — uit `aliasse.csv` "
        f"verwyder, nie gelaai nie: {kurering}. Voorstel: Piet kies in 2b 'n lys subplekke "
        "per alias."
    )
    volgende += 1

    kandidate_res = kw["kandidate_res"]
    if kandidate_res and kandidate_res.get("gelaai") and kandidate_res["iec_besluite"]:
        r.append(
            f"{volgende}. **Kandidaattotale verskil van die OVK s'n** — "
            + "; ".join(kandidate_res["iec_besluite"])
            + f". Die OVK korrigeer sy lyste tot {lk.IEC_REGSTELLING_TOT}: publiseer so, of wag "
            "vir 'n nuwe lys en herlaai?"
        )
        volgende += 1

    r.append(
        f"{volgende}. **\"Mahikeng\" (huidige amptelike spelling) kom nie in die bron voor "
        "nie** — net die ouer \"Mafikeng\" (7 subplekke, NW383). Voorstel: 'n soek-alias "
        "in 2b."
    )
    r.append("")

    # --- Kommentaar ----------------------------------------------------------------------
    if kw.get("kommentaar"):
        r.append("## Kommentaar")
        for reël in kw["kommentaar"]:
            r.append(f"- {reël}")
        r.append("")

    r.append("## Tydsberekening")
    r.append(f"- Volle kontrole: {kw['kontrole_tyd']:.1f}s")
    r.append("")

    VERSLAG_PAD.write_text("\n".join(r))


# ---------------------------------------------------------------------------------
# Hoof
# ---------------------------------------------------------------------------------


def hoof() -> int:
    tydstempel = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    begin = time.monotonic()
    kommentaar: list[str] = []
    hard_gefaal: list[str] = []
    sectie_foute: dict[str, str] = {}

    try:
        klient = _bou_klient()
    except omgewing.OmgewingFout as fout:
        # Kan nog geen kliënt bou nie — daar is letterlik niks om te kontroleer of te
        # rapporteer nie, dus skryf ons hier geen verslag nie (anders as elke
        # gelaaide afdeling hieronder, wat wel elkeen onafhanklik faal-veilig is).
        print(f"Omgewingsfout: {fout}", file=sys.stderr)
        return 1

    def v(sectie: str, funksie: Callable[[], dict]):
        return veilig(hard_gefaal, sectie_foute, sectie, funksie)

    try:
        muni_res = v("munisipaliteite", lambda: gather_munisipaliteite(klient))
        muni_provinsie = muni_res["muni_provinsie"] if muni_res else {}
        muni_naam = muni_res["muni_naam"] if muni_res else {}

        wyke_res = v("wyke", lambda: gather_wyke(klient, muni_provinsie))

        selftoets = v("wyk_selftoets", lambda: gather_wyk_selftoets(klient))
        if selftoets is not None and selftoets["selftoets_gefaal"] > 0:
            hard_gefaal.append(
                f"wyk_selftoets: {selftoets['selftoets_gefaal']} wyk(e) gefaal van {selftoets['wyke_totaal']}"
            )

        stasies_res = v("stemlokale", lambda: gather_stemstasies(klient, muni_provinsie))
        plekke_res = v("plekke", lambda: gather_plekke(klient, muni_naam))
        raad_res = v("raadsetels_2021", lambda: gather_raadsetels(klient))
        nie_gelaai_res = v("nog_nie_gelaai", lambda: gather_nie_gelaai(klient))
        kandidate_res = v("kandidate", lambda: gather_kandidate(klient, muni_provinsie))
        voorafgelees = kandidate_res.pop("_rye", None) if kandidate_res else None
        hard_gefaal.extend(evalueer_kandidaat_hekke(kandidate_res))
        publiek_res = v("gepubliseerde_weergawe", lambda: gather_publieke_diff(klient, voorafgelees))

        landelik_res = v("landelike_plekke", lambda: gather_landelike_plekke(klient))
        if landelik_res:
            for inligting in landelik_res["per_plek"].values():
                if inligting["wyktal"] == 0:
                    hard_gefaal.append(
                        f"{inligting['naam_in_bron']} ({inligting['sp_kode']}) het 0 wyke in stg_plek_wyke"
                    )

        # --- Harde hekke: tellings, onbekende wyke, plekke sonder wyk, duplikaat
        # natuurlike sleutels, leë aliasse (net vir afdelings wat wél gekontroleer kon
        # word — 'n mislukte afdeling is reeds in hard_gefaal via veilig()). ---
        if muni_res and (muni_res["metro"] + muni_res["plaaslik"] + muni_res["distrik"]) == 0:
            hard_gefaal.append("stg_munisipaliteite is leeg")
        if wyke_res and wyke_res["totaal"] == 0:
            hard_gefaal.append("stg_wyke is leeg")
        hard_gefaal.extend(evalueer_harde_hekke(muni_res, wyke_res, stasies_res, plekke_res, raad_res))

        # --- Smoke tests (spec §5.3: Brooklyn, Waterkloof, Stellenbosch, Kaapstad,
        # Moreleta Park, plus this task's extra names) ---
        smoke_resultate = [smoke_toets_plek(klient, naam, muni_naam) for naam in SMOKE_NAME]
        brooklyn = next((s for s in smoke_resultate if s["naam"] == "Brooklyn"), {})
        waterkloof = next((s for s in smoke_resultate if s["naam"] == "Waterkloof"), {})
        brooklyn_probleem = kontroleer_veelvuldige_munisipaliteite(
            brooklyn.get("munisipaliteite", []), ("Tshwane", "Cape Town"), min_aantal=2
        )
        waterkloof_probleem = kontroleer_veelvuldige_munisipaliteite(
            waterkloof.get("munisipaliteite", []), ("Tshwane",), min_aantal=1
        )
        if brooklyn_probleem:
            hard_gefaal.append(f"Brooklyn-steekproef voldoen nie aan spec §8 nie: {brooklyn_probleem}")
        if waterkloof_probleem:
            hard_gefaal.append(f"Waterkloof-steekproef voldoen nie aan spec §8 nie: {waterkloof_probleem}")

    finally:
        klient.close()

    kontrole_tyd = time.monotonic() - begin

    skryf_verslag(
        tydstempel=tydstempel,
        sectie_foute=sectie_foute,
        hard_gefaal=hard_gefaal,
        muni_res=muni_res,
        wyke_res=wyke_res,
        selftoets=selftoets,
        stasies_res=stasies_res,
        plekke_res=plekke_res,
        raad_res=raad_res,
        nie_gelaai_res=nie_gelaai_res,
        kandidate_res=kandidate_res,
        publiek_res=publiek_res,
        landelik_res=landelik_res,
        smoke_resultate=smoke_resultate,
        brooklyn_probleem=brooklyn_probleem,
        waterkloof_probleem=waterkloof_probleem,
        kommentaar=kommentaar,
        kontrole_tyd=kontrole_tyd,
    )

    if wyke_res:
        print(f"Wyke: {wyke_res['totaal']} (verwag {VERWAG_WYKE_GELAAI}; amptelik {VERWAG_WYKE})")
    if muni_res:
        print(f"Munisipaliteite: {muni_res['metro'] + muni_res['plaaslik']} (+ {muni_res['distrik']} distrikte)")
    if stasies_res:
        print(f"Stemstasies: {stasies_res['totaal']}")
    if plekke_res:
        print(
            f"Plekke: {plekke_res['totaal']}, plek_wyke: {plekke_res['plek_wyke_totaal']}, "
            f"aliasse: {plekke_res['alias_totaal']}"
        )
    if raad_res:
        print(f"Raadsetel-rye: {raad_res['uitslae_totaal']}, rade sonder meerderheid: {len(raad_res['geen_meerderheid'])}")
    if kandidate_res:
        if kandidate_res.get("gelaai"):
            t = kandidate_res["tellings"]
            print(
                f"Kandidate: {lk.getal(t['totaal'])} (OVK {lk.getal(lk.IEC_TOTAAL)}), "
                f"partye: {kandidate_res['partye_totaal']}"
            )
        else:
            print("Kandidate: nog nie gelaai nie")
    if publiek_res:
        verskil = [t for t, d in publiek_res["tabelle"].items() if not d["gelyk"]]
        print(f"Publiseer-diff: {'alles in pas' if not verskil else 'verskil in ' + ', '.join(verskil)}")
    if selftoets is not None:
        print(f"Wyk-selftoets: {selftoets['selftoets_geslaag']} geslaag / {selftoets['selftoets_gefaal']} gefaal")
    print(f"Kontrole-tyd: {kontrole_tyd:.1f}s")
    print(f"Verslag: {VERSLAG_PAD}")

    if hard_gefaal:
        print("Harde kontroles het gefaal:", file=sys.stderr)
        for reën in hard_gefaal:
            print(f"  - {reën}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
