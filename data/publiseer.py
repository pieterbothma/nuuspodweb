"""Verkiesing Fase 2b, Task 2 — move checked `stg_` data into the public tables the
site reads, then refresh the site's cache.

This is the one command that runs the moment Piet says "publiseer" (and again the
moment the IEC candidate list has been loaded and approved), so it is deliberately
boring: it validates first, writes in a fixed order, verifies every count, and always
leaves `data/uitvoer/publiseer-verslag.md` behind — even when it fails.

    cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest python publiseer.py \
        --datastelle munisipaliteite,wyke,stemstasies,plekke,plek_wyke,plek_aliasse,raad_uitslae_2021,raad_grootte_2021 \
        --bron-datum 2026-09-16

    [--stukgrootte 2000] [--droogloop] [--aanvaar-verskil "rede"]

What it does, in order:

1. `kontroleer_datastelle` — every name must be on the same 11-name allow-list the SQL
   functions hard-code (`publiseer_leeg`/`publiseer_tabel`/`publiseer_afrond`, migration
   20260916062706 and its fix rounds). A name off the list is a `PubliseerFout` before
   anything is read, let alone written.
2. Counts: every requested dataset's `stg_` count, and all 11 public counts.
3. `kontroleer_afhanklikhede` — the FK gate. The public tables carry real foreign keys
   with no ON DELETE CASCADE, so `publiseer_leeg('wyke')` fails while `public.stemstasies`
   still holds rows. Emptying a parent therefore requires its non-empty children in the
   same run; otherwise the run stops **before any write**.
4. Empty phase: `publiseer_leeg` for every dataset being published, in **reverse**
   PUBLISEERBAAR order (children first) — again, the FKs.
5. Fill phase: `publiseer_tabel(datastel, van, tot)` per chunk in forward PUBLISEERBAAR
   order, retrying and halving a chunk on a statement timeout. A chunk is idempotent
   (`on conflict do nothing`), so a retry after a client-side timeout cannot duplicate.
6. Verify: the public count must equal the `stg_` count. A mismatch aborts unless
   `--aanvaar-verskil "rede"` is given, and the reason goes into the report.
7. `publiseer_afrond(datastelle, bron_datum)` — one `data_weergawes` row per dataset.
8. `POST https://www.nuuspod.co.za/api/herlaai` once per affected cache tag. A failed
   refresh is a **warning**, not a failure — the report says so and the exit code stays 0.

A dataset whose `stg_` table is empty is skipped entirely (logged as skipped): its public
table keeps whatever is already published, which is what you want on candidate day when
only `partye`/`kandidate`/`stembrief_volgorde` have new rows.

`--droogloop` does steps 1-3 and prints the plan (chunks per dataset) without emptying,
filling, rounding off or refreshing.

Credentials: the Supabase secret key comes from `~/nuuspod/.env.local` and the site's
`HERLAAI_SECRET` from `nuuspod-web/.env.local`, both only through `lib/omgewing.py`.
Neither value is ever printed, logged or written to the report.
"""

from __future__ import annotations

import sys
import time
from datetime import date, datetime
from pathlib import Path

import httpx

from lib import omgewing, supabase

BASIS_PAD = Path(__file__).parent
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "publiseer-verslag.md"

# The same 11 names, in the same order, as the hard-coded `publiseerbaar` array inside
# publiseer_leeg / publiseer_tabel / publiseer_afrond. The order is also the FK-safe
# **fill** order (every parent before its children); the empty phase walks it backwards.
PUBLISEERBAAR: tuple[str, ...] = (
    "munisipaliteite",
    "wyke",
    "stemstasies",
    "plekke",
    "plek_wyke",
    "plek_aliasse",
    "raad_uitslae_2021",
    "raad_grootte_2021",
    "partye",
    "kandidate",
    "stembrief_volgorde",
)

# public FK dependents per dataset (migration 20260915082741 + 20260915111818). Used by
# the pre-flight gate only — `munisipaliteite`'s self-reference (distrik_kode) is left
# out because a table is always emptied and filled together with itself.
KINDERS: dict[str, tuple[str, ...]] = {
    "munisipaliteite": (
        "wyke",
        "stemstasies",
        "raad_uitslae_2021",
        "raad_grootte_2021",
        "kandidate",
        "stembrief_volgorde",
    ),
    "wyke": ("stemstasies", "plek_wyke", "kandidate"),
    "plekke": ("plek_wyke", "plek_aliasse"),
    "partye": ("kandidate", "stembrief_volgorde"),
}

