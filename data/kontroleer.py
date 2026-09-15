"""Task 8: combined check report for Verkiesing Fase 2a.

Reads every stg_ table loaded by Tasks 1-7 (plus the currently-published public
tables, for the §5.3 diff) via PostgREST, runs the ward self-test
(`rpc/kontroleer_wyke`) and a handful of place-search smoke tests, and writes one
combined `data/uitvoer/kontroleverslag.md` so Piet can say "publiseer".

Read-only: this script never writes to Supabase. There is no search RPC yet (that's
Fase 2b), so the smoke tests are implemented as plain REST lookups: resolve a name
through `stg_plek_aliasse` first (exact match), else `stg_plekke.naam_soek` (prefix
match), then `stg_plek_wyke` for the resulting ward count. The `authenticator` role's
8s `statement_timeout` means any of those three calls can time out; a timeout is
recorded as a failed smoke test, not raised — one slow name must never crash the
whole report.

Run: cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest python kontroleer.py
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

import httpx

from lib import omgewing, supabase, teks

BASIS_PAD = Path(__file__).parent
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "kontroleverslag.md"

VERWAG_WYKE = 4488
VERWAG_MUNISIPALITEITE = 213
VERWAG_DISTRIKTE = 44

# stg_ tables that Tasks 1-6 load; an empty one here is a hard failure (unlike
# stg_kandidate / stg_stembrief_volgorde, which are legitimately still empty — see
# "Nog nie gelaai nie" below).
GELAAIDE_TABELLE = (
    "stg_munisipaliteite",
    "stg_wyke",
    "stg_stemstasies",
    "stg_plekke",
    "stg_plek_wyke",
    "stg_plek_aliasse",
    "stg_raad_uitslae_2021",
    "stg_raad_grootte_2021",
)

# Publieke teëhangers van elke stg_-tabel hierbo, vir die §5.3-diff teen die tans
# gepubliseerde weergawe (geen publiseer-stap in hierdie taak nie — sien spec §5.3).
PUBLIEKE_TABELLE = (
    "munisipaliteite",
    "wyke",
    "stemstasies",
    "plekke",
    "plek_wyke",
    "plek_aliasse",
    "raad_uitslae_2021",
    "raad_grootte_2021",
)

# Task 8-brief §Place-search smoke tests: 'n handjievol name — groot metro's,
# 'n hoofstad, 'n dorpie, en (doelbewus) die huidige amptelike spelling "Mahikeng"
# om te kyk of die bron dit ken (dit ken nie — sien §Smoke-toetse in die verslag).
SMOKE_NAME = (
    "Strand",
    "Stellenbosch",
    "Kaapstad",
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


def smoke_toets_plek(klient: httpx.Client, naam: str, tydsuit_s: float = 7.5) -> dict:
    """Resolve `naam` -> ward count, per §Read first item 4's instructions.

    Volgorde: (1) `stg_plek_aliasse` presiese (case-insensitive) treffer, anders
    (2) `stg_plekke.naam_soek` voorvoegsel-treffer, dan altyd `stg_plek_wyke` vir die
    wyktal. 'n Tydverstreke of PostgREST-fout op enige stap word as 'n gefaalde
    steekproef aangeteken, nie 'n uitsondering nie.
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
            return {"naam": naam, "gevind": False, "plekke": 0, "wyke": 0, "bron": None}

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
        return {
            "naam": naam,
            "gevind": True,
            "plekke": len(sp_kodes),
            "wyke": len(wyke),
            "bron": bron,
        }
    except httpx.TimeoutException:
        return {"naam": naam, "gevind": False, "fout": f"PostgREST-tydverstreke (> {tydsuit_s}s)"}


def vind_plekke_sonder_wyk(klient: httpx.Client) -> list[dict]:
    """`stg_plekke` rye met geen `stg_plek_wyke`-ry nie (sp_kode-versameling-verskil,
    nie 'n spatiale navraag nie — vinnig, twee kolomme, alles via kry_alles)."""
    alle_plekke = supabase.kry_alles("stg_plekke", {"select": "sp_kode,naam,mp_naam"}, klient=klient)
    met_wyk = {r["sp_kode"] for r in supabase.kry_alles("stg_plek_wyke", {"select": "sp_kode"}, klient=klient)}
    by_kode = {r["sp_kode"]: r for r in alle_plekke}
    sonder = vind_ontbrekende({r["sp_kode"] for r in alle_plekke}, met_wyk)
    return [by_kode[k] for k in sonder]


