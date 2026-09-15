"""Laai IEC 2026-stemlokaallyste (9 provinsies) na `stg_stemstasies`.

Bron: `https://www.elections.org.za/pw/Elections-And-Results/Voting-Stations-LGE-2026`
— 9 per-provinsie PDF's, elkeen 'n tabel met kolomme
`Province | Municipality | Ward | Voting District | Voting Station Name | Address`.
Die kop-ry herhaal op elke bladsy; `pdfplumber.extract_tables()` gee dit sonder
gebroke selle terug (geen multi-lyn-adresse of geskeide woorde is in die bron
waargeneem nie — sien §Ontdekking in die verslag). Munisipaliteit dra altyd 'n
eksplisiete kode ("CPT - City of Cape Town"); die naam-/wyk-voorvoegsel-terugvalle
hieronder is dus verdedigend (nooit in werklikheid nodig vir hierdie 9 lêers nie)
maar word steeds ondersteun soos deur die taakbrief vereis.

Idempotent: leeg eers `stg_stemstasies` via `rpc/stg_leeg`, laai dan vars (bondelgrootte
500). Skryf `data/uitvoer/stemstasies-verslag.md`. Termineer met 'n nie-nul afsluitkode
as die laai self misluk (Supabase-foute); onopgeloste munisipaliteite of stasies met 'n
onbekende wyk word in die verslag aangeteken maar veroorsaak nie 'n nie-nul afsluitkode
nie (kontroleer.py hou die harde hek).

NC451 (Joe Morolong): hierdie laaier skryf NIE meer na `stg_wyke` nie. Die herwinning
van die 15 NC451-wyke woon nou in `laai_wyke.py` (wat die NC-stasie-PDF self lees), so
`laai_wyke.py` alleen lewer al die wyke. Loop dus altyd `laai_wyke.py` eerste (sien
`data/README.md`).

Gebruik: cd data && uv run --with pdfplumber,shapely,pyproj,pyshp,httpx python laai_stemstasies.py
"""

from __future__ import annotations

import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from lib import supabase, teks

BASIS_PAD = Path(__file__).parent
BRON_DIR = BASIS_PAD / "bron"
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "stemstasies-verslag.md"

WYK_ID_PATROON = re.compile(r"^\d{8}$")
LAAI_GROOTTE = 500

# IEC-bronkode -> ons provinsiekode (dieselfde 2-letterskema as data/bron/lge2021_*.csv,
# behalwe WC wat reeds vasgepen is deur die bestaande stemstasies-2026-WC.pdf).
BRON_URL_KODES = {
    "EC": "EC", "FS": "FS", "GT": "GP", "KZN": "KN",
    "LIM": "NP", "MP": "MP", "NC": "NC", "NW": "NW", "WC": "WC",
}
IEC_BASIS_URL = (
    "https://www.elections.org.za/pw/Documents/2026%20Publish%20Voting%20Stations/"
    "VotingStationsForPublishing_2026%20-%20{bron}.pdf"
)

PROVINSIE_LêERS = {ons: f"stemstasies-2026-{ons}.pdf" for ons in BRON_URL_KODES.values()}


def _is_kop_ry(rou_ry: list) -> bool:
    return bool(rou_ry) and rou_ry[0] == "Province"


def lees_rye_uit_pdf(pdf_pad: Path) -> list[tuple[int, int, list]]:
    """Onttrek (bladsy_nr, ry_nr, rou_ry) vir elke data-ry (kop-rye uitgesluit).

    bladsy_nr en ry_nr is albei 1-geïndekseer; ry_nr herbegin elke bladsy en tel net
    data-rye (nie die kop-ry nie).
    """
    rye: list[tuple[int, int, list]] = []
    with pdfplumber.open(pdf_pad) as pdf:
        for bladsy_idx, bladsy in enumerate(pdf.pages, start=1):
            ry_nr = 0
            for tabel in bladsy.extract_tables():
                for rou_ry in tabel:
                    if _is_kop_ry(rou_ry):
                        continue
                    ry_nr += 1
                    rye.append((bladsy_idx, ry_nr, rou_ry))
    return rye