# The site's cache tags (app/api/herlaai/route.ts): geography/stations/places/aliases/
# the 2021 council under `wyke`, candidates/parties/ballot order under `kandidate`.
TAG_PER_DATASTEL: dict[str, str] = {
    "munisipaliteite": "wyke",
    "wyke": "wyke",
    "stemstasies": "wyke",
    "plekke": "wyke",
    "plek_wyke": "wyke",
    "plek_aliasse": "wyke",
    "raad_uitslae_2021": "wyke",
    "raad_grootte_2021": "wyke",
    "partye": "kandidate",
    "kandidate": "kandidate",
    "stembrief_volgorde": "kandidate",
}
TAG_ORDE: tuple[str, ...] = ("wyke", "kandidate")

HERLAAI_URL = "https://www.nuuspod.co.za/api/herlaai"
HERLAAI_TYDSUIT_S = 30.0

STANDAARD_STUKGROOTTE = 2000
# munisipaliteite must land in ONE insert: `distrik_kode` references the same table, and
# the rows are ordered by `kode`, so a local council can precede its district. A
# non-deferred FK is checked at the end of the statement, which makes a single-statement
# insert safe and a split one a guaranteed FK violation. 257 rows took 0.3s in Task 1, so
# one chunk never comes near the 8s statement_timeout.
ENKEL_STUK_DATASTELLE: frozenset[str] = frozenset({"munisipaliteite"})

MAKS_STUK_POGINGS = 3  # attempts for a 1-row range before giving up
STUK_HERHALING_VERTRAGING_S = 2.0


class PubliseerFout(Exception):
    """Raised on any hard publish failure (bad arguments, blocked FK gate, a chunk that
    never succeeds, a count mismatch without --aanvaar-verskil)."""


# ---------------------------------------------------------------------------------
# Pure helpers (network-free — covered by data/tests/test_publiseer.py)
# ---------------------------------------------------------------------------------


def stukkies(totaal: int, grootte: int) -> list[tuple[int, int]]:
    """1-based inclusive (van, tot) ranges covering `totaal` rows, `grootte` at a time.

    These are `publiseer_tabel`'s row_number() bounds, not offsets: 4485 rows at 2000
    gives (1, 2000), (2001, 4000), (4001, 4485).
    """
    if grootte < 1:
        raise PubliseerFout(f"stukgrootte moet minstens 1 wees, nie {grootte} nie")
    return [(van, min(van + grootte - 1, totaal)) for van in range(1, totaal + 1, grootte)]


def kontroleer_datastelle(name: list[str]) -> list[str]:
    """Validate the requested dataset names and return them in PUBLISEERBAAR order.

    Same allow-list as the SQL functions, so a typo fails here (before any read) rather
    than inside a SECURITY DEFINER function halfway through a publish.
    """
    if not name:
        raise PubliseerFout("geen datastelle gegee nie (--datastelle is verpligtend)")
    onbekend = [n for n in name if n not in PUBLISEERBAAR]
    if onbekend:
        raise PubliseerFout(
            f"onbekende datastel(le): {', '.join(onbekend)} — geldig is: {', '.join(PUBLISEERBAAR)}"
        )
    duplikate = sorted({n for n in name if name.count(n) > 1})
    if duplikate:
        raise PubliseerFout(f"datastel(le) meer as een keer gegee: {', '.join(duplikate)}")
    return [n for n in PUBLISEERBAAR if n in set(name)]


def leeg_orde(datastelle: list[str]) -> list[str]:
    """The empty-phase order: PUBLISEERBAAR reversed (children before their parents)."""
    gevra = set(datastelle)
    return [n for n in reversed(PUBLISEERBAAR) if n in gevra]


def tags_vir(datastelle: list[str]) -> list[str]:
    """The site cache tags these datasets affect, in TAG_ORDE, without duplicates."""
    getref = {TAG_PER_DATASTEL[n] for n in datastelle if n in TAG_PER_DATASTEL}
    return [t for t in TAG_ORDE if t in getref]


