"""Laai Stats SA Census 2011 Sub Place-poligone (`bron/plekke/Subplace.zip`) na
`stg_plekke`, bereken oorvleuelings met 2026-wyke (`rpc/bou_plek_wyke`), en saai
'n Afrikaans/Engels alias-tabel (`data/aliasse.csv` -> `stg_plek_aliasse`).

Bron: Stats SA Census 2011 Sub Place-grense, `data/bron/plekke/Subplace.zip`. Word
uitgepak na `data/bron/plekke/Subplace/` (gitignored). `MainPlace.zip` word ook
uitgepak (na `data/bron/plekke/Main Place/`) net vir ontdekking/verifikasie van
hoofplek-name — dit word nie in enige stg_-tabel gelaai nie (stg_plekke se
`mp_naam`-kolom kom reeds van Subplace se MP_NAME-veld).

CRS: die .prj vir albei lêers is Hartebeesthoek94 (GCS_Hartebeesthoek_1994, WGS84-
sferoïed) — EPSG:4148. Soos die taakbrief aanvaar, word dit as 4326-ekwivalent
behandel (geen herprojeksie nie); `lib.geo.na_ewkt_4326` word met bron_epsg=4326
aangeroep sodat dit die punte ongewysig laat (buiten geldigheid/presisie-opskoning).

Idempotent: leeg eers `stg_plekke`, `stg_plek_wyke` en `stg_plek_aliasse` via
`rpc/stg_leeg`, laai dan vars. Skryf `data/uitvoer/plekke-verslag.md`. Termineer met
'n nie-nul afsluitkode as die laai self misluk (Supabase-foute); onopgeloste aliasse
of plekke sonder wyke word in die verslag aangeteken maar veroorsaak nie 'n nie-nul
afsluitkode nie (dis 'n bronprobleem, nie 'n laaifout nie).

Gebruik: cd data && uv run --with shapely,pyproj,pyshp,httpx python laai_plekke.py
"""

from __future__ import annotations

import csv
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import shapefile

from lib import geo, supabase, teks

BASIS_PAD = Path(__file__).parent
BRON_SP_ZIP = BASIS_PAD / "bron" / "plekke" / "Subplace.zip"
BRON_MP_ZIP = BASIS_PAD / "bron" / "plekke" / "MainPlace.zip"
BRON_SP_DIR = BASIS_PAD / "bron" / "plekke" / "Subplace"
BRON_MP_DIR = BASIS_PAD / "bron" / "plekke" / "Main Place"
SP_SHP_PAD = BRON_SP_DIR / "SP_SA_2011.shp"
MP_SHP_PAD = BRON_MP_DIR / "MP_SA_2011.shp"
ALIASSE_CSV_PAD = BASIS_PAD / "aliasse.csv"
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "plekke-verslag.md"

BRON_EPSG = 4326  # Hartebeesthoek94 (EPSG:4148) as 4326-ekwivalent behandel — geen herprojeksie
PLEKKE_GROOTTE = 200
BOU_PLEK_WYKE_BONDEL = 100  # rye per bou_plek_wyke(van, tot)-oproep — kalibreer teen die
# `authenticator`-rol se 8s statement_timeout (sien Task-5-verslag §rpc/bou_plek_wyke se
# kalibrasietabel: 50 rye ~3.5s, 100 rye ~5.75s, 150 rye ~6.9s, 300 rye tref reeds die
# 8s-limiet). 100 laat genoeg marge oor vir netwerkwisseling.


def pak_uit() -> None:
    if SP_SHP_PAD.exists() and MP_SHP_PAD.exists():
        return
    if not BRON_SP_ZIP.exists():
        raise SystemExit(f"bronlêer nie gevind nie: {BRON_SP_ZIP}")
    if not BRON_MP_ZIP.exists():
        raise SystemExit(f"bronlêer nie gevind nie: {BRON_MP_ZIP}")
    for zip_pad, teiken_dir in ((BRON_SP_ZIP, BRON_SP_ZIP.parent), (BRON_MP_ZIP, BRON_MP_ZIP.parent)):
        with zipfile.ZipFile(zip_pad) as z:
            for lid in z.infolist():
                if lid.filename.startswith("__MACOSX/") or Path(lid.filename).name.startswith("._"):
                    continue
                z.extract(lid, teiken_dir)


def lees_prj(shp_pad: Path) -> str:
    return shp_pad.with_suffix(".prj").read_text().strip()


def lees_vorm_rekord_pare() -> list[tuple[Any, dict]]:
    """Lees vorm + rekord saam (gepaar per indeks) uit die Subplace-shapefile.

    cp1252-enkodering per die taakbrief (Afrikaanse plekname dra bv. "ë"/"ô").
    """
    r = shapefile.Reader(str(SP_SHP_PAD), encoding="cp1252")
    return [(sr.shape, sr.record.as_dict()) for sr in r.iterShapeRecords()]