def vind_stasies_onbekende_wyk(klient: httpx.Client) -> list[str]:
    wyk_ids = {r["wyk_id"] for r in supabase.kry_alles("stg_wyke", {"select": "wyk_id"}, klient=klient)}
    stasie_wyk_ids = {
        r["wyk_id"] for r in supabase.kry_alles("stg_stemstasies", {"select": "wyk_id"}, klient=klient)
    }
    return vind_ontbrekende(stasie_wyk_ids, wyk_ids)


def vind_stasies_leë_adres(klient: httpx.Client) -> list[dict]:
    resp = klient.get(
        "stg_stemstasies",
        params={"select": "vd_nommer,naam,adres,muni_kode,wyk_id", "adres": "eq."},
    )
    if resp.status_code >= 400:
        raise supabase.SupabaseFout(resp.text[:500])
    return resp.json()


def tel_aliasse(klient: httpx.Client) -> dict[str, int]:
    rye = supabase.kry_alles("stg_plek_aliasse", {"select": "alias"}, klient=klient)
    return dict(sorted(Counter(r["alias"] for r in rye).items()))


# ---------------------------------------------------------------------------------
# Verslag
# ---------------------------------------------------------------------------------


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)
    r: list[str] = []

    r.append("# Kontroleverslag — Verkiesing Fase 2a (Task 8)")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}")
    r.append("")
    r.append(
        "Lees-alleen: hierdie verslag skryf geen rye nie. Dit dek alles wat §5.3 op "
        "hierdie stadium vereis (kandidate en stembriefvolgorde is nog nie gelaai nie — "
        "sien daardie afdeling hieronder). Piet lees dit en sê \"publiseer\" — "
        "`data/publiseer.py` (later taak) doen die werklike swap."
    )
    r.append("")

    # --- Wyke ---------------------------------------------------------------------
    r.append("## Wyke")
    r.append(formatteer_telling_reël("stg_wyke", kw["wyke_totaal"], VERWAG_WYKE))
    r.append(f"- sonder geometrie: **{kw['wyke_sonder_geom_totaal']}**")
    if kw["wyke_sonder_geom_lys"]:
        for wid in kw["wyke_sonder_geom_lys"]:
            r.append(f"  - `{wid}`")
    r.append("")
    r.append("### Wyke per provinsie")
    r.append("| Provinsie | stg_wyke |")
    r.append("|---|---:|")
    for prov, n in kw["wyke_per_provinsie"].items():
        r.append(f"| {prov} | {n} |")
    r.append("")
    r.append(
        f"Vrystaat: {kw['wyke_per_provinsie'].get('Free State', 0)} teenoor die amptelike "
        "311 (verskil 3) — sien **Besluite nodig #1** hieronder."
    )
    r.append("")

    # --- Munisipaliteite ------------------------------------------------------------
    r.append("## Munisipaliteite en distrikte")
    r.append(
        formatteer_telling_reël(
            "stg_munisipaliteite (metro + plaaslik)",
            kw["metro_telling"] + kw["plaaslik_telling"],
            VERWAG_MUNISIPALITEITE,
        )
    )
    r.append(f"  - metro's: **{kw['metro_telling']}**, plaaslik: **{kw['plaaslik_telling']}**")
    r.append(formatteer_telling_reël("distrikte", kw["distrik_telling"], VERWAG_DISTRIKTE))
    r.append("")

    # --- Stemstasies -----------------------------------------------------------------
    r.append("## Stemlokale")
    r.append(f"- stg_stemstasies: **{kw['stasies_totaal']}**")
    r.append(f"- wyk_id nie in stg_wyke nie: **{len(kw['stasies_onbekende_wyk'])}**")
    if kw["stasies_onbekende_wyk"]:
        for wid in kw["stasies_onbekende_wyk"]:
            r.append(f"  - `{wid}`")
    r.append(f"- leë adresveld: **{len(kw['stasies_leë_adres'])}**")
    for stasie in kw["stasies_leë_adres"]:
        r.append(
            f"  - `{stasie['vd_nommer']}` {stasie['naam']} — {stasie['muni_kode']}, "
            f"wyk `{stasie['wyk_id']}`"
        )
    r.append("")
    r.append("### Stemlokale per provinsie")
    r.append("| Provinsie | stg_stemstasies |")
    r.append("|---|---:|")
    for prov, n in kw["stasies_per_provinsie"].items():
        r.append(f"| {prov} | {n} |")
    r.append("")

    # --- Plekke ----------------------------------------------------------------------
    r.append("## Plekke, oorvleuelings, aliasse")
    r.append(f"- stg_plekke: **{kw['plekke_totaal']}**")
    r.append(f"- stg_plek_wyke: **{kw['plek_wyke_totaal']}**")
    r.append(f"- stg_plek_aliasse: **{kw['alias_totaal']}**")
    r.append(f"- plekke sonder enige wyk (0 oorvleuelings): **{len(kw['plekke_sonder_wyk'])}**")
    for plek in kw["plekke_sonder_wyk"]:
        r.append(f"  - `{plek['sp_kode']}` {plek['naam']} ({plek['mp_naam']})")
    r.append("")
    r.append("### Aliasse — uitwaaiering (rye per alias in stg_plek_aliasse)")
    r.append("| Alias | Subplekke |")
    r.append("|---|---:|")
    for alias, n in kw["alias_tellings"].items():
        r.append(f"| {alias} | {n} |")
    r.append("")

    # --- 2021 raadsetels ---------------------------------------------------------------
    r.append("## Raadsetels 2021")
    r.append(f"- stg_raad_uitslae_2021 (party-rye): **{kw['raad_uitslae_totaal']}**")
    r.append(f"- stg_raad_grootte_2021 (een per raad): **{kw['raad_grootte_totaal']}**")
    r.append(
        f"- rade sonder meerderheid (teen die volle raadsgrootte, party + onafhanklikes): "
        f"**{len(kw['geen_meerderheid'])}**"
    )
    r.append("")
    r.append("| Munisipaliteit | Raadsgrootte | Grootste party | Setels |")
    r.append("|---|---:|---|---:|")
    for ry in kw["geen_meerderheid"]:
        r.append(
            f"| {ry['muni_kode']} | {ry['raadsgrootte_totaal']} | {ry['grootste_party']} | {ry['setels']} |"
        )
    r.append("")

    # --- Selftoets ---------------------------------------------------------------------
    r.append("## Wyk-selftoets (`rpc/kontroleer_wyke`)")
    st = kw["selftoets"]
    if st is None:
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

    # --- Smoke tests ---------------------------------------------------------------------
    r.append("## Plek-soek steekproewe (smoke tests)")
    r.append(
        "Daar is nog geen soek-RPC nie (dis Fase 2b) — hierdie is eenvoudige REST-opsoeke: "
        "alias eers, anders `naam_soek`-voorvoegsel, dan `stg_plek_wyke` vir die wyktal."
    )
    r.append("")
    r.append("| Naam | Gevind? | Bron | Plekke | Unieke wyke | Fout |")
    r.append("|---|---|---|---:|---:|---|")
    for res in kw["smoke_resultate"]:
        r.append(
            f"| {res['naam']} | {'ja' if res.get('gevind') else 'nee'} | {res.get('bron') or '—'} | "
            f"{res.get('plekke', '—')} | {res.get('wyke', '—')} | {res.get('fout', '')} |"
        )
    r.append("")
    r.append(
        "Let wel: \"Mahikeng\" (die huidige amptelike spelling) kom glad nie in `stg_plekke` "
        "of `stg_munisipaliteite` voor nie — die bron gebruik deurgaans die ouer spelling "
        "\"Mafikeng\" (7 subplekke, munisipaliteitskode NW383). 'n 2b-soek-alias vir "
        "\"Mahikeng\" → Mafikeng sal nodig wees."
    )
    r.append("")

    # --- Nog nie gelaai nie ---------------------------------------------------------------
    r.append("## Nog nie gelaai nie")
    r.append("Kandidate (16 Sep), stembriefvolgorde (23 Sep).")
    r.append(
        f"- stg_kandidate: {kw['kandidate_totaal']} rye "
        f"({'soos verwag — leeg' if kw['kandidate_totaal'] == 0 else 'ONVERWAGS NIE LEEG NIE'})"
    )
    r.append(
        f"- stg_stembrief_volgorde: {kw['stembrief_volgorde_totaal']} rye "
        f"({'soos verwag — leeg' if kw['stembrief_volgorde_totaal'] == 0 else 'ONVERWAGS NIE LEEG NIE'})"
    )
    r.append("")

    # --- Diff teen gepubliseerde weergawe ---------------------------------------------------
    r.append("## Diff teen tans gepubliseerde weergawe")
    if all(n == 0 for n in kw["publieke_tellings"].values()):
        r.append(
            "Geen publieke tabel dra enige ry nie — daar was nog nooit 'n publiseer-stap "
            "vir hierdie fase nie. Die eerste publiseer sal dus elke stg_-ry as "
            "\"toegevoeg\" oordra; daar is niks om te verwyder of te verander nie."
        )
    else:
        for tabel, n in kw["publieke_tellings"].items():
            r.append(f"- `{tabel}`: {n} rye tans gepubliseer")
    r.append("")
    r.append("| Publieke tabel | Rye |")
    r.append("|---|---:|")
    for tabel, n in kw["publieke_tellings"].items():
        r.append(f"| {tabel} | {n} |")
    r.append("")

    # --- Besluite nodig -------------------------------------------------------------------
    r.append("## Besluite nodig")
    r.append(
        f"1. **3 Vrystaat-wyke ontbreek in die MDB-lêer** ({kw['wyke_totaal']} vs amptelike "
        f"{VERWAG_WYKE}) en het ook geen stemstasies in die OVK-lys nie (bevestig: geen "
        "IEC-stemlokaal verwys na een van daardie 3 wyke nie) — is 4 488 dalk verouderd? "
        "Voorstel: publiseer met "
        f"{kw['wyke_totaal']} en vra die OVK/MDB."
    )
    kaapstad_n = kw["alias_tellings"].get("Kaapstad", 0)
    r.append(
        f"2. **Alias-uitwaaiering**: \"Kaapstad\" wys na {kaapstad_n} subplekke (oor "
        f"{kw['smoke_kaapstad_wyke']} unieke 2026-wyke) — soektog in 2b moet saamvoeg per "
        "hoofplek/munisipaliteit, nie 126 los resultate wys nie."
    )
    r.append(
        "3. **4 groot plattelandse plekke** (Mnquna/Mnquma, Ngquza Hill, Nyandeni, "
        "Thulamela — let wel: die bronshapefile self spel die eerste \"Mnquna\", nie "
        "\"Mnquma\" nie) se wyk-oorvleuelings (34 + 32 + 32 + 58 = 156 rye) is met direkte "
        "SQL bereken omdat elke PostgREST-oproep na 8s uitval, selfs vir een plek op 'n "
        "slag. 'n Volle herlaai van `laai_plekke.py` (sonder `--net-oorvleueling-vir`) vee "
        "dit uit — die publiseer-draaiboek moet dit weer met direkte SQL doen (sien "
        "Task-5-verslag)."
    )
    r.append(
        f"4. **2021: {len(kw['geen_meerderheid'])} rade sonder 'n meerderheidsparty** "
        "(vergeleke met die volle raadsgrootte uit stg_raad_grootte_2021, insluitend "
        f"onafhanklikes; was verkeerd 67 voor die raadsgrootte-fix). Bevestig dat dit die "
        "regte maatstaf is (volle raad, nie net die som van party-setels nie)."
    )
    hawe_lys = ", ".join(f"{p['naam']}" for p in kw["plekke_sonder_wyk"])
    r.append(
        f"5. **{len(kw['plekke_sonder_wyk'])} hawe-snippers** ({hawe_lys}) het geen wyk nie "
        "— voorstel: sluit uit van soektog (of wys 'n \"geen wyk gevind nie\"-boodskap eerder "
        "as 'n leë resultaat)."
    )
    volgende = 6
    if kw["stasies_leë_adres"]:
        vd_lys = ", ".join(s["vd_nommer"] for s in kw["stasies_leë_adres"])
        r.append(
            f"{volgende}. **{len(kw['stasies_leë_adres'])} stemlokale het 'n leë adresveld** "
            f"(VD {vd_lys}, albei in {kw['stasies_leë_adres'][0]['muni_kode']}) — die OVK-PDF "
            "self dra geen adres vir hierdie rye nie (bronprobleem, nie 'n ontledingsfout "
            "nie). Voorstel: wys net die stasienaam op `/wyk/[wykId]` wanneer die adres leeg is."
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

    try:
        klient = _bou_klient()
    except omgewing.OmgewingFout as fout:
        print(f"Omgewingsfout: {fout}", file=sys.stderr)
        return 1

    try:
        # --- Wyke ---
        wyke_totaal = telling(klient, "stg_wyke")
        wyke_sonder_geom_totaal = telling(klient, "stg_wyke", {"geom": "is.null"})
        wyke_sonder_geom_lys = []
        if wyke_sonder_geom_totaal:
            resp = klient.get("stg_wyke", params={"select": "wyk_id", "geom": "is.null"})
            wyke_sonder_geom_lys = [r["wyk_id"] for r in resp.json()]

        wyk_munis = supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"}, klient=klient)
        munis_vir_prov = supabase.kry_alles("stg_munisipaliteite", {"select": "kode,provinsie"}, klient=klient)
        muni_provinsie = {m["kode"]: m["provinsie"] for m in munis_vir_prov}
        wyke_per_provinsie = tel_per_sleutel([w["muni_kode"] for w in wyk_munis], muni_provinsie)

        try:
            selftoets_rye = supabase.rpc("kontroleer_wyke", {}, klient=klient)
            selftoets = selftoets_rye[0] if isinstance(selftoets_rye, list) else selftoets_rye
        except supabase.SupabaseFout as fout:
            hard_gefaal.append(f"rpc/kontroleer_wyke het misluk: {fout}")
            selftoets = None

        if selftoets is not None and selftoets["selftoets_gefaal"] > 0:
            hard_gefaal.append(
                f"wyk-selftoets: {selftoets['selftoets_gefaal']} wyk(e) gefaal van {selftoets['wyke_totaal']}"
            )

        # --- Munisipaliteite ---
        metro_telling = telling(klient, "stg_munisipaliteite", {"tipe": "eq.metro"})
        plaaslik_telling = telling(klient, "stg_munisipaliteite", {"tipe": "eq.plaaslik"})
        distrik_telling = telling(klient, "stg_munisipaliteite", {"tipe": "eq.distrik"})

        # --- Stemstasies ---
        stasies_totaal = telling(klient, "stg_stemstasies")
        stasie_munis = [r["muni_kode"] for r in supabase.kry_alles("stg_stemstasies", {"select": "muni_kode"}, klient=klient)]
        stasies_per_provinsie = tel_per_sleutel(stasie_munis, muni_provinsie)
        stasies_onbekende_wyk = vind_stasies_onbekende_wyk(klient)
        stasies_leë_adres = vind_stasies_leë_adres(klient)

        # --- Plekke ---
        plekke_totaal = telling(klient, "stg_plekke")
        plek_wyke_totaal = telling(klient, "stg_plek_wyke")
        alias_totaal = telling(klient, "stg_plek_aliasse")
        plekke_sonder_wyk = vind_plekke_sonder_wyk(klient)
        alias_tellings = tel_aliasse(klient)

        # --- 2021 raadsetels ---
        raad_uitslae_totaal = telling(klient, "stg_raad_uitslae_2021")
        raad_grootte_totaal = telling(klient, "stg_raad_grootte_2021")
        uitslae_rye = supabase.kry_alles(
            "stg_raad_uitslae_2021", {"select": "muni_kode,party_naam,setels_totaal"}, klient=klient
        )
        grootte_rye = supabase.kry_alles(
            "stg_raad_grootte_2021", {"select": "muni_kode,raadsgrootte_totaal,onafhanklike_setels"}, klient=klient
        )
        grootte_by_kode = {r["muni_kode"]: r for r in grootte_rye}
        geen_meerderheid = bereken_geen_meerderheid(uitslae_rye, grootte_by_kode)

        # --- Nog nie gelaai nie ---
        kandidate_totaal = telling(klient, "stg_kandidate")
        stembrief_volgorde_totaal = telling(klient, "stg_stembrief_volgorde")

        # --- Diff teen gepubliseerde weergawe ---
        publieke_tellings = {tabel: telling(klient, tabel) for tabel in PUBLIEKE_TABELLE}

        # --- Hard-check: elke gelaaide stg_-tabel moet nie leeg wees nie ---
        gelaaide_tellings = {
            "stg_wyke": wyke_totaal,
            "stg_munisipaliteite": metro_telling + plaaslik_telling + distrik_telling,
            "stg_stemstasies": stasies_totaal,
            "stg_plekke": plekke_totaal,
            "stg_plek_wyke": plek_wyke_totaal,
            "stg_plek_aliasse": alias_totaal,
            "stg_raad_uitslae_2021": raad_uitslae_totaal,
            "stg_raad_grootte_2021": raad_grootte_totaal,
        }
        assert set(gelaaide_tellings) == set(GELAAIDE_TABELLE)
        for tabel, n in gelaaide_tellings.items():
            if n == 0:
                hard_gefaal.append(f"{tabel} is leeg")

        # --- Smoke tests ---
        smoke_resultate = [smoke_toets_plek(klient, naam) for naam in SMOKE_NAME]
        kaapstad_res = next((r for r in smoke_resultate if r["naam"] == "Kaapstad"), {})
        smoke_kaapstad_wyke = kaapstad_res.get("wyke", "?")

    except supabase.SupabaseFout as fout:
        print(f"Kontrole het misluk (Supabase-fout): {fout}", file=sys.stderr)
        return 1
    finally:
        klient.close()

    kontrole_tyd = time.monotonic() - begin

    skryf_verslag(
        tydstempel=tydstempel,
        wyke_totaal=wyke_totaal,
        wyke_sonder_geom_totaal=wyke_sonder_geom_totaal,
        wyke_sonder_geom_lys=wyke_sonder_geom_lys,
        wyke_per_provinsie=wyke_per_provinsie,
        metro_telling=metro_telling,
        plaaslik_telling=plaaslik_telling,
        distrik_telling=distrik_telling,
        stasies_totaal=stasies_totaal,
        stasies_per_provinsie=stasies_per_provinsie,
        stasies_onbekende_wyk=stasies_onbekende_wyk,
        stasies_leë_adres=stasies_leë_adres,
        plekke_totaal=plekke_totaal,
        plek_wyke_totaal=plek_wyke_totaal,
        alias_totaal=alias_totaal,
        plekke_sonder_wyk=plekke_sonder_wyk,
        alias_tellings=alias_tellings,
        raad_uitslae_totaal=raad_uitslae_totaal,
        raad_grootte_totaal=raad_grootte_totaal,
        geen_meerderheid=geen_meerderheid,
        selftoets=selftoets,
        smoke_resultate=smoke_resultate,
        smoke_kaapstad_wyke=smoke_kaapstad_wyke,
        kandidate_totaal=kandidate_totaal,
        stembrief_volgorde_totaal=stembrief_volgorde_totaal,
        publieke_tellings=publieke_tellings,
        kommentaar=kommentaar,
        kontrole_tyd=kontrole_tyd,
    )

    print(f"Wyke: {wyke_totaal} (verwag {VERWAG_WYKE})")
    print(f"Munisipaliteite: {metro_telling + plaaslik_telling} (+ {distrik_telling} distrikte)")
    print(f"Stemstasies: {stasies_totaal}")
    print(f"Plekke: {plekke_totaal}, plek_wyke: {plek_wyke_totaal}, aliasse: {alias_totaal}")
    print(f"Raadsetel-rye: {raad_uitslae_totaal}, rade sonder meerderheid: {len(geen_meerderheid)}")
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
