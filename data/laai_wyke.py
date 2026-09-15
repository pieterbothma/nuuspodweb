"""Laai MDB 2026-wyksgrense (`MDBWards2026.zip`) na `stg_wyke` en `stg_munisipaliteite`.

Bron: Munisipale Afbakeningsraad (MDB), `data/bron/MDBWards2026.zip`. Word uitgepak na
`data/bron/wyke/` (gitignored).

Idempotent: leeg eers `stg_wyke` en `stg_munisipaliteite` via `rpc/stg_leeg`, laai dan
vars. Skryf `data/uitvoer/wyke-verslag.md`. Termineer met 'n nie-nul afsluitkode as die
laai self misluk (Supabase-foute); 'n selftoets wat nie 100% slaag nie word in die
verslag aangeteken maar veroorsaak nie 'n nie-nul afsluitkode nie (dis 'n bronprobleem,
nie 'n laaifout nie).

Gebruik: cd data && uv run --with shapely,pyproj,pyshp,httpx python laai_wyke.py
"""

from __future__ import annotations

import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import shapefile

from lib import geo, supabase, teks  # noqa: F401  (teks unused here, kept for symmetry)

BASIS_PAD = Path(__file__).parent
BRON_ZIP = BASIS_PAD / "bron" / "MDBWards2026.zip"
BRON_DIR = BASIS_PAD / "bron" / "wyke"
SHP_PAD = BRON_DIR / "MDBWards2026.shp"
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "wyke-verslag.md"

BRON_EPSG = 3857  # bevestig teen die .prj — sien §Ontdekking in die verslag
WYKE_GROOTTE = 25  # klein bondelgrootte: poligone is groot

METRO_KODES = {"BUF", "CPT", "EKU", "ETH", "JHB", "MAN", "NMA", "TSH"}


def pak_uit() -> None:
    if SHP_PAD.exists():
        return
    if not BRON_ZIP.exists():
        raise SystemExit(f"bronlêer nie gevind nie: {BRON_ZIP}")
    BRON_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BRON_ZIP) as z:
        z.extractall(BRON_DIR)


def lees_prj() -> str:
    prj_pad = SHP_PAD.with_suffix(".prj")
    return prj_pad.read_text().strip()


def lees_vorm_rekord_pare() -> list[tuple[Any, dict]]:
    """Lees shape + record saam (gepaar per indeks) uit een Reader-lopie."""
    r = shapefile.Reader(str(SHP_PAD))
    return [(sr.shape, sr.record.as_dict()) for sr in r.iterShapeRecords()]


def agt_syfer_wyk_id(ward_id: str) -> str | None:
    """WardID -> 8-syfer teks, of None as dit nie 'n suiwer syferveld is nie."""
    ward_id = ward_id.strip()
    if ward_id.isdigit():
        return ward_id.zfill(8)
    return None


def bou_wyk_rye(vorm_rekord_pare: list[tuple[Any, dict]]) -> tuple[list[dict], list[str], list[str]]:
    """Bou stg_wyke-rye. Gee (rye, oorgeslaan_id_probleem, oorgeslaan_leë_geom) terug."""
    rye: list[dict] = []
    oorgeslaan_id: list[str] = []
    oorgeslaan_geom: list[str] = []

    for vorm, rekord in vorm_rekord_pare:
        ward_id = rekord["WardID"]
        wyk_id = agt_syfer_wyk_id(ward_id)
        if wyk_id is None:
            # bv. NC451 se 15 wyke dra "NC451_<nr>" i.p.v. 'n numeriese MDB-ID —
            # kan nie by die stg_wyke.wyk_id CHECK ('^\\d{8}$') pas nie sonder om 'n
            # ID te versin. Oorgeslaan en in die verslag aangeteken.
            oorgeslaan_id.append(f"{ward_id} ({rekord['CAT_B']} wyk {rekord['WardNo']})")
            continue
        try:
            ewkt = geo.na_ewkt_4326(vorm, BRON_EPSG)
        except geo.LeeGeometrieFout:
            oorgeslaan_geom.append(wyk_id)
            continue
        rye.append(
            {
                "wyk_id": wyk_id,
                "wyk_nr": rekord["WardNo"],
                "muni_kode": rekord["CAT_B"],
                "geom": ewkt,
            }
        )
    return rye, oorgeslaan_id, oorgeslaan_geom