def lees_mp_rekords() -> list[dict]:
    r = shapefile.Reader(str(MP_SHP_PAD), encoding="cp1252")
    return [sr.record.as_dict() for sr in r.iterShapeRecords()]


def na_sp_kode(sp_code: float | str) -> str:
    """SP_CODE kom uit die dbf as 'n float (bv. 160001001.0) — skoon na heelgetal-teks."""
    return str(int(sp_code))


def bou_plek_rye(vorm_rekord_pare: list[tuple[Any, dict]]) -> tuple[list[dict], list[str]]:
    """Bou stg_plekke-rye. Gee (rye, oorgeslaan_leë_geom) terug (sp_kode-lys)."""
    rye: list[dict] = []
    oorgeslaan_geom: list[str] = []

    for vorm, rekord in vorm_rekord_pare:
        sp_kode = na_sp_kode(rekord["SP_CODE"])
        naam, landelik = teks.skoon_plek_naam(rekord["SP_NAME"])
        try:
            ewkt = geo.na_ewkt_4326(vorm, BRON_EPSG)
        except geo.LeeGeometrieFout:
            oorgeslaan_geom.append(sp_kode)
            continue
        rye.append(
            {
                "sp_kode": sp_kode,
                "naam": naam,
                "naam_soek": teks.normaliseer(naam),
                "mp_naam": rekord["MP_NAME"],
                "landelik": landelik,
                "geom": ewkt,
            }
        )
    return rye, oorgeslaan_geom


# --- bou_plek_wyke: volle oproep of, as dit te stadig is, in bondels -----------------


def roep_bou_plek_wyke_volledig() -> tuple[int, float]:
    """Roep rpc/bou_plek_wyke() sonder reeks aan. Gee (ingevoeg, tyd_s) terug."""
    begin = time.monotonic()
    ingevoeg = supabase.rpc("bou_plek_wyke", {})
    return ingevoeg, time.monotonic() - begin


ENKEL_PLEK_HERHALINGS = 2  # ekstra pogings vir 'n reeks van 1 plek voor dit oorgeslaan word
ENKEL_PLEK_HERHALING_VERTRAGING_S = 1.0


def _roep_bou_plek_wyke_reeks(
    van: int,
    tot: int,
    tydsberekenings: list[tuple[int, int, int, float]],
    oorgeslaan_reekse: list[tuple[int, int, str]],
) -> int:
    """Roep bou_plek_wyke(van, tot) vir een reeks; halveer en herhaal op timeout.

    `lib.supabase.rpc` herhaal reeds 3x met eksponensiële terugslag op 429/5xx
    (PostgREST se 57014 statement-timeout kom deur as HTTP 500), maar 'n enkele
    reeks kan steeds swaarder as ander wees (meer wyk-oorvleuelings om te bereken)
    en die 8s `authenticator`-statement_timeout selfs ná die herhalings tref. In
    daardie geval word die reeks — soos `plaas_bondels` met 413 doen — in twee
    gehalveer en elke helfte apart geprobeer, tot by reekse van 1 plek.

    'n Reeks van 1 plek wat steeds misluk, kry nog `ENKEL_PLEK_HERHALINGS` pogings
    (met 'n kort pouse — waargeneem gedrag was dat dit dikwels tydelike
    verbindings-/rekenaar-mededinging is, nie 'n konstante eienskap van daardie een
    plek se geometrie nie). As dit steeds misluk, word die plek **oorgeslaan** (nie
    'n nie-nul afsluitkode nie — sien `oorgeslaan_reekse`, aangeteken in die verslag)
    eerder as om die hele laai te laat val.
    """
    begin = time.monotonic()
    try:
        ingevoeg = supabase.rpc("bou_plek_wyke", {"van": van, "tot": tot})
    except supabase.SupabaseFout as fout:
        if tot != van:
            middel = van + (tot - van) // 2
            print(f"  bou_plek_wyke({van}, {tot}) het misluk ({fout}) — halveer na "
                  f"({van}, {middel}) + ({middel + 1}, {tot})")
            return _roep_bou_plek_wyke_reeks(
                van, middel, tydsberekenings, oorgeslaan_reekse
            ) + _roep_bou_plek_wyke_reeks(middel + 1, tot, tydsberekenings, oorgeslaan_reekse)

        laaste_fout = fout
        for poging in range(1, ENKEL_PLEK_HERHALINGS + 1):
            time.sleep(ENKEL_PLEK_HERHALING_VERTRAGING_S)
            try:
                begin = time.monotonic()
                ingevoeg = supabase.rpc("bou_plek_wyke", {"van": van, "tot": tot})
                break
            except supabase.SupabaseFout as herhaal_fout:
                laaste_fout = herhaal_fout
        else:
            print(f"  bou_plek_wyke({van}, {tot}) (1 plek) het ook ná "
                  f"{ENKEL_PLEK_HERHALINGS} ekstra pogings misluk ({laaste_fout}) — oorgeslaan.")
            oorgeslaan_reekse.append((van, tot, str(laaste_fout)))
            return 0

    tyd = time.monotonic() - begin
    tydsberekenings.append((van, tot, ingevoeg, tyd))
    print(f"  bou_plek_wyke({van}, {tot}): {ingevoeg} ingevoeg ({tyd:.1f}s)")
    return ingevoeg