def kontroleer_afhanklikhede(
    datastelle: list[str], publieke_tellings: dict[str, int]
) -> list[str]:
    """The FK gate: one message per dataset that cannot be emptied yet.

    `publiseer_leeg(ouer)` is a plain DELETE, and the public FKs have no ON DELETE
    CASCADE, so a parent can only be emptied when each of its children is either empty
    or being republished in the same run. A missing count counts as 0 (the caller reads
    all 11 public counts before calling this).
    """
    gevra = set(datastelle)
    blokkeerders: list[str] = []
    for datastel in datastelle:
        for kind in KINDERS.get(datastel, ()):
            if kind in gevra:
                continue
            if publieke_tellings.get(kind, 0) > 0:
                blokkeerders.append(
                    f"{datastel}: public.{kind} dra {publieke_tellings.get(kind, 0)} rye en "
                    f"verwys na {datastel} — publiseer {kind} saam, of maak dit eers leeg"
                )
    return blokkeerders


def ontleed_inhoud_reeks(header: str) -> int:
    """Parse PostgREST's `Content-Range` ("0-0/4485", "*/0") to its total count."""
    return int(header.rsplit("/", 1)[-1])


def ontleed_argumente(argv: list[str]) -> dict:
    """Parse the CLI into {datastelle, stukgrootte, bron_datum, droogloop,
    aanvaar_verskil}. Raises PubliseerFout on anything unknown or malformed."""
    argumente: dict = {
        "datastelle": [],
        "stukgrootte": STANDAARD_STUKGROOTTE,
        "bron_datum": date.today().isoformat(),
        "droogloop": False,
        "aanvaar_verskil": None,
    }
    oorblywend = list(argv)
    gesien_datastelle = False

    while oorblywend:
        vlag = oorblywend.pop(0)
        if vlag == "--droogloop":
            argumente["droogloop"] = True
            continue
        if vlag not in ("--datastelle", "--stukgrootte", "--bron-datum", "--aanvaar-verskil"):
            raise PubliseerFout(f"onbekende argument: {vlag!r}")
        if not oorblywend:
            raise PubliseerFout(f"{vlag} het 'n waarde nodig")
        waarde = oorblywend.pop(0)
        if vlag == "--datastelle":
            argumente["datastelle"] = [d.strip() for d in waarde.split(",") if d.strip()]
            gesien_datastelle = True
        elif vlag == "--stukgrootte":
            try:
                argumente["stukgrootte"] = int(waarde)
            except ValueError as fout:
                raise PubliseerFout(f"--stukgrootte moet 'n heelgetal wees: {waarde!r}") from fout
            if argumente["stukgrootte"] < 1:
                raise PubliseerFout("--stukgrootte moet minstens 1 wees")
        elif vlag == "--bron-datum":
            try:
                datetime.strptime(waarde, "%Y-%m-%d")
            except ValueError as fout:
                raise PubliseerFout(f"--bron-datum moet JJJJ-MM-DD wees: {waarde!r}") from fout
            argumente["bron_datum"] = waarde
        else:
            argumente["aanvaar_verskil"] = waarde

    if not gesien_datastelle or not argumente["datastelle"]:
        raise PubliseerFout("--datastelle is verpligtend (bv. --datastelle wyke,stemstasies)")
    return argumente


def stukgrootte_vir(datastel: str, stukgrootte: int, stg_telling: int) -> int:
    """The chunk size actually used for `datastel` — the whole table for the datasets
    that must land in a single insert (see ENKEL_STUK_DATASTELLE)."""
    if datastel in ENKEL_STUK_DATASTELLE:
        return max(stg_telling, 1)
    return stukgrootte


# ---------------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------------


def _bou_klient() -> httpx.Client:
    """Own httpx.Client (mirrors `lib.supabase._bou_klient`, the same pattern
    `kontroleer.py` and `laai_plekke.py` use) because this script needs plain GETs with
    a `Prefer: count=exact` header, which `lib/supabase.py` does not expose — and that
    file is out of this task's scope."""
    omgewing_waardes = omgewing.lees()
    basis_url = omgewing_waardes["url"].rstrip("/") + "/rest/v1/"
    koptekste = {
        "apikey": omgewing_waardes["sleutel"],
        "Authorization": f"Bearer {omgewing_waardes['sleutel']}",
        "Content-Type": "application/json",
    }
    return httpx.Client(base_url=basis_url, headers=koptekste, timeout=60.0)