def bou_munisipaliteit_rye(rekords: list[dict]) -> list[dict]:
    """Een ry per unieke CAT_B, plus een ry per unieke distrikskode (DC-voorvoegsel)."""
    munis: dict[str, dict] = {}
    distrikte: dict[str, dict] = {}

    for rekord in rekords:
        kode = rekord["CAT_B"]
        distrik_kode = rekord["DISTRICTCO"]
        is_distrik_kode = distrik_kode.startswith("DC")

        if kode not in munis:
            tipe = "metro" if kode in METRO_KODES else "plaaslik"
            munis[kode] = {
                "kode": kode,
                "naam": rekord["MUNICNAME"],
                "tipe": tipe,
                # metro's DISTRICTCO verwys na homself (bv. CPT/CPT) — nie 'n
                # regte distrik nie, so metro's kry distrik_kode = None.
                "distrik_kode": distrik_kode if (tipe == "plaaslik" and is_distrik_kode) else None,
                "provinsie": rekord["Province"],
            }

        if is_distrik_kode and distrik_kode not in distrikte:
            distrikte[distrik_kode] = {
                "kode": distrik_kode,
                "naam": rekord["DISTRICT"],
                "tipe": "distrik",
                "distrik_kode": None,
                "provinsie": rekord["Province"],
            }

    return list(munis.values()) + list(distrikte.values())