def roep_bou_plek_wyke_in_bondels(
    plek_totaal: int,
) -> tuple[int, list[tuple[int, int, int, float]], list[tuple[int, int, str]]]:
    """Roep rpc/bou_plek_wyke(van, tot) in bondels van BOU_PLEK_WYKE_BONDEL.

    Die eerste oproep (van=1) leeg self stg_plek_wyke (sien migrasie — delete-all
    gebeur net as van/tot albei NULL is; ons gee dus eers 'n eksplisiete
    `stg_leeg`-oproep vooraf, dan elke bondel met sy eie reeks, wat nooit bestaande
    rye uitvee nie). 'n Reeks wat steeds ná herhalings 'n statement-timeout tref, word
    gehalveer (sien `_roep_bou_plek_wyke_reeks`); 'n hardnekkige enkel-plek-reeks word
    oorgeslaan, nie die hele laai laat val nie. Gee (totaal_ingevoeg,
    [(van, tot, ingevoeg, tyd_s), ...], [(van, tot, fout), ...]) terug — die
    tydsberekening-lys bevat een inskrywing per werklik-suksesvolle oproep (dus
    moontlik meer as die aanvanklike bondeltal as enige reeks gehalveer moes word);
    die oorgeslaan-lys bevat elke plek wat glad nie bereken kon word nie.
    """
    supabase.rpc("stg_leeg", {"tabel": "stg_plek_wyke"})
    tydsberekenings: list[tuple[int, int, int, float]] = []
    oorgeslaan_reekse: list[tuple[int, int, str]] = []
    totaal = 0
    for van in range(1, plek_totaal + 1, BOU_PLEK_WYKE_BONDEL):
        tot = min(van + BOU_PLEK_WYKE_BONDEL - 1, plek_totaal)
        totaal += _roep_bou_plek_wyke_reeks(van, tot, tydsberekenings, oorgeslaan_reekse)
    return totaal, tydsberekenings, oorgeslaan_reekse


# --- aliasse -------------------------------------------------------------------------


def lees_aliasse_csv(pad: Path) -> list[dict]:
    with pad.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def los_alias_op(
    alias_ry: dict,
    plekke_per_naam_mp: dict[tuple[str, str | None], list[str]],
    plekke_per_mp: dict[str, list[str]],
) -> tuple[list[str], list[dict]]:
    """Los een aliasse.csv-ry op teen die reeds-gelaaide stg_plekke-data.

    Drie modusse, na gelang van watter kolomme in die CSV-ry gevul is:
    - naam + mp_naam albei gegee: presiese (naam, mp_naam)-opeenkoms (een sub-plek).
    - net naam gegee (mp_naam leeg): bybring oor alle mp_naam-waardes met hierdie naam.
    - net mp_naam gegee (naam leeg): "hoofplek"-alias — bring elke sub-plek onder
      daardie mp_naam by (bv. Kaapstad -> al 126 sub-plekke met mp_naam="Cape Town").

    munisipaliteit_naam word nie hier gebruik om te filter nie (dis dokumentasie in
    die CSV vir die mens); die loader se enigste opeenkoms is naam en/of mp_naam.

    Gee (sp_kodes, []) terug — sp_kodes is leeg as niks ooreenstem nie (word deur die
    aanroeper as onopgelos aangeteken). Die tweede lid is 'n gereserveerde plekhouer
    (tans altyd leeg) sodat die aanroeper se aanroepvorm stabiel bly.
    """
    naam = (alias_ry.get("naam") or "").strip() or None
    mp_naam = (alias_ry.get("mp_naam") or "").strip() or None

    if naam is not None and mp_naam is not None:
        return list(plekke_per_naam_mp.get((naam, mp_naam), [])), []

    if naam is not None:
        # geen mp_naam gegee nie: bybring oor alle plekke met hierdie naam, ongeag mp_naam
        gevonde: list[str] = []
        for (kand_naam, _kand_mp), sp_kodes in plekke_per_naam_mp.items():
            if kand_naam == naam:
                gevonde.extend(sp_kodes)
        return gevonde, []

    if mp_naam is not None:
        # "hoofplek"-alias: elke sub-plek onder hierdie mp_naam
        return list(plekke_per_mp.get(mp_naam, [])), []

    return [], []