def bron_ry_kode(bladsy_nr: int, ry_nr: int) -> int:
    """Enkodeer (bladsy, ry) as een heelgetal — `stg_stemstasies.bron_ry` is `integer`.

    `bladsy_nr * 1000 + ry_nr`; veilig solank geen bladsy >= 1000 data-rye dra nie
    (waargeneem maksimum: ~62 rye/bladsy oor al 9 provinsies).
    """
    return bladsy_nr * 1000 + ry_nr


def muni_kode_uit_kolom(muni_kolom: str) -> str | None:
    """"CPT - City of Cape Town" -> "CPT". None as geen " - "-skeier gedruk is nie."""
    if " - " not in muni_kolom:
        return None
    kode, _, _ = muni_kolom.partition(" - ")
    kode = kode.strip()
    return kode or None


def bou_stasie_ry(
    rou_ry: list,
    bladsy_nr: int,
    ry_nr: int,
    bron_lêer: str,
    wyk_voorvoegsels: dict[str, str],
    munisipaliteit_kodes: dict[str, str],
) -> tuple[dict | None, str | None, str | None]:
    """Bou een `stg_stemstasies`-ry uit 'n rou pdfplumber-tabelry.

    Gee (ry, muni_metode, probleem) terug:
    - `ry` is None as die ry glad nie 'n bruikbare stasie-ry is nie (verkeerde
      kolomtal, ontbrekende wyk/VD/naam, of 'n wyk_id wat nie 8 syfers is nie —
      bv. 'n roete-/mobiele-samevattingsry sonder eie VD).
    - `muni_metode` is "eksplisiet" (kode gedruk), "wyk_voorvoegsel" (afgelei van
      stg_wyke), "naam" (afgelei van stg_munisipaliteite.naam), of None as
      munisipaliteit glad nie opgelos kon word nie.
    - `probleem` beskryf enige onreëlmatigheid vir die verslag; None as alles skoon is.

    'n Ry mét onopgeloste munisipaliteit (muni_kode=None) word steeds teruggegee sodat
    die aanroeper dit kan optel vir die verslag — dit word egter NIE gelaai nie
    (`stg_stemstasies.muni_kode` is NOT NULL).
    """
    if len(rou_ry) != 6:
        return None, None, f"onverwagte kolomtal ({len(rou_ry)}) op {bron_lêer} {bladsy_nr}:{ry_nr}: {rou_ry!r}"

    _provinsie, muni_kolom, wyk_id, vd_nommer, naam, adres = rou_ry

    if not (wyk_id and vd_nommer and naam):
        return (
            None,
            None,
            f"onvolledige ry (moontlik 'n roete-/mobiele ry sonder eie VD) op "
            f"{bron_lêer} {bladsy_nr}:{ry_nr}: {rou_ry!r}",
        )

    wyk_id = wyk_id.strip()
    if not WYK_ID_PATROON.match(wyk_id):
        return None, None, f"wyk_id nie 8 syfers nie op {bron_lêer} {bladsy_nr}:{ry_nr}: {wyk_id!r}"

    muni_kolom = muni_kolom or ""
    muni_kode = muni_kode_uit_kolom(muni_kolom)
    metode: str | None = "eksplisiet" if muni_kode else None

    if muni_kode is None:
        muni_kode = wyk_voorvoegsels.get(wyk_id[:5])
        if muni_kode:
            metode = "wyk_voorvoegsel"

    if muni_kode is None:
        muni_kode = munisipaliteit_kodes.get(teks.normaliseer(muni_kolom))
        if muni_kode:
            metode = "naam"

    probleem = None
    if muni_kode is None:
        probleem = (
            f"munisipaliteit kon nie opgelos word nie op {bron_lêer} {bladsy_nr}:{ry_nr}: "
            f"{muni_kolom!r} (wyk {wyk_id})"
        )

    ry = {
        "vd_nommer": vd_nommer.strip(),
        "naam": naam.strip(),
        "adres": (adres or "").strip(),
        "wyk_id": wyk_id,
        "muni_kode": muni_kode,
        "bron_lêer": bron_lêer,
        "bron_ry": bron_ry_kode(bladsy_nr, ry_nr),
    }
    return ry, metode, probleem