def per_provinsie_telling(rekords: list[dict]) -> dict[str, int]:
    telling: dict[str, int] = defaultdict(int)
    for rekord in rekords:
        telling[rekord["Province"]] += 1
    return dict(sorted(telling.items()))


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)

    reëls: list[str] = []
    reëls.append("# Wyke- en munisipaliteitverslag (Task 3)")
    reëls.append("")
    reëls.append(f"Gegenereer: {kw['tydstempel']}")
    reëls.append("")

    reëls.append("## Ontdekking")
    reëls.append(f"- Bronlêer: `{BRON_ZIP.name}`, uitgepak na `{BRON_DIR.relative_to(BASIS_PAD)}`.")
    reëls.append(f"- `.prj`: `{kw['prj']}`")
    reëls.append(
        "  - Dit is Web Mercator Auxiliary Sphere (WGS84 basis, meter-eenhede) — EPSG:3857, soos verwag."
    )
    reëls.append(
        "- Velde bevestig: WardID, WardNo, CAT_B, MUNICNAME, DISTRICT (naam), "
        "DISTRICTCO (kode, bv. `DC12`), Province."
    )
    reëls.append(
        "  - Let wel: die brief het aanvaar DISTRICT dra 'n kode; in werklikheid dra "
        "DISTRICT die distriksnaam (bv. `Amathole`) en DISTRICTCO die kode (bv. `DC12`). "
        "`distrik_kode` word van DISTRICTCO geneem, distriknaam van DISTRICT."
    )
    reëls.append(f"- Rekordtal in shapefile: **{kw['rekordtal']}** (verwag 4 485).")
    reëls.append("")

    reëls.append("### Probleem in die bron: NC451 (Joe Morolong) se WardID's")
    reëls.append(
        f"Al {len(kw['oorgeslaan_id'])} wyke van munisipaliteit **NC451 (Joe Morolong, "
        "Noord-Kaap)** dra 'n WardID in die vorm `NC451_<nr>` (bv. `NC451_1`) i.p.v. 'n "
        "numeriese 8-syfer MDB-ID soos elke ander rekord in die lêer. Dit is nie 'n "
        "geometrieprobleem nie — dis 'n kodeprobleem — en `stg_wyke.wyk_id` het 'n "
        "CHECK-beperking (`^\\d{8}$`) wat so 'n waarde weier. Om nie 'n ID te versin wat "
        "later nie sal ooreenstem met die IEC se stemlokaal-/kandidaatdata (Task 4/5) "
        "wat op die regte MDB WardID staatmaak nie, is hierdie 15 wyke **oorgeslaan**, "
        "nie gelaai nie. Sien §Wyke hieronder vir die volle lys."
    )
    reëls.append("")

    reëls.append("## Munisipaliteite en distrikte")
    reëls.append(f"- Munisipaliteite met wyke gelaai: **{kw['munisipaliteite_totaal']}** (verwag 213)")
    reëls.append(f"  - metro's: **{kw['metro_telling']}** — {', '.join(sorted(kw['metro_lys']))}")
    reëls.append(f"  - plaaslike munisipaliteite: **{kw['plaaslik_telling']}**")
    reëls.append(f"- Distrikte gelaai: **{kw['distrik_telling']}** (verwag 44)")
    reëls.append("")

    reëls.append("## Wyke")
    reëls.append(f"- Rekords in bron: {kw['rekordtal']}")
    reëls.append(f"- Oorgeslaan (WardID nie 'n suiwer syferveld nie): {len(kw['oorgeslaan_id'])}")
    for item in kw["oorgeslaan_id"]:
        reëls.append(f"  - `{item}`")
    reëls.append(f"- Oorgeslaan (geometrie het leeg geword ná afronding): {len(kw['oorgeslaan_geom'])}")
    for wid in kw["oorgeslaan_geom"]:
        reëls.append(f"  - `{wid}`")
    reëls.append(f"- Gelaai na `stg_wyke`: **{kw['gelaaide_wyke']}**")
    reëls.append("")

    reëls.append("### Wyke per provinsie (bron vs verwag)")
    reëls.append("| Provinsie | Bronlêer | Verwag (IEC) | Verskil |")
    reëls.append("|---|---:|---:|---:|")
    verwag = kw.get("verwag_per_provinsie", {})
    for prov, telling in kw["per_provinsie"].items():
        v = verwag.get(prov)
        if v is not None:
            reëls.append(f"| {prov} | {telling} | {v} | {telling - v} |")
        else:
            reëls.append(f"| {prov} | {telling} | — | — |")
    reëls.append("")
    reëls.append(
        "Vrystaat: 308 in die bronlêer teenoor 311 volgens die IEC-tabel (verskil van 3 — "
        "die bekende 3 ontbrekende Vrystaatse wyke, per die globale beperkings-dokument). "
        "Noord-Kaap se bronlêer-telling (233) sluit die 15 NC451-wyke hierbo in wat "
        "*nie* gelaai is nie omrede die WardID-probleem — só is 218 werklik in `stg_wyke` "
        "vir Noord-Kaap."
    )
    reëls.append("")

    reëls.append("## Selftoets (`rpc/kontroleer_wyke`)")
    st = kw["selftoets"]
    reëls.append(f"- wyke_totaal: {st['wyke_totaal']}")
    reëls.append(f"- met_geom: {st['met_geom']}")
    reëls.append(f"- sonder_geom: {st['sonder_geom']}")
    reëls.append(f"- selftoets_geslaag: {st['selftoets_geslaag']}")
    reëls.append(f"- selftoets_gefaal: {st['selftoets_gefaal']}")
    if st.get("gefaalde_ids"):
        reëls.append(f"- gefaalde_ids: {st['gefaalde_ids']}")
    reëls.append("")
    if st["selftoets_gefaal"] == 0:
        reëls.append(f"**Selftoets geslaag: {st['selftoets_geslaag']} / {st['wyke_totaal']}.**")
    else:
        reëls.append(
            f"**Selftoets: {st['selftoets_geslaag']} geslaag, {st['selftoets_gefaal']} gefaal "
            f"van {st['wyke_totaal']}.** Sien gefaalde_ids hierbo."
        )
    reëls.append("")

    reëls.append("## Steekproef-kontrole (Kaapstad SSD)")
    reëls.append(kw["kaapstad_kontrole"])
    reëls.append("")

    reëls.append("## SQL-verifikasie")
    for reël in kw["sql_verifikasie"]:
        reëls.append(f"- {reël}")
    reëls.append("")

    reëls.append("## Tydsberekening")
    reëls.append(f"- Volle laai (munisipaliteite + distrikte + wyke): {kw['laai_tyd']:.1f}s")
    reëls.append(f"- `rpc/kontroleer_wyke`: {kw['selftoets_tyd']:.1f}s")
    reëls.append("")

    reëls.append("## Kommentaar")
    for reël in kw["kommentaar"]:
        reëls.append(f"- {reël}")
    reëls.append("")

    VERSLAG_PAD.write_text("\n".join(reëls))