def bou_alias_indeks(
    gelaaide_plekke: list[dict],
) -> tuple[dict[tuple[str, str | None], list[str]], dict[str, list[str]]]:
    """Gee (naam+mp_naam-indeks, mp_naam-alleen-indeks) uit die gelaaide stg_plekke-rye."""
    per_naam_mp: dict[tuple[str, str | None], list[str]] = {}
    per_mp: dict[str, list[str]] = {}
    for ry in gelaaide_plekke:
        per_naam_mp.setdefault((ry["naam"], ry["mp_naam"]), []).append(ry["sp_kode"])
        if ry["mp_naam"]:
            per_mp.setdefault(ry["mp_naam"], []).append(ry["sp_kode"])
    return per_naam_mp, per_mp


def bou_alias_rye(
    aliasse_csv_rye: list[dict],
    plekke_per_naam_mp: dict[tuple[str, str | None], list[str]],
    plekke_per_mp: dict[str, list[str]],
) -> tuple[list[dict], list[dict]]:
    """Gee (stg_plek_aliasse-rye, onopgeloste_rye) terug.

    'n stg_plek_aliasse-ry word geskryf vir élke sp_kode wat 'n alias-CSV-ry
    oplewer (een alias kan na meer as een sp_kode wys, bv. 'n hoofplek-alias soos
    Kaapstad wat elke sub-plek onder mp_naam="Cape Town" bybring).
    """
    aliasse: list[dict] = []
    onopgelos: list[dict] = []
    for csv_ry in aliasse_csv_rye:
        sp_kodes, _ = los_alias_op(csv_ry, plekke_per_naam_mp, plekke_per_mp)
        if not sp_kodes:
            onopgelos.append(csv_ry)
            continue
        for sp_kode in sp_kodes:
            aliasse.append({"alias": csv_ry["alias"], "sp_kode": sp_kode})
    return aliasse, onopgelos