def telling(klient: httpx.Client, tabel: str) -> int:
    """GET tabel with `Prefer: count=exact`, `Range: 0-0` — the total only, never the
    rows (fast even for stg_plek_wyke's 35 582)."""
    resp = klient.get(
        tabel,
        headers={"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"},
    )
    if resp.status_code >= 400:
        raise supabase.SupabaseFout(resp.text[:500])
    return ontleed_inhoud_reeks(resp.headers.get("content-range", "*/0"))


def publiseer_stuk(
    datastel: str,
    van: int,
    tot: int,
    tydsberekenings: list[dict],
    klient: httpx.Client | None = None,
) -> int:
    """`publiseer_tabel(datastel, van, tot)` for one chunk; halve and retry on failure.

    `lib.supabase.rpc` already retries 3× with exponential backoff on 429/5xx (a
    PostgREST 57014 statement timeout arrives as HTTP 500), but one chunk can still be
    heavier than its neighbours. In that case the range is halved — exactly what
    `plaas_bondels` does with a 413 and `laai_plekke.py` with `bou_plek_wyke` — down to
    a single row, which gets MAKS_STUK_POGINGS attempts before this raises PubliseerFout.

    Unlike `laai_plekke.py` a stubborn range is **never skipped**: a missing row here
    would be a ward or a candidate silently absent from the live site.

    Every successful call is appended to `tydsberekenings` as
    {datastel, van, tot, ingevoeg, tyd_s}. The insert is `on conflict do nothing`, so a
    retry of a chunk the server actually finished inserts 0 rows instead of duplicating.
    """
    laaste_fout: Exception | None = None
    for poging in range(1, MAKS_STUK_POGINGS + 1):
        begin = time.monotonic()
        try:
            ingevoeg = supabase.rpc(
                "publiseer_tabel", {"datastel": datastel, "van": van, "tot": tot}, klient=klient
            )
            tyd = time.monotonic() - begin
            tydsberekenings.append(
                {"datastel": datastel, "van": van, "tot": tot, "ingevoeg": ingevoeg, "tyd_s": tyd}
            )
            print(f"    {datastel}[{van}..{tot}]: {ingevoeg} ingevoeg ({tyd:.1f}s)")
            return ingevoeg or 0
        except supabase.SupabaseFout as fout:
            laaste_fout = fout
            if tot > van:
                middel = van + (tot - van) // 2
                print(
                    f"    {datastel}[{van}..{tot}] het misluk ({fout}) — halveer na "
                    f"[{van}..{middel}] + [{middel + 1}..{tot}]"
                )
                return publiseer_stuk(
                    datastel, van, middel, tydsberekenings, klient=klient
                ) + publiseer_stuk(datastel, middel + 1, tot, tydsberekenings, klient=klient)
            print(
                f"    {datastel}[{van}..{tot}] (1 ry) poging {poging}/{MAKS_STUK_POGINGS} het "
                f"misluk: {fout}"
            )
            if poging < MAKS_STUK_POGINGS:
                time.sleep(STUK_HERHALING_VERTRAGING_S)

    raise PubliseerFout(
        f"{datastel}[{van}..{tot}] kon nie gepubliseer word nie ná {MAKS_STUK_POGINGS} "
        f"pogings: {laaste_fout}"
    )


def herlaai(tags: list[str], geheim: str, klient: httpx.Client | None = None) -> list[dict]:
    """POST /api/herlaai once per tag. Never raises, never echoes the secret.

    `follow_redirects=False` (fetch's `redirect: "manual"`): the apex-to-www redirect
    would drop the Authorization header, so a 3xx is reported as a failure to fix rather
    than silently followed. Each result is
    {tag, ok, status, liggaam} with `liggaam` the response body truncated to 200 chars
    (the route only ever answers {"ok":true,...} or {"fout":...}).
    """
    eie_klient = klient is None
    aktiewe_klient = klient if klient is not None else httpx.Client(follow_redirects=False)
    uitslae: list[dict] = []
    try:
        for tag in tags:
            try:
                resp = aktiewe_klient.post(
                    HERLAAI_URL,
                    json={"tag": tag},
                    headers={"Authorization": f"Bearer {geheim}"},
                    timeout=HERLAAI_TYDSUIT_S,
                )
            except httpx.HTTPError as fout:
                # str(httpx.HTTPError) never contains request headers, so the secret
                # cannot leak through here.
                uitslae.append({"tag": tag, "ok": False, "status": None, "liggaam": str(fout)[:200]})
                continue
            uitslae.append(
                {
                    "tag": tag,
                    "ok": resp.status_code == 200,
                    "status": resp.status_code,
                    "liggaam": (resp.text or "")[:200],
                }
            )
    finally:
        if eie_klient:
            aktiewe_klient.close()
    return uitslae