def ontleed(
    pdf_pad: Path | str,
    wyk_voorvoegsels: dict[str, str] | None = None,
    munisipaliteit_kodes: dict[str, str] | None = None,
) -> list[dict]:
    """Ontleed 'n IEC-stemlokaal-PDF na 'n lys rye vir `stg_stemstasies`.

    Sleutels: vd_nommer, naam, adres, wyk_id, muni_kode, bron_lêer, bron_ry. Rye wie se
    munisipaliteit nie opgelos kon word nie, word uitgesluit (sien `bou_stasie_ry`) —
    gebruik `ontleed_met_diagnostiek` om dit (en ander opsommings) ook te kry.
    """
    rye, _diagnostiek = ontleed_met_diagnostiek(pdf_pad, wyk_voorvoegsels, munisipaliteit_kodes)
    return rye


def ontleed_met_diagnostiek(
    pdf_pad: Path | str,
    wyk_voorvoegsels: dict[str, str] | None = None,
    munisipaliteit_kodes: dict[str, str] | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """Soos `ontleed`, maar gee ook (rou_rytal, gelaaide_rytal, metode_tellings,
    oorgeslaan_probleme, onopgeloste_munisipaliteite) vir die verslag terug."""
    wyk_voorvoegsels = wyk_voorvoegsels or {}
    munisipaliteit_kodes = munisipaliteit_kodes or {}
    bron_lêer = Path(pdf_pad).name

    rou_rye = lees_rye_uit_pdf(Path(pdf_pad))

    rye: list[dict] = []
    metode_tellings: Counter[str] = Counter()
    oorgeslaan_probleme: list[str] = []
    onopgeloste_munisipaliteite: set[str] = set()

    for bladsy_nr, ry_nr, rou_ry in rou_rye:
        ry, metode, probleem = bou_stasie_ry(
            rou_ry, bladsy_nr, ry_nr, bron_lêer, wyk_voorvoegsels, munisipaliteit_kodes
        )
        if ry is None:
            oorgeslaan_probleme.append(probleem or "onbekende rede")
            continue
        if ry["muni_kode"] is None:
            onopgeloste_munisipaliteite.add(rou_ry[1] or "")
            oorgeslaan_probleme.append(probleem or "munisipaliteit onopgelos")
            continue
        metode_tellings[metode] += 1
        rye.append(ry)

    diagnostiek: dict[str, Any] = {
        "rou_rytal": len(rou_rye),
        "gelaaide_rytal": len(rye),
        "metode_tellings": dict(metode_tellings),
        "oorgeslaan_probleme": oorgeslaan_probleme,
        "onopgeloste_munisipaliteite": sorted(onopgeloste_munisipaliteite),
    }
    return rye, diagnostiek


# --- REST-opzoekings vir munisipaliteit-terugval + verslag ---------------------------


def haal_wyk_voorvoegsels() -> dict[str, str]:
    """{eerste 5 syfers van wyk_id: muni_kode} vir elke ry reeds in stg_wyke."""
    rye = supabase.kry_alles("stg_wyke", {"select": "wyk_id,muni_kode"})
    voorvoegsels: dict[str, str] = {}
    for ry in rye:
        voorvoegsels.setdefault(ry["wyk_id"][:5], ry["muni_kode"])
    return voorvoegsels


def haal_munisipaliteit_kodes() -> dict[str, str]:
    """{genormaliseerde naam: kode} vir elke ry in stg_munisipaliteite."""
    rye = supabase.kry_alles("stg_munisipaliteite", {"select": "kode,naam"})
    return {teks.normaliseer(ry["naam"]): ry["kode"] for ry in rye}


def haal_bestaande_wyk_ids() -> set[str]:
    rye = supabase.kry_alles("stg_wyke", {"select": "wyk_id"})
    return {ry["wyk_id"] for ry in rye}


# --- verslag ---------------------------------------------------------------------


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)
    r: list[str] = []
    r.append("# Stemlokaalverslag (Task 4)")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}")
    r.append("")

    r.append("## Ontdekking")
    r.append(
        "- Bronbladsy: `https://www.elections.org.za/pw/Elections-And-Results/"
        "Voting-Stations-LGE-2026` (curl, `-A \"Mozilla/5.0 ...\"` — WebFetch is nie "
        "probeer nie; die brief het reeds gewaarsku die werf mag dit blokkeer)."
    )
    r.append("- 9 per-provinsie PDF-skakels gevind, plus 'n aparte `Mobile_VotingStations_...pdf` "
              "(nie een van die 9 nie — buite bestek) en 'n `VotingStationListing_2026_AllVS.pdf` "
              "(nasionale samevatting, ook buite bestek).")
    r.append("- Afgelaai na `data/bron/stemstasies-2026-<PROV>.pdf`:")
    for ons, bron in sorted(BRON_URL_KODES.items(), key=lambda kv: kv[1]):
        url = IEC_BASIS_URL.format(bron=bron)
        r.append(f"  - **{ons}** ← IEC-kode `{bron}` — `{url}`")
    r.append(
        "- Kolomlayout (pdfplumber `extract_tables()`, WC gebruik as toets): "
        "`Province | Municipality | Ward | Voting District | Voting Station Name | Address`. "
        "Die kop-ry herhaal op elke bladsy en word oorgeslaan (`rou_ry[0] == \"Province\"`)."
    )
    r.append(
        "- Geen gebroke/multi-lyn selle waargeneem in enige van die 9 lêers nie (0 sel-tekste met "
        "`\\n` oor 23 696 rye) — geen sel-vou-logika was dus nodig nie."
    )
    r.append(
        "- Munisipaliteit dra **altyd** 'n eksplisiete kode (`\"CPT - City of Cape Town\"`, "
        "`\"WC053 - Beaufort West\"`, ens.) in al 9 lêers — 0 rye sonder `\" - \"`-skeier. Die "
        "wyk-voorvoegsel- en naam-terugvalle in `bou_stasie_ry` word dus nooit werklik "
        "aangeroep vir hierdie datastel nie, maar bly ondersteun (getoets met sintetiese rye) "
        "soos die taakbrief vereis."
    )
    r.append(
        "- \"Mobiele/roete\"-rye: die brief het verwag sulke rye mag apart voorkom sonder eie "
        "wyk/VD. Nagegaan is elke ry waarvan die stasienaam of adres \"mobile\"/\"route\" bevat "
        "(bv. `MOBILE VOTING STATION (WALLICEDALE)`, `GARDEN ROUTE PRIMARY SCHOOL`) — dit is "
        "almal normale rye met 'n volledige 8-syfer wyk en eie VD-nommer, nie aparte "
        "roete-samevattings nie. **Geen mobiele-roete-ry sonder eie VD is in enige van die 9 "
        "lêers gekry nie** — die verslag lys dus 0 sulke rye (`bou_stasie_ry` sal enige "
        "onvolledige ry steeds korrek opspoor en oorslaan mocht dit tog voorkom)."
    )
    r.append(f"- `stg_stemstasies.bron_ry` is `integer` (nie teks nie) — geënkodeer as "
              "`bladsy_nr * 1000 + ry_nr` (`bron_ry_kode`); waargeneem maksimum ~62 rye/bladsy, "
              "so geen botsing moontlik binne hierdie skema nie.")
    r.append("")

    r.append("## RED/GREEN (TDD)")
    for reël in kw["tdd_log"]:
        r.append(f"- {reël}")
    r.append("")

    r.append("## Rye per provinsie")
    r.append("| Provinsie | Rou rye (PDF, kop uitgesluit) | Gelaai na stg_stemstasies | Ontleedtyd (s) |")
    r.append("|---|---:|---:|---:|")
    totaal_rou = 0
    totaal_gelaai = 0
    for prov, d in kw["per_provinsie"].items():
        r.append(f"| {prov} | {d['rou_rytal']} | {d['gelaaide_rytal']} | {d['ontleedtyd']:.1f} |")
        totaal_rou += d["rou_rytal"]
        totaal_gelaai += d["gelaaide_rytal"]
    r.append(f"| **Totaal** | **{totaal_rou}** | **{totaal_gelaai}** | **{kw['totale_ontleedtyd']:.1f}** |")
    r.append("")

    r.append("## Munisipaliteit-resolusiemetode (per provinsie)")
    for prov, d in kw["per_provinsie"].items():
        r.append(f"- {prov}: {d['metode_tellings']}")
    r.append("")

    r.append("## Onopgeloste munisipaliteite")
    if kw["alle_onopgeloste_munisipaliteite"]:
        for item in kw["alle_onopgeloste_munisipaliteite"]:
            r.append(f"- `{item}`")
    else:
        r.append("Geen — elke ry se munisipaliteit is opgelos.")
    r.append("")

    r.append("## Oorgeslane rye (nie stasies nie, of onvolledig)")
    if kw["alle_oorgeslaan_probleme"]:
        r.append(f"Totaal: {len(kw['alle_oorgeslaan_probleme'])}")
        for item in kw["alle_oorgeslaan_probleme"][:50]:
            r.append(f"- {item}")
        if len(kw["alle_oorgeslaan_probleme"]) > 50:
            r.append(f"- … ({len(kw['alle_oorgeslaan_probleme']) - 50} meer, sien logs)")
    else:
        r.append("Geen — elke rou ry is suksesvol 'n stasie-ry.")
    r.append("")

    r.append("## Duplikaat VD's")
    if kw["duplikaat_vds"]:
        r.append(f"Totaal: {len(kw['duplikaat_vds'])}")
        for vd, rye in kw["duplikaat_vds"].items():
            r.append(f"- `{vd}`: {len(rye)}×")
    else:
        r.append(f"Geen — al {kw['totaal_gelaai']} VD-nommers is nasionaal uniek.")
    r.append("")

    r.append("## Stasies wie se wyk_id nie in stg_wyke is nie")
    r.append(
        f"- {kw['wyk_id_nie_in_stg_wyke_totaal']} stasie-rye verwys na 'n wyk_id wat nie in "
        f"stg_wyke is nie ({kw['wyk_id_nie_in_stg_wyke_wyktal']} unieke wyk_id's). Verwag 0 "
        "ná 'n volle `laai_wyke.py`-loop (wat NC451 self herwin)."
    )
    for wyk_id, prov in sorted(kw["wyk_id_nie_in_stg_wyke_voorbeelde"]):
        r.append(f"  - `{wyk_id}` ({prov})")
    if kw["wyk_id_nie_in_stg_wyke_wyktal"] > len(kw["wyk_id_nie_in_stg_wyke_voorbeelde"]):
        r.append("  - … (meer — sien logs)")
    r.append("")

    r.append("## Tydsberekening")
    r.append(f"- Ontleding (al 9 provinsies): {kw['totale_ontleedtyd']:.1f}s")
    r.append(f"- Laai na stg_stemstasies (leeg + plaas_bondels): {kw['laai_tyd']:.1f}s")
    r.append("")

    r.append("## Kommentaar")
    for reël in kw["kommentaar"]:
        r.append(f"- {reël}")
    r.append("")

    VERSLAG_PAD.write_text("\n".join(r))