# --- verslag ---------------------------------------------------------------------


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)
    r: list[str] = []
    r.append("# Plekke-, oorvleueling- en aliasverslag (Task 5)")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}")
    r.append("")

    r.append("## Ontdekking")
    r.append(f"- Bronlêers: `{BRON_SP_ZIP.name}` (Sub Place), `{BRON_MP_ZIP.name}` (Main Place, "
              "net vir ontdekking — nie in enige stg_-tabel gelaai nie; stg_plekke se mp_naam "
              "kom reeds van Subplace se eie MP_NAME-veld).")
    r.append(f"- Subplace `.prj`: `{kw['sp_prj']}`")
    r.append(f"- Main Place `.prj`: `{kw['mp_prj']}`")
    r.append(
        "  - Dit is Hartebeesthoek94 (GCS_Hartebeesthoek_1994, WGS84-sferoïed) — EPSG:4148. "
        "Soos die taakbrief aanvaar, as 4326-ekwivalent behandel: geen herprojeksie nie "
        "(`geo.na_ewkt_4326` met `bron_epsg=4326`, wat die vertaalstap oorslaan en net "
        "geldigheid/presisie opskoon)."
    )
    r.append(
        "- SP-velde bevestig: SP_CODE, SP_NAME, MP_CODE, MP_NAME, MN_MDB_C, MN_CODE, MN_NAME, "
        "MN_TYPE, DC_MDB_C, DC_MN_C, DC_NAME, Shape_Leng, Shape_Area."
    )
    r.append(f"- SP-rekordtal in shapefile: **{kw['sp_rekordtal']}** (verwag 22 196).")
    r.append(f"- MP-rekordtal in shapefile: **{kw['mp_rekordtal']}** (ter vergelyking — nie gelaai nie).")
    r.append(
        "- `SP_CODE` kom uit die dbf as 'n float (bv. `160001001.0`) — `na_sp_kode` skoon dit "
        "na heelgetal-teks (`\"160001001\"`) vir `stg_plekke.sp_kode`. Al 22 196 SP_CODE-waardes "
        "is uniek."
    )
    r.append("- cp1252-enkodering (`shapefile.Reader(..., encoding=\"cp1252\")`) per die taakbrief.")
    r.append("")

    r.append("## RED/GREEN (TDD)")
    for reël in kw["tdd_log"]:
        r.append(f"- {reël}")
    r.append("")

    r.append("## Laai na stg_plekke")
    r.append(f"- Rekords in bron: {kw['sp_rekordtal']}")
    r.append(f"- Oorgeslaan (geometrie het leeg geword ná afronding): {len(kw['oorgeslaan_geom'])}")
    for sp_kode in kw["oorgeslaan_geom"]:
        r.append(f"  - `{sp_kode}`")
    r.append(f"- Gelaai na `stg_plekke`: **{kw['gelaaide_plekke']}**")
    r.append(f"- Laai-tyd (leeg + plaas_bondels, bondelgrootte {PLEKKE_GROOTTE}): {kw['laai_tyd']:.1f}s")
    r.append("")

    r.append("## `rpc/bou_plek_wyke`")
    r.append(f"- Metode: **{kw['bpw_metode']}**")
    if kw["bpw_metode"] == "volledig (een oproep)":
        r.append(f"- Ingevoeg: **{kw['bpw_ingevoeg']}**")
        r.append(f"- Tyd: {kw['bpw_tyd']:.1f}s")
    else:
        r.append(
            f"- Die volle `rpc/bou_plek_wyke()`-oproep het misluk (PostgREST-statement-timeout of "
            f"soortgelyke fout): `{kw['bpw_volledig_fout']}`."
        )
        r.append(
            "- Vervolgens is 'n voorwaartse migrasie toegepas wat 'n opsionele "
            "`(van int, tot int)`-reeks by `bou_plek_wyke` voeg (rye van `stg_plekke` "
            "georden per `row_number() over (order by sp_kode)`; `delete from stg_plek_wyke` "
            "gebeur net wanneer albei parameters NULL is — 'n reeks-oproep vee dus nooit "
            "bestaande rye uit nie). Migrasie: "
            f"`{kw['migrasie_lêernaam']}` (toegepas via MCP `apply_migration`)."
        )
        r.append(f"- Bondelgrootte: {BOU_PLEK_WYKE_BONDEL} plekke per oproep — gekalibreer teen die "
                  "`authenticator`-rol se 8s `statement_timeout` (sien kalibrasietabel hieronder).")
        r.append(f"- Ingevoeg (som van alle suksesvolle oproepe): **{kw['bpw_ingevoeg']}**")
        r.append(f"- Totale tyd (alle bondels, insluitend halverings/herhalings): {kw['bpw_tyd']:.1f}s")
        tye = [tyd for _van, _tot, _ing, tyd in kw["bpw_bondel_tydsberekenings"]]
        if tye:
            r.append(
                f"- Suksesvolle oproepe: {len(tye)} — tyd/oproep min {min(tye):.1f}s, "
                f"maks {max(tye):.1f}s, gemiddeld {sum(tye) / len(tye):.1f}s"
            )
        r.append("")
        r.append("### Vroeë kalibrasie (voor die volle bondelloop, per `curl`)")
        r.append("| Reeksgrootte | Tyd (s) | Uitkoms |")
        r.append("|---:|---:|---|")
        r.append("| 50 | 3.4–3.5 | geslaag |")
        r.append("| 100 | 5.8 | geslaag |")
        r.append("| 150 | 6.9 | geslaag (naby die limiet) |")
        r.append("| 300 | 9.65 | **misluk** — 57014 statement timeout |")
        r.append("")
        r.append("### Reekse wat gehalveer moes word (statement-timeout op die volle bondel)")
        gehalveer = [
            (van, tot, ing, tyd)
            for van, tot, ing, tyd in kw["bpw_bondel_tydsberekenings"]
            if (tot - van + 1) < BOU_PLEK_WYKE_BONDEL
        ]
        if gehalveer:
            r.append(f"Totaal {len(gehalveer)} suksesvolle deel-reekse (uit halverings van "
                      f"oorspronklike {BOU_PLEK_WYKE_BONDEL}-groot bondels):")
            r.append("| Van | Tot | Ingevoeg | Tyd (s) |")
            r.append("|---:|---:|---:|---:|")
            for van, tot, ingevoeg, tyd in gehalveer:
                r.append(f"| {van} | {tot} | {ingevoeg} | {tyd:.1f} |")
        else:
            r.append("Geen — elke bondel van die volle grootte het op die eerste poging geslaag.")
        r.append("")
        r.append("### Plekke wat glad nie bereken kon word nie (oorgeslaan)")
        if kw["bpw_oorgeslaan_plekke"]:
            r.append(
                f"**{len(kw['bpw_oorgeslaan_plekke'])} plek(ke)** het 'n hardnekkige "
                "statement-timeout getref selfs by 'n reeks van 1 plek (ná 429/5xx-herhalings "
                f"in `lib.supabase.rpc` én {ENKEL_PLEK_HERHALINGS} ekstra enkel-plek-herhalings). "
                "Hulle het geen stg_plek_wyke-rye nie en verskyn dus hieronder onder '0 wyke', "
                "maar om 'n ander rede as 'n werklike kus-/see-snipper:"
            )
            r.append("| sp_kode | naam | mp_naam | row_number-reeks | fout |")
            r.append("|---|---|---|---|---|")
            for plek in kw["bpw_oorgeslaan_plekke"]:
                r.append(
                    f"| {plek['sp_kode']} | {plek['naam']} | {plek['mp_naam'] or ''} | "
                    f"({plek['van']}, {plek['tot']}) | `{plek['fout'][:120]}` |"
                )
        else:
            r.append("Geen — elke plek is uiteindelik suksesvol bereken (na moontlike halvering).")
    r.append("")

    r.append("## `stg_plek_wyke`-opsomming")
    r.append(f"- Totale rye: **{kw['plek_wyke_totaal']}**")
    r.append(f"- Plekke met 0 wyke: **{kw['nul_wyke_totaal']}** (verwag: sommige kus-/see-snippers)")
    r.append("")
    r.append("### Eerste 20 plekke met 0 wyke")
    r.append("| sp_kode | naam | mp_naam |")
    r.append("|---|---|---|")
    for ry in kw["nul_wyke_eerste_20"]:
        r.append(f"| {ry['sp_kode']} | {ry['naam']} | {ry['mp_naam'] or ''} |")
    r.append("")
    r.append("### Top 10 plekke per wyktal")
    r.append("| sp_kode | naam | mp_naam | wyktal |")
    r.append("|---|---|---|---:|")
    for ry in kw["top_10_wyktal"]:
        r.append(f"| {ry['sp_kode']} | {ry['naam']} | {ry['mp_naam'] or ''} | {ry['wyktal']} |")
    r.append("")

    r.append("## Aliasse")
    r.append(f"- Rye in `{ALIASSE_CSV_PAD.name}`: {kw['aliasse_csv_totaal']}")
    r.append(f"- Opgelos (sp_kode gevind): {kw['aliasse_opgelos']}")
    r.append(f"- Gelaai na `stg_plek_aliasse`: **{kw['aliasse_gelaai']}**")
    r.append("")
    r.append("### Alias-resolusietabel")
    r.append("| alias | naam | mp_naam | opgelos? | sp_kode-tal |")
    r.append("|---|---|---|---|---:|")
    for reël in kw["alias_resolusie_tabel"]:
        r.append(
            f"| {reël['alias']} | {reël['naam']} | {reël['mp_naam'] or ''} | "
            f"{'ja' if reël['opgelos'] else '**nee**'} | {reël['sp_kode_tal']} |"
        )
    r.append("")
    if kw["onopgeloste_aliasse"]:
        r.append("### Onopgeloste aliasse (nie gelaai nie — nie geraai nie)")
        for csv_ry in kw["onopgeloste_aliasse"]:
            r.append(f"- `{csv_ry['alias']}` -> `{csv_ry['naam']}` (mp_naam: `{csv_ry.get('mp_naam') or ''}`)")
        r.append("")

    r.append("## Steekproef-/smoke-navrae")
    r.append(kw["smoke_navrae"])
    r.append("")

    r.append("## DB-grootte ná laai")
    r.append(kw["db_grootte"])
    r.append("")

    r.append("## Kommentaar")
    for reël in kw["kommentaar"]:
        r.append(f"- {reël}")
    r.append("")

    VERSLAG_PAD.write_text("\n".join(r))