# ---------------------------------------------------------------------------------
# Verslag
# ---------------------------------------------------------------------------------


def bou_verslag(**kw) -> str:
    """The whole `data/uitvoer/publiseer-verslag.md` as one string (pure — the caller
    writes it, so it can be written on the failure path too)."""
    r: list[str] = []
    geslaag = not kw["foute"]
    r.append("# Publiseerverslag — Verkiesing Fase 2b (Task 2)")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}")
    r.append("")
    r.append(f"**Uitslag: {'GESLAAG' if geslaag else 'GEFAAL'}**" + (" (droogloop)" if kw["droogloop"] else ""))
    r.append("")
    r.append("## Opdrag")
    r.append(f"- Datastelle gevra: `{','.join(kw['gevra'])}`")
    r.append(f"- Stukgrootte: {kw['stukgrootte']}")
    r.append(f"- Brondatum: {kw['bron_datum']}")
    r.append(f"- Droogloop: {'ja' if kw['droogloop'] else 'nee'}")
    r.append(
        f"- `--aanvaar-verskil`: {kw['aanvaar_verskil']!r}" if kw["aanvaar_verskil"]
        else "- `--aanvaar-verskil`: nie gegee nie (enige telling-verskil is 'n harde fout)"
    )
    r.append("")

    if kw["foute"]:
        r.append("## Foute (GEFAAL)")
        for fout in kw["foute"]:
            r.append(f"- {fout}")
        r.append("")

    r.append("## Datastelle")
    if not kw["uitslae"]:
        r.append("Geen datastel is verwerk nie.")
    else:
        r.append(
            "| Datastel | stg-rye | verwyder | gepubliseer | publiek ná | stukke | "
            "langste stuk (s) | tyd (s) | status |"
        )
        r.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for u in kw["uitslae"]:
            if u.get("oorgeslaan"):
                r.append(
                    f"| `{u['datastel']}` | {u.get('stg', 0)} | — | — | "
                    f"{u.get('publiek_na', '—')} | — | — | — | oorgeslaan (stg leeg) |"
                )
                continue
            status = f"verskil aanvaar: {u['verskil']}" if u.get("verskil") else "ok"
            r.append(
                f"| `{u['datastel']}` | {u.get('stg', '—')} | {u.get('verwyder', '—')} | "
                f"{u.get('gepubliseer', '—')} | {u.get('publiek_na', '—')} | "
                f"{u.get('stukke', '—')} | {u.get('langste_stuk_s', 0.0):.1f} | "
                f"{u.get('tyd_s', 0.0):.1f} | {status} |"
            )
    r.append("")

    if kw.get("plan"):
        r.append("## Plan (droogloop)")
        r.append("| Datastel | stg-rye | publiek voor | stukgrootte | stukke |")
        r.append("|---|---:|---:|---:|---:|")
        for reël in kw["plan"]:
            r.append(
                f"| `{reël['datastel']}` | {reël['stg']} | {reël['publiek_voor']} | "
                f"{reël['stukgrootte']} | {reël['stukke']} |"
            )
        r.append("")
        r.append(f"Leeg-orde (omgekeerde FK-orde): `{' -> '.join(kw['leeg_orde'])}`")
        r.append(f"Vul-orde: `{' -> '.join(kw['vul_orde'])}`")
        r.append("")

    r.append("## `publiseer_afrond`")
    if kw["droogloop"]:
        r.append("- nie geroep nie (droogloop)")
    elif kw["afrond_ok"]:
        r.append(
            f"- geroep vir {len([u for u in kw['uitslae'] if not u.get('oorgeslaan')])} "
            f"datastel(le) met `bron_datum = {kw['bron_datum']}` — een `data_weergawes`-ry elk"
        )
    else:
        r.append("- **nie suksesvol nie** (sien Foute hierbo)")
    r.append("")

    r.append("## Kasverfrissing (`POST /api/herlaai`)")
    r.append(
        "'n Mislukte verfrissing is 'n **waarskuwing**, nie 'n fout nie — die data is "
        "gepubliseer; die werf se kas verval eers later (of kan met die hand herlaai word)."
    )
    r.append("")
    if kw["droogloop"]:
        r.append("- nie geroep nie (droogloop)")
    elif not kw["herlaai_uitslae"]:
        r.append("- nie geroep nie")
    else:
        r.append("| Tag | Status | Antwoord |")
        r.append("|---|---:|---|")
        for u in kw["herlaai_uitslae"]:
            r.append(f"| `{u['tag']}` | {u['status'] if u['status'] is not None else '—'} | `{u['liggaam']}` |")
        mislukte = [u["tag"] for u in kw["herlaai_uitslae"] if not u["ok"]]
        if mislukte:
            r.append("")
            r.append(f"**Waarskuwing:** {len(mislukte)} tag(s) nie verfris nie: {', '.join(mislukte)}.")
    r.append("")

    if kw.get("waarskuwings"):
        r.append("## Waarskuwings")
        for waarskuwing in kw["waarskuwings"]:
            r.append(f"- {waarskuwing}")
        r.append("")

    r.append("## Tydsberekening")
    r.append(f"- Totaal: {kw.get('totale_tyd', 0.0):.1f}s")
    if kw.get("langste_stuk"):
        langste = kw["langste_stuk"]
        r.append(
            f"- Langste enkele stuk: `{langste['datastel']}`[{langste['van']}..{langste['tot']}] "
            f"— {langste['tyd_s']:.1f}s (service_role se `statement_timeout` is 8s)"
        )
    r.append("")
    return "\n".join(r)


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)
    VERSLAG_PAD.write_text(bou_verslag(**kw))