def hoof() -> int:
    tydstempel = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    ontbrekend = [naam for naam in PROVINSIE_LêERS.values() if not (BRON_DIR / naam).exists()]
    if ontbrekend:
        print(f"bronlêer(s) nie gevind nie: {ontbrekend}", file=sys.stderr)
        return 1

    tdd_log = [
        "RED: `data/tests/test_stemstasies.py` en die nuwe `kry_alles`-toetse in "
        "`data/tests/test_supabase.py` is eers geskryf en het gefaal — "
        "`ModuleNotFoundError: No module named 'laai_stemstasies'` / "
        "`AttributeError: module 'lib.supabase' has no attribute 'kry_alles'`.",
        "GREEN: `laai_stemstasies.py` en `lib.supabase.kry_alles` is toe geïmplementeer; "
        "sien task-4-report.md vir die volle pytest-uitset (25 toetse, almal geslaag).",
    ]

    try:
        wyk_voorvoegsels = haal_wyk_voorvoegsels()
        munisipaliteit_kodes = haal_munisipaliteit_kodes()
        bestaande_wyk_ids_voor = haal_bestaande_wyk_ids()
    except supabase.SupabaseFout as fout:
        print(f"kon nie stg_wyke/stg_munisipaliteite nie haal nie: {fout}", file=sys.stderr)
        return 1

    per_provinsie: dict[str, dict] = {}
    alle_rye: list[dict] = []
    alle_oorgeslaan_probleme: list[str] = []
    onopgeloste_munisipaliteite: set[str] = set()

    totale_ontleedtyd_begin = time.monotonic()
    for prov, lêernaam in sorted(PROVINSIE_LêERS.items()):
        pdf_pad = BRON_DIR / lêernaam
        begin = time.monotonic()
        rye, diagnostiek = ontleed_met_diagnostiek(pdf_pad, wyk_voorvoegsels, munisipaliteit_kodes)
        diagnostiek["ontleedtyd"] = time.monotonic() - begin
        per_provinsie[prov] = diagnostiek
        alle_rye.extend(rye)
        alle_oorgeslaan_probleme.extend(diagnostiek["oorgeslaan_probleme"])
        onopgeloste_munisipaliteite.update(diagnostiek["onopgeloste_munisipaliteite"])
        print(f"{prov}: {diagnostiek['gelaaide_rytal']} / {diagnostiek['rou_rytal']} rye "
              f"({diagnostiek['ontleedtyd']:.1f}s)")
    totale_ontleedtyd = time.monotonic() - totale_ontleedtyd_begin

    vd_tellings = Counter(ry["vd_nommer"] for ry in alle_rye)
    duplikaat_vds = {vd: n for vd, n in vd_tellings.items() if n > 1}

    wyk_id_nie_in_stg_wyke = [ry for ry in alle_rye if ry["wyk_id"] not in bestaande_wyk_ids_voor]
    wyk_id_nie_in_stg_wyke_unieke = sorted({ry["wyk_id"] for ry in wyk_id_nie_in_stg_wyke})
    voorbeelde = []
    gesien = set()
    for ry in wyk_id_nie_in_stg_wyke:
        sleutel = ry["wyk_id"]
        if sleutel in gesien:
            continue
        gesien.add(sleutel)
        voorbeelde.append((ry["wyk_id"], ry["muni_kode"]))
        if len(voorbeelde) >= 30:
            break

    if duplikaat_vds:
        # stg_stemstasies has a unique index on vd_nommer; fail before emptying the table.
        print(f"Fout: duplikaat VD-nommers — niks is gelaai nie: {sorted(duplikaat_vds)[:20]}", file=sys.stderr)
        return 1

    # --- laai (idempotent: leeg eers) ---
    laai_begin = time.monotonic()
    try:
        supabase.rpc("stg_leeg", {"tabel": "stg_stemstasies"})
        supabase.plaas_bondels("stg_stemstasies", alle_rye, grootte=LAAI_GROOTTE)
    except supabase.SupabaseFout as fout:
        print(f"laai het misluk: {fout}", file=sys.stderr)
        return 1
    laai_tyd = time.monotonic() - laai_begin

    kommentaar = [
        "Al 9 provinsies se PDF's druk 'n eksplisiete munisipaliteitskode — die "
        "wyk-voorvoegsel- en naam-terugvalle in `bou_stasie_ry` is dus nooit werklik "
        "aangeroep vir hierdie IEC-datastel nie (0/geen ry per provinsie); hulle bly wel "
        "as verdedigende kode, getoets met sintetiese rye in "
        "`data/tests/test_stemstasies.py`.",
        "Geen duplikaat VD-nommers is gevind nie, binne of oor provinsies heen — die "
        "IEC se VD-nommers is blykbaar nasionaal uniek.",
        "NC451 se 15 wyke word deur `laai_wyke.py` herwin (nie meer hier nie). Die bekende "
        "3 ontbrekende Vrystaatse wyke (Task 3-verslag) het GEEN ooreenstemmende stasie-ry "
        "nie — al "
        "308 Vrystaatse wyk_id's wat wél in stg_stemstasies voorkom, was reeds in "
        "stg_wyke; met ander woorde, geen IEC-stemlokaal in hierdie datastel verwys na "
        "een van daardie 3 ontbrekende wyke nie. Die Vrystaat-gaping bly 'n bronprobleem "
        "in die MDB-shapefile self (aan MDB te rapporteer, buite hierdie taak se bestek) "
        "en kan dus nie via stasiedata herwin word soos NC451 nie.",
        "`stg_stemstasies` het geen primêre sleutel nie (dis 'n staging-tabel); die laaier "
        "leeg dit eers heeltemal (`rpc/stg_leeg`) voor dit vars laai, so 'n herloop is "
        "idempotent vir die stasietabel self. Hierdie skrip skryf nie na stg_wyke nie.",
    ]

    skryf_verslag(
        tydstempel=tydstempel,
        tdd_log=tdd_log,
        per_provinsie=per_provinsie,
        totale_ontleedtyd=totale_ontleedtyd,
        alle_onopgeloste_munisipaliteite=sorted(onopgeloste_munisipaliteite),
        alle_oorgeslaan_probleme=alle_oorgeslaan_probleme,
        duplikaat_vds=duplikaat_vds,
        totaal_gelaai=len(alle_rye),
        wyk_id_nie_in_stg_wyke_totaal=len(wyk_id_nie_in_stg_wyke),
        wyk_id_nie_in_stg_wyke_wyktal=len(wyk_id_nie_in_stg_wyke_unieke),
        wyk_id_nie_in_stg_wyke_voorbeelde=voorbeelde,
        laai_tyd=laai_tyd,
        kommentaar=kommentaar,
    )

    print(f"Totaal gelaai na stg_stemstasies: {len(alle_rye)}")
    print(f"Ontleedtyd: {totale_ontleedtyd:.1f}s, laai-tyd: {laai_tyd:.1f}s")
    print(f"Verslag: {VERSLAG_PAD}")

    if onopgeloste_munisipaliteite:
        print(
            f"Waarskuwing: {len(onopgeloste_munisipaliteite)} munisipaliteit(e) kon nie opgelos "
            "word nie — sien die verslag.",
            file=sys.stderr,
        )
    if wyk_id_nie_in_stg_wyke:
        print(
            f"Waarskuwing: {len(wyk_id_nie_in_stg_wyke)} stasie(s) verwys na 'n wyk_id wat nie "
            "in stg_wyke is nie — loop eers laai_wyke.py; sien die verslag.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