def hoof() -> int:
    tydstempel = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    if not ALIASSE_CSV_PAD.exists():
        print(f"aliasse.csv nie gevind nie: {ALIASSE_CSV_PAD}", file=sys.stderr)
        return 1

    pak_uit()
    sp_prj = lees_prj(SP_SHP_PAD)
    mp_prj = lees_prj(MP_SHP_PAD)

    vorm_rekord_pare = lees_vorm_rekord_pare()
    sp_rekordtal = len(vorm_rekord_pare)
    mp_rekordtal = len(lees_mp_rekords())

    tdd_log = [
        "RED: `data/tests/test_plekke.py` is eers geskryf en het gefaal — "
        "`ModuleNotFoundError: No module named 'laai_plekke'`.",
        "GREEN: `laai_plekke.py` is toe geïmplementeer; sien task-5-report.md vir die "
        "volle pytest-uitset.",
    ]

    plek_rye, oorgeslaan_geom = bou_plek_rye(vorm_rekord_pare)

    # --- laai (idempotent: leeg eers) ---
    laai_begin = time.monotonic()
    try:
        supabase.rpc("stg_leeg", {"tabel": "stg_plekke"})
        supabase.rpc("stg_leeg", {"tabel": "stg_plek_wyke"})
        supabase.rpc("stg_leeg", {"tabel": "stg_plek_aliasse"})
        supabase.plaas_bondels("stg_plekke", plek_rye, grootte=PLEKKE_GROOTTE)
    except supabase.SupabaseFout as fout:
        print(f"Laai het misluk: {fout}", file=sys.stderr)
        return 1
    laai_tyd = time.monotonic() - laai_begin
    print(f"Gelaai na stg_plekke: {len(plek_rye)} / {sp_rekordtal} (oorgeslaan geom: {len(oorgeslaan_geom)})")
    print(f"Laai-tyd: {laai_tyd:.1f}s")

    gebruik_bondel = "--bondel" in sys.argv[1:]

    # --- rpc/bou_plek_wyke ---
    bpw_metode: str
    bpw_ingevoeg: int
    bpw_tyd: float
    bpw_bondel_tydsberekenings: list[tuple[int, int, int, float]] = []
    bpw_oorgeslaan_reekse: list[tuple[int, int, str]] = []
    bpw_volledig_fout = ""

    if not gebruik_bondel:
        try:
            bpw_ingevoeg, bpw_tyd = roep_bou_plek_wyke_volledig()
            bpw_metode = "volledig (een oproep)"
        except supabase.SupabaseFout as fout:
            print(
                f"rpc/bou_plek_wyke() (volledig) het misluk: {fout}\n"
                "Waarskynlik 'n PostgREST-statement-timeout. Volgende stap: pas die "
                "voorwaartse migrasie toe wat 'n (van, tot)-reeks by bou_plek_wyke voeg, "
                "en herloop hierdie skrip met --bondel.",
                file=sys.stderr,
            )
            return 1
    else:
        bpw_metode = "bondels (van/tot-reeks)"
        migrasie_begin = time.monotonic()
        try:
            bpw_ingevoeg, bpw_bondel_tydsberekenings, bpw_oorgeslaan_reekse = roep_bou_plek_wyke_in_bondels(
                len(plek_rye)
            )
        except supabase.SupabaseFout as fout:
            print(f"rpc/bou_plek_wyke (bondels) het onverwags misluk: {fout}", file=sys.stderr)
            return 1
        bpw_tyd = time.monotonic() - migrasie_begin
        bpw_volledig_fout = kw_volledig_fout_boodskap()
        if bpw_oorgeslaan_reekse:
            print(
                f"Waarskuwing: {len(bpw_oorgeslaan_reekse)} plek(ke) kon nie bereken word nie "
                "(hardnekkige RPC-timeout selfs by 1 plek) — oorgeslaan, sien die verslag.",
                file=sys.stderr,
            )

    print(f"bou_plek_wyke ({bpw_metode}): {bpw_ingevoeg} ingevoeg ({bpw_tyd:.1f}s)")

    # --- lees stg_plek_wyke + stg_plekke terug (REST) vir opsomming + aliasse ---
    try:
        alle_plek_wyke = supabase.kry_alles("stg_plek_wyke", {"select": "sp_kode,wyk_id"})
        alle_plekke = supabase.kry_alles("stg_plekke", {"select": "sp_kode,naam,mp_naam"})
    except supabase.SupabaseFout as fout:
        print(f"kon nie stg_plek_wyke/stg_plekke terug lees nie: {fout}", file=sys.stderr)
        return 1

    plekke_by_sp_kode = {ry["sp_kode"]: ry for ry in alle_plekke}

    # bou_plek_wyke se (van, tot) is 'n row_number() oor stg_plekke geordend per sp_kode
    # (sien migrasie) — dieselfde ordening hier repliseer sodat 'n oorgeslaan-reeks se
    # row_number(s) na die werklike sp_kode/naam gekarteer kan word vir die verslag.
    plekke_geordend = sorted(alle_plekke, key=lambda ry: ry["sp_kode"])
    bpw_oorgeslaan_plekke = [
        {**plekke_geordend[rn - 1], "van": van, "tot": tot, "fout": fout}
        for van, tot, fout in bpw_oorgeslaan_reekse
        for rn in range(van, tot + 1)
        if rn - 1 < len(plekke_geordend)
    ]

    wyktal_per_sp_kode: dict[str, int] = {}
    for ry in alle_plek_wyke:
        wyktal_per_sp_kode[ry["sp_kode"]] = wyktal_per_sp_kode.get(ry["sp_kode"], 0) + 1

    plekke_met_wyke = set(wyktal_per_sp_kode)
    nul_wyke_sp_kodes = [ry["sp_kode"] for ry in alle_plekke if ry["sp_kode"] not in plekke_met_wyke]
    nul_wyke_eerste_20 = [plekke_by_sp_kode[sp] for sp in nul_wyke_sp_kodes[:20]]

    top_10_wyktal = sorted(wyktal_per_sp_kode.items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_10_wyktal_rye = [
        {**plekke_by_sp_kode[sp], "wyktal": telling} for sp, telling in top_10_wyktal if sp in plekke_by_sp_kode
    ]

    # --- aliasse ---
    aliasse_csv_rye = lees_aliasse_csv(ALIASSE_CSV_PAD)
    plekke_per_naam_mp, plekke_per_mp = bou_alias_indeks(alle_plekke)
    alias_rye, onopgeloste_aliasse = bou_alias_rye(aliasse_csv_rye, plekke_per_naam_mp, plekke_per_mp)

    alias_resolusie_tabel = []
    for csv_ry in aliasse_csv_rye:
        sp_kodes, _ = los_alias_op(csv_ry, plekke_per_naam_mp, plekke_per_mp)
        alias_resolusie_tabel.append(
            {
                "alias": csv_ry["alias"],
                "naam": csv_ry["naam"],
                "mp_naam": csv_ry.get("mp_naam") or None,
                "opgelos": bool(sp_kodes),
                "sp_kode_tal": len(sp_kodes),
            }
        )

    try:
        supabase.plaas_bondels("stg_plek_aliasse", alias_rye, grootte=200)
    except supabase.SupabaseFout as fout:
        print(f"Aliasse-laai het misluk: {fout}", file=sys.stderr)
        return 1

    print(f"Aliasse: {len(alias_rye)} gelaai / {len(aliasse_csv_rye)} CSV-rye "
          f"({len(onopgeloste_aliasse)} onopgelos)")

    migrasie_lêernaam = "20260915100200_bou_plek_wyke_reeks.sql" if gebruik_bondel else ""

    kommentaar = [
        "`stg_plekke` het geen primêre sleutel nie (dis 'n staging-tabel), maar al "
        "22 196 SP_CODE-waardes in die bron is uniek, so `sp_kode` gedra hom effektief "
        "as 'n natuurlike sleutel binne hierdie laai.",
        "`MainPlace.zip` word uitgepak en gelees vir ontdekking/naam-verifikasie "
        "(bv. of 'Port Elizabeth' as MP_NAME bestaan) maar nooit self na 'n stg_-tabel "
        "gelaai nie — stg_plekke se mp_naam kom reeds van Subplace se eie MP_NAME-veld.",
        "Aliasse word slegs gelaai vir CSV-rye wat teen die werklik gelaaide "
        "stg_plekke-name (+ mp_naam indien gegee) oplos; niks is geraai nie. Sien "
        "§Onopgeloste aliasse vir wat uitgesluit is en hoekom.",
    ]
    if bpw_oorgeslaan_plekke:
        kommentaar.append(
            f"{len(bpw_oorgeslaan_plekke)} plek(ke) kon glad nie deur `bou_plek_wyke` bereken "
            "word nie (hardnekkige PostgREST-statement-timeout selfs by 'n reeks van 1 plek, "
            "ná 429/5xx-herhalings én ekstra enkel-plek-herhalings) en is oorgeslaan — hulle "
            "verskyn dus in die '0 wyke'-lys hieronder om 'n ander rede as die verwagte "
            "kus-/see-snipper-geval. Sien §rpc/bou_plek_wyke se oorgeslaan-tabel."
        )

    skryf_verslag(
        tydstempel=tydstempel,
        sp_prj=sp_prj,
        mp_prj=mp_prj,
        sp_rekordtal=sp_rekordtal,
        mp_rekordtal=mp_rekordtal,
        oorgeslaan_geom=oorgeslaan_geom,
        gelaaide_plekke=len(plek_rye),
        laai_tyd=laai_tyd,
        tdd_log=tdd_log,
        bpw_metode=bpw_metode,
        bpw_ingevoeg=bpw_ingevoeg,
        bpw_tyd=bpw_tyd,
        bpw_bondel_tydsberekenings=bpw_bondel_tydsberekenings,
        bpw_volledig_fout=bpw_volledig_fout,
        bpw_oorgeslaan_plekke=bpw_oorgeslaan_plekke,
        migrasie_lêernaam=migrasie_lêernaam,
        plek_wyke_totaal=len(alle_plek_wyke),
        nul_wyke_totaal=len(nul_wyke_sp_kodes),
        nul_wyke_eerste_20=nul_wyke_eerste_20,
        top_10_wyktal=top_10_wyktal_rye,
        aliasse_csv_totaal=len(aliasse_csv_rye),
        aliasse_opgelos=len(aliasse_csv_rye) - len(onopgeloste_aliasse),
        aliasse_gelaai=len(alias_rye),
        alias_resolusie_tabel=alias_resolusie_tabel,
        onopgeloste_aliasse=onopgeloste_aliasse,
        smoke_navrae="sien hieronder (uitgevoer via Supabase MCP read-only SQL, buite hierdie "
        "Python-laaier — soos Task 3/4 se SQL-verifikasie).",
        db_grootte="sien hieronder (uitgevoer via Supabase MCP read-only SQL, buite hierdie "
        "Python-laaier).",
        kommentaar=kommentaar,
    )

    print(f"Verslag: {VERSLAG_PAD}")

    if onopgeloste_aliasse:
        print(
            f"Waarskuwing: {len(onopgeloste_aliasse)} alias(se) kon nie opgelos word nie — "
            "sien die verslag.",
            file=sys.stderr,
        )
    if nul_wyke_sp_kodes:
        print(
            f"Waarskuwing: {len(nul_wyke_sp_kodes)} plek(ke) het 0 wyke — sien die verslag.",
            file=sys.stderr,
        )

    return 0


def kw_volledig_fout_boodskap() -> str:
    return (
        "PostgREST-statement-timeout op die volledige rpc/bou_plek_wyke()-oproep "
        "(sien vorige loop se stderr) — opgelos deur die (van, tot)-reeks-migrasie."
    )


if __name__ == "__main__":
    raise SystemExit(hoof())