# ---------------------------------------------------------------------------------
# Hoof
# ---------------------------------------------------------------------------------


def hoof(
    datastelle_gevra: list[str],
    stukgrootte: int = STANDAARD_STUKGROOTTE,
    bron_datum: str | None = None,
    droogloop: bool = False,
    aanvaar_verskil: str | None = None,
) -> int:
    tydstempel = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    begin = time.monotonic()
    bron_datum = bron_datum or date.today().isoformat()

    foute: list[str] = []
    waarskuwings: list[str] = []
    uitslae: list[dict] = []
    herlaai_uitslae: list[dict] = []
    tydsberekenings: list[dict] = []
    plan: list[dict] = []
    afrond_ok = False
    datastelle: list[str] = []

    def klaar() -> int:
        langste = max(tydsberekenings, key=lambda t: t["tyd_s"]) if tydsberekenings else None
        skryf_verslag(
            tydstempel=tydstempel,
            bron_datum=bron_datum,
            stukgrootte=stukgrootte,
            droogloop=droogloop,
            aanvaar_verskil=aanvaar_verskil,
            gevra=datastelle or datastelle_gevra,
            uitslae=uitslae,
            herlaai_uitslae=herlaai_uitslae,
            foute=foute,
            afrond_ok=afrond_ok,
            waarskuwings=waarskuwings,
            plan=plan,
            leeg_orde=leeg_orde(datastelle),
            vul_orde=datastelle,
            totale_tyd=time.monotonic() - begin,
            langste_stuk=langste,
        )
        print(f"Verslag: {VERSLAG_PAD}")
        if foute:
            print("Publisering het gefaal:", file=sys.stderr)
            for fout in foute:
                print(f"  - {fout}", file=sys.stderr)
            return 1
        for waarskuwing in waarskuwings:
            print(f"Waarskuwing: {waarskuwing}", file=sys.stderr)
        return 0

    # --- 1. allow-list ---------------------------------------------------------------
    try:
        datastelle = kontroleer_datastelle(datastelle_gevra)
    except PubliseerFout as fout:
        foute.append(str(fout))
        return klaar()

    try:
        klient = _bou_klient()
    except omgewing.OmgewingFout as fout:
        foute.append(f"omgewing: {fout}")
        return klaar()

    try:
        # --- 2. tellings -------------------------------------------------------------
        try:
            stg_tellings = {d: telling(klient, f"stg_{d}") for d in datastelle}
            publiek_voor = {d: telling(klient, d) for d in PUBLISEERBAAR}
        except supabase.SupabaseFout as fout:
            foute.append(f"kon nie die tellings lees nie: {fout}")
            return klaar()

        for datastel in datastelle:
            print(
                f"{datastel}: stg={stg_tellings[datastel]}, publiek voor={publiek_voor[datastel]}"
            )

        te_publiseer = [d for d in datastelle if stg_tellings[d] > 0]
        oorgeslaan = [d for d in datastelle if stg_tellings[d] == 0]
        for datastel in oorgeslaan:
            print(f"{datastel}: stg_{datastel} is leeg — oorgeslaan (publieke tabel bly soos dit is)")
            uitslae.append(
                {
                    "datastel": datastel,
                    "stg": 0,
                    "publiek_na": publiek_voor[datastel],
                    "oorgeslaan": True,
                    "tyd_s": 0.0,
                    "langste_stuk_s": 0.0,
                }
            )

        # --- 3. FK-hek ---------------------------------------------------------------
        blokkeerders = kontroleer_afhanklikhede(te_publiseer, publiek_voor)
        if blokkeerders:
            foute.extend(blokkeerders)
            print("FK-hek het geblokkeer — niks is geskryf nie.", file=sys.stderr)
            return klaar()

        if not te_publiseer:
            waarskuwings.append(
                "elke gevraagde stg_-tabel is leeg — niks is gepubliseer, verfris of afgerond nie"
            )
            return klaar()

        # --- droogloop ---------------------------------------------------------------
        if droogloop:
            print("\nDroogloop — niks word geskryf nie.")
            print(f"Leeg-orde: {' -> '.join(leeg_orde(te_publiseer))}")
            print(f"Vul-orde:  {' -> '.join(te_publiseer)}")
            for datastel in te_publiseer:
                grootte = stukgrootte_vir(datastel, stukgrootte, stg_tellings[datastel])
                stukke = stukkies(stg_tellings[datastel], grootte)
                plan.append(
                    {
                        "datastel": datastel,
                        "stg": stg_tellings[datastel],
                        "publiek_voor": publiek_voor[datastel],
                        "stukgrootte": grootte,
                        "stukke": len(stukke),
                    }
                )
                print(
                    f"  {datastel}: {stg_tellings[datastel]} rye -> {len(stukke)} stuk(ke) van "
                    f"{grootte} (publiek voor: {publiek_voor[datastel]})"
                )
            print(f"Tags wat verfris sou word: {', '.join(tags_vir(te_publiseer)) or '—'}")
            datastelle = te_publiseer
            return klaar()

        # --- 4. leeg (omgekeerde FK-orde) --------------------------------------------
        verwyder_per_datastel: dict[str, int] = {}
        print("\nLeegmaak (omgekeerde FK-orde):")
        for datastel in leeg_orde(te_publiseer):
            try:
                verwyder = supabase.rpc("publiseer_leeg", {"datastel": datastel}, klient=klient)
            except supabase.SupabaseFout as fout:
                foute.append(f"publiseer_leeg({datastel}): {fout}")
                return klaar()
            verwyder_per_datastel[datastel] = verwyder or 0
            print(f"  {datastel}: {verwyder} rye verwyder")

        # --- 5. vul + 6. verifieer ---------------------------------------------------
        print("\nVul (FK-orde):")
        for datastel in te_publiseer:
            datastel_begin = time.monotonic()
            eie_tydsberekenings: list[dict] = []
            grootte = stukgrootte_vir(datastel, stukgrootte, stg_tellings[datastel])
            stukke = stukkies(stg_tellings[datastel], grootte)
            print(f"  {datastel}: {len(stukke)} stuk(ke) van {grootte}")
            gepubliseer = 0
            try:
                for van, tot in stukke:
                    gepubliseer += publiseer_stuk(
                        datastel, van, tot, eie_tydsberekenings, klient=klient
                    )
            except PubliseerFout as fout:
                tydsberekenings.extend(eie_tydsberekenings)
                foute.append(str(fout))
                return klaar()
            tydsberekenings.extend(eie_tydsberekenings)

            try:
                publiek_na = telling(klient, datastel)
            except supabase.SupabaseFout as fout:
                foute.append(f"kon nie public.{datastel} se telling na die publisering lees nie: {fout}")
                return klaar()

            verskil: str | None = None
            if publiek_na != stg_tellings[datastel]:
                boodskap = (
                    f"{datastel}: telling klop nie — stg_{datastel} het "
                    f"{stg_tellings[datastel]} rye, public.{datastel} het {publiek_na}"
                )
                if aanvaar_verskil:
                    verskil = aanvaar_verskil
                    waarskuwings.append(f"{boodskap} (verskil aanvaar: {aanvaar_verskil})")
                    print(f"    Waarskuwing: {boodskap} — aanvaar: {aanvaar_verskil}")
                else:
                    uitslae.append(
                        {
                            "datastel": datastel,
                            "stg": stg_tellings[datastel],
                            "verwyder": verwyder_per_datastel.get(datastel, 0),
                            "gepubliseer": gepubliseer,
                            "publiek_na": publiek_na,
                            "stukke": len(eie_tydsberekenings),
                            "langste_stuk_s": max(
                                (t["tyd_s"] for t in eie_tydsberekenings), default=0.0
                            ),
                            "tyd_s": time.monotonic() - datastel_begin,
                            "oorgeslaan": False,
                            "verskil": None,
                        }
                    )
                    foute.append(boodskap + " — gebruik --aanvaar-verskil \"rede\" as dit korrek is")
                    return klaar()

            uitslae.append(
                {
                    "datastel": datastel,
                    "stg": stg_tellings[datastel],
                    "verwyder": verwyder_per_datastel.get(datastel, 0),
                    "gepubliseer": gepubliseer,
                    "publiek_na": publiek_na,
                    "stukke": len(eie_tydsberekenings),
                    "langste_stuk_s": max((t["tyd_s"] for t in eie_tydsberekenings), default=0.0),
                    "tyd_s": time.monotonic() - datastel_begin,
                    "oorgeslaan": False,
                    "verskil": verskil,
                }
            )
            print(
                f"    {datastel}: {gepubliseer} ingevoeg, publiek nou {publiek_na} "
                f"({time.monotonic() - datastel_begin:.1f}s)"
            )

        # --- 7. afrond ---------------------------------------------------------------
        try:
            supabase.rpc(
                "publiseer_afrond",
                {"datastelle": te_publiseer, "bron_datum": bron_datum},
                klient=klient,
            )
            afrond_ok = True
            print(f"\npubliseer_afrond: {len(te_publiseer)} data_weergawes-ry(e) geskryf")
        except supabase.SupabaseFout as fout:
            foute.append(f"publiseer_afrond: {fout}")
            return klaar()
    finally:
        klient.close()

    # --- 8. kasverfrissing (waarskuwing, nie 'n fout nie) ------------------------------
    tags = tags_vir(te_publiseer)
    if tags:
        try:
            geheim = omgewing.lees_herlaai()
        except omgewing.OmgewingFout as fout:
            waarskuwings.append(f"kas nie verfris nie — {fout}")
        else:
            herlaai_uitslae = herlaai(tags, geheim)
            for uitslag in herlaai_uitslae:
                print(f"herlaai {uitslag['tag']}: HTTP {uitslag['status']} {uitslag['liggaam']}")
            mislukte = [u["tag"] for u in herlaai_uitslae if not u["ok"]]
            if mislukte:
                waarskuwings.append(
                    f"kas nie verfris nie vir: {', '.join(mislukte)} (die data is wél gepubliseer)"
                )

    return klaar()


if __name__ == "__main__":
    try:
        _argumente = ontleed_argumente(sys.argv[1:])
    except PubliseerFout as _fout:
        print(f"{_fout}\nSien die module-dokstring vir die geldige argumente.", file=sys.stderr)
        raise SystemExit(2)

    raise SystemExit(
        hoof(
            _argumente["datastelle"],
            stukgrootte=_argumente["stukgrootte"],
            bron_datum=_argumente["bron_datum"],
            droogloop=_argumente["droogloop"],
            aanvaar_verskil=_argumente["aanvaar_verskil"],
        )
    )