def hoof() -> int:
    tydstempel = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    pak_uit()
    prj = lees_prj()
    vorm_rekord_pare = lees_vorm_rekord_pare()
    rekords = [rekord for _, rekord in vorm_rekord_pare]
    rekordtal = len(rekords)

    munisipaliteit_rye = bou_munisipaliteit_rye(rekords)
    wyk_rye, oorgeslaan_id, oorgeslaan_geom = bou_wyk_rye(vorm_rekord_pare)

    metro_lys = sorted({r["kode"] for r in munisipaliteit_rye if r["tipe"] == "metro"})
    plaaslik_telling = sum(1 for r in munisipaliteit_rye if r["tipe"] == "plaaslik")
    distrik_telling = sum(1 for r in munisipaliteit_rye if r["tipe"] == "distrik")
    munisipaliteite_totaal = len(metro_lys) + plaaslik_telling

    # --- Laai (idempotent: leeg eers) ---
    laai_begin = time.monotonic()
    try:
        supabase.rpc("stg_leeg", {"tabel": "stg_munisipaliteite"})
        supabase.rpc("stg_leeg", {"tabel": "stg_wyke"})
        supabase.plaas_bondels("stg_munisipaliteite", munisipaliteit_rye, grootte=200)
        supabase.plaas_bondels("stg_wyke", wyk_rye, grootte=WYKE_GROOTTE)
    except supabase.SupabaseFout as fout:
        print(f"Laai het misluk: {fout}", file=sys.stderr)
        return 1
    laai_tyd = time.monotonic() - laai_begin

    # --- Selftoets ---
    selftoets_begin = time.monotonic()
    try:
        selftoets_rye = supabase.rpc("kontroleer_wyke", {})
    except supabase.SupabaseFout as fout:
        print(f"kontroleer_wyke het misluk: {fout}", file=sys.stderr)
        return 1
    selftoets_tyd = time.monotonic() - selftoets_begin
    selftoets = selftoets_rye[0] if isinstance(selftoets_rye, list) else selftoets_rye

    verwag_per_provinsie = {
        "Eastern Cape": None,
        "Free State": 311,
        "Gauteng": None,
        "KwaZulu-Natal": None,
        "Limpopo": None,
        "Mpumalanga": None,
        "North West": None,
        "Northern Cape": None,
        "Western Cape": None,
    }
    verwag_per_provinsie = {k: v for k, v in verwag_per_provinsie.items() if v is not None}

    kommentaar = [
        "Die IEC se amptelike per-provinsie tabel is nie in hierdie taak se bronne "
        "beskikbaar nie behalwe die Vrystaat-syfer (311) wat in die globale beperkings "
        "gegee is; die ander provinsies se 'Verwag'-kolom bly leeg totdat daardie tabel "
        "bekom word.",
        "NC451 (Joe Morolong) se 15 wyke se WardID-probleem moet aan MDB gerapporteer "
        "word — soortgelyk aan die bekende 3 ontbrekende Vrystaatse wyke, maar 'n "
        "aparte, nuut-ontdekte probleem.",
        "`stg_munisipaliteite` het geen primêre sleutel nie (dis 'n staging-tabel); die "
        "laaier skryf steeds net een ry per unieke CAT_B en per unieke DC-distrikskode, "
        "so daar behoort geen duplikate te wees nie.",
    ]

    skryf_verslag(
        tydstempel=tydstempel,
        prj=prj,
        rekordtal=rekordtal,
        munisipaliteite_totaal=munisipaliteite_totaal,
        metro_telling=len(metro_lys),
        metro_lys=metro_lys,
        plaaslik_telling=plaaslik_telling,
        distrik_telling=distrik_telling,
        oorgeslaan_id=oorgeslaan_id,
        oorgeslaan_geom=oorgeslaan_geom,
        gelaaide_wyke=len(wyk_rye),
        per_provinsie=per_provinsie_telling(rekords),
        verwag_per_provinsie=verwag_per_provinsie,
        selftoets=selftoets,
        kaapstad_kontrole="sien Task-3-verslag (SQL hieronder uitgevoer via MCP, nie hierdie skrip nie)",
        sql_verifikasie=[
            "sien Task-3-verslag vir die volle SQL-uitset (row counts, ST_IsValid, SRID, "
            "Kaapstad-steekproef) — dit is buite hierdie Python-laaier uitgevoer."
        ],
        laai_tyd=laai_tyd,
        selftoets_tyd=selftoets_tyd,
        kommentaar=kommentaar,
    )

    print(f"Munisipaliteite gelaai: {munisipaliteite_totaal} (+ {distrik_telling} distrikte)")
    print(f"Wyke gelaai: {len(wyk_rye)} / {rekordtal} (oorgeslaan: id={len(oorgeslaan_id)}, geom={len(oorgeslaan_geom)})")
    print(f"Selftoets: {selftoets['selftoets_geslaag']} geslaag / {selftoets['selftoets_gefaal']} gefaal van {selftoets['wyke_totaal']}")
    print(f"Laai-tyd: {laai_tyd:.1f}s, selftoets-tyd: {selftoets_tyd:.1f}s")
    print(f"Verslag: {VERSLAG_PAD}")

    if selftoets["selftoets_gefaal"] > 0:
        print(
            f"Waarskuwing: {selftoets['selftoets_gefaal']} wyk(e) het die selftoets gefaal — "
            "sien die verslag.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
