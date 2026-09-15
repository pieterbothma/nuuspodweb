"""Ontleed IEC-kandidaatlys-PDF's (bv. `kandidate-2021-WC.pdf`) na `Kandidaat`-rekords.

Bron-vorm (waargeneem op die 2021 WC-lys, 249 bladsye, `pdfplumber.extract_tables()`):
elke bladsy dra 'n titelry ("Updated LGE2021 Candidate Lists - 8 Oct 2021"), 'n kop-ry
(`Municipality | Party | Ward \\ List Order | IDNumber | Fullname | Surname`) en dan
data-rye. Die kop-ry herhaal op elke bladsy. Geen gebroke/multi-lyn selle is waargeneem
nie (0 sel-tekste met "\\n"), maar `skoon()` vou wit spasie/nuwe-lyne ineen ter
verdediging vir 'n moontlik ander 2026-uitleg.

Kolomme word deur koptekste herken (nie vaste indekse nie — sien `kry_kolom_indekse`),
sodat 'n effens ander 2026-uitleg (ander spasiëring, "Ward/List" i.p.v.
"Ward \\ List Order", "Full Name" i.p.v. "Fullname") nie die ontleder breek nie. 'n
Kop-ry met ontbrekende verwagte kolomme gooi `KandidaatOntledingFout` en noem presies
watter kolomme ontbreek.

PERSONAL DATA RULE (verpligtend, sien die taakbrief se globale beperkings): die
gemaskeerde ID-nommer-kolom se indeks word wel in `kry_kolom_indekse` se resultaat
opgeneem (om te bevestig die kolom bestáán in die kop-ry), maar sy WAARDE word nooit uit
'n rou ry gelees of aan enige veranderlike toegeken nie — dit verskyn dus nêrens in
`Kandidaat`, in logs, of in die verslag nie. `bou_kandidaat` lees slegs die ses ander
kolomme se waardes. (`bron_ry` en `lys_posisie` is heelgetal-velde wat uitsluitlik uit
die bladsy/ry-teller en die Ward\\List-kolom afgelei word — nooit uit die ID-kolom nie —
en word dus doelbewus uitgesluit van die "geen 6+-syfer-string"-skans; dié skans geld die
tekstuele velde wat regstreeks uit PDF-selle oorgeneem word.)

Reël vir die "Ward \\ List Order"-kolom: 'n presies-8-syfer waarde beteken 'n wyk-kandidaat
(`stembrief="wyk"`, `wyk_id` gestel); enige ander suiwer-syfer waarde is 'n PV-lyspossie
(`lys_posisie` gestel). PV word verder verdeel in `pv_distrik` (munisipaliteit se rou sel
begin met "DC" of bevat "District", bv. "DC1 - West Coast") teenoor `pv_plaaslik`.
Onafhanklikes (`party == "INDEPENDENT"`, gevalsonsensitief) kom net op wyk-rye voor —
PR-lyste het per definisie 'n party.

FAIL LOUDLY OP LEË SELLE (beheerder-uitspraak, fix round 1): 'n leë munisipaliteit- of
party-sel word NOOIT stilweg oorgedra van 'n vorige ry nie (soos 'n uitgedrukte Excel-
lêer soms doen) — `bou_kandidaat` gooi `KandidaatOntledingFout` en noem die bladsy en ry.
As die 2026-lys werklik sulke oorgedra-selle gebruik, is dit 'n beleidsbesluit vir dan.

Gebruik (CLI, druk tellings per stembrief, per munisipaliteit, en 'n munisipaliteit x
stembrief-kruistabel — nooit kandidaatname nie):

    cd data && uv run --with pdfplumber python kandidate_ontleder.py <pdf> [--verslag pad]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pdfplumber

BASIS_PAD = Path(__file__).parent
VERSLAG_PAD_DEFAULT = BASIS_PAD / "uitvoer" / "kandidate-2021-fixture-verslag.md"

WYK_ID_PATROON = re.compile(r"^\d{8}$")


class KandidaatOntledingFout(Exception):
    """Die PDF se uitleg kon nie verstaan word nie (ontbrekende kolomme, onverwagte
    waarde in die Ward\\List-kolom, ens.)."""


@dataclass
class Kandidaat:
    muni_naam: str
    muni_kode: str | None
    party_naam: str
    onafhanklik: bool
    stembrief: str  # "wyk" | "pv_plaaslik" | "pv_distrik"
    wyk_id: str | None
    lys_posisie: int | None
    volle_naam: str
    van: str
    bron_lêer: str
    bron_ry: int


# --- kop-ry-herkenning (koptekste, nie vaste indekse nie) -----------------------------

# Elke sleutel se toets loop oor die genormaliseerde (kleinletters, net a-z) kopteks.
# "id" vereis beide "id" én "number" as substringe sodat dit nie per ongeluk op 'n ander
# kolom pas nie ("Ward \ List Order" -> "wardlistorder" bevat bv. nie "id" nie).
_KOP_TOETSE: dict[str, "callable"] = {
    "muni": lambda s: s == "municipality",
    "party": lambda s: s == "party",
    "wyklys": lambda s: "ward" in s,
    "id": lambda s: "id" in s and "number" in s,
    "volle_naam": lambda s: "full" in s and "name" in s,
    "van": lambda s: s == "surname",
}


def normaliseer_kop(s) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def kry_kolom_indekse(rou_ry: list) -> dict[str, int] | None:
    """As `rou_ry` 'n kop-ry is, gee `{sleutel: kolomindeks}` terug vir al ses sleutels
    (muni, party, wyklys, id, volle_naam, van). Gee None terug as die ry glad nie soos 'n
    kop-ry lyk nie (minder as 2 herkende koptekste). Gooi `KandidaatOntledingFout` as dit
    wél 'n kop-ry is (>=2 herkende koptekste) maar een of meer verwagte kolomme ontbreek —
    dit noem presies watter sleutels ontbreek."""
    genorm = [normaliseer_kop(sel) for sel in rou_ry]
    indekse: dict[str, int] = {}
    for sleutel, toets in _KOP_TOETSE.items():
        for i, g in enumerate(genorm):
            if toets(g):
                indekse[sleutel] = i
                break

    if len(indekse) < 2:
        return None

    ontbrekend = sorted(set(_KOP_TOETSE) - set(indekse))
    if ontbrekend:
        raise KandidaatOntledingFout(
            f"kop-ry herken maar kolomme ontbreek: {ontbrekend} (kop-ry: {rou_ry!r})"
        )
    return indekse


def is_leeg_of_titel_ry(rou_ry: list) -> bool:
    """'n Titelry (bv. 'Updated LGE2021 Candidate Lists - 8 Oct 2021', net kolom 0 gevul)
    of 'n heeltemal leë ry."""
    return all(not (sel and str(sel).strip()) for sel in rou_ry[1:])


def skoon(s) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def ontleed_muni(muni_sel: str) -> tuple[str, str | None]:
    """"CPT - City of Cape Town" -> ("City of Cape Town", "CPT"). Geen " - "-skeier
    gedruk nie -> (volle skoon string, None)."""
    muni_sel = skoon(muni_sel)
    if " - " not in muni_sel:
        return muni_sel, None
    kode, _, naam = muni_sel.partition(" - ")
    return naam.strip(), kode.strip()


def is_distrik(muni_sel_rou: str) -> bool:
    """'n Munisipaliteit is 'n distrik as sy rou selwaarde met 'DC' begin (bv. 'DC1 -
    West Coast') of 'District' bevat — getoets op die ONgesplitste selwaarde, soos die
    taakbrief dit stel."""
    muni_sel_rou = skoon(muni_sel_rou)
    if muni_sel_rou.upper().startswith("DC"):
        return True
    return "district" in muni_sel_rou.lower()


def bron_ry_kode(bladsy_nr: int, ry_nr: int) -> int:
    """Enkodeer (bladsy, ry) as een heelgetal: `bladsy_nr * 10000 + ry_nr` (soortgelyk aan
    `laai_stemstasies.bron_ry_kode`, maar *10000 i.p.v. *1000 sodat dit ook 'n 2026-lêer
    met tot 9 999 rye/bladsy sonder botsing verdra — die 2021 WC-lys se digste bladsy dra
    slegs 50 data-rye). Gooi `KandidaatOntledingFout` as `ry_nr >= 10000`: die enkodering
    kan dan nie meer waarborg twee rye op dieselfde bladsy kry verskillende `bron_ry`-
    waardes nie. Hierdie veld is 'n heelgetal-teller, nooit uit die ID-kolom afgelei nie —
    sien PERSONAL DATA RULE hierbo vir waarom dit uitgesluit is van die "geen 6+-syfer"-
    skans op `Kandidaat`-velde."""
    if ry_nr >= 10000:
        raise KandidaatOntledingFout(
            f"te veel rye op bladsy {bladsy_nr} ({ry_nr}) — bron_ry-enkodering (*10000) "
            "kan nie meer 'n unieke waarde per ry waarborg nie"
        )
    return bladsy_nr * 10000 + ry_nr


def bou_kandidaat(
    rou_ry: list,
    kolom_indekse: dict[str, int],
    bladsy_nr: int,
    ry_nr: int,
    bron_lêer: str,
) -> Kandidaat:
    """Bou een `Kandidaat` uit 'n rou pdfplumber-tabelry. Lees NOOIT `kolom_indekse["id"]`
    se waarde nie — dis die gemaskeerde-ID-kolom, positioneel oorgeslaan (sien
    PERSONAL DATA RULE in die module-dokumentasie)."""
    muni_rou = rou_ry[kolom_indekse["muni"]]
    party_rou = rou_ry[kolom_indekse["party"]]
    wyklys_rou = rou_ry[kolom_indekse["wyklys"]]
    volle_naam_rou = rou_ry[kolom_indekse["volle_naam"]]
    van_rou = rou_ry[kolom_indekse["van"]]

    # FAIL LOUDLY OP LEË SELLE (beheerder-uitspraak, fix round 1): 'n leë munisipaliteit-
    # of party-sel word nooit stilweg vanaf 'n vorige ry oorgedra nie (soos 'n
    # uitgedrukte-Excel-lêer soms doen) — dit sou 'n ry stilweg verkeerd klassifiseer.
    if not (muni_rou and str(muni_rou).strip()):
        raise KandidaatOntledingFout(
            f"leë munisipaliteit-sel op {bron_lêer} bladsy {bladsy_nr} ry {ry_nr} — "
            "word nie stilweg oorgedra van 'n vorige ry nie"
        )
    if not (party_rou and str(party_rou).strip()):
        raise KandidaatOntledingFout(
            f"leë party-sel op {bron_lêer} bladsy {bladsy_nr} ry {ry_nr} — "
            "word nie stilweg oorgedra van 'n vorige ry nie"
        )

    muni_naam, muni_kode = ontleed_muni(muni_rou)
    party_naam = skoon(party_rou)
    onafhanklik = party_naam.strip().upper() == "INDEPENDENT"

    wyklys_waarde = skoon(wyklys_rou)
    if WYK_ID_PATROON.match(wyklys_waarde):
        wyk_id: str | None = wyklys_waarde
        lys_posisie: int | None = None
        stembrief = "wyk"
    elif wyklys_waarde.isdigit():
        wyk_id = None
        lys_posisie = int(wyklys_waarde)
        stembrief = "pv_distrik" if is_distrik(muni_rou) else "pv_plaaslik"
    else:
        raise KandidaatOntledingFout(
            f"onverwagte waarde in die Ward\\List-kolom op {bron_lêer} bladsy {bladsy_nr} "
            f"ry {ry_nr}: {wyklys_waarde!r}"
        )

    return Kandidaat(
        muni_naam=muni_naam,
        muni_kode=muni_kode,
        party_naam=party_naam,
        onafhanklik=onafhanklik,
        stembrief=stembrief,
        wyk_id=wyk_id,
        lys_posisie=lys_posisie,
        volle_naam=skoon(volle_naam_rou),
        van=skoon(van_rou),
        bron_lêer=bron_lêer,
        bron_ry=bron_ry_kode(bladsy_nr, ry_nr),
    )


def ontleed(pdf_pad: Path | str) -> Iterator[Kandidaat]:
    """Ontleed 'n IEC-kandidaatlys-PDF na 'n stroom `Kandidaat`-rekords.

    Die kop-ry herken die kolomposisies opnuut elke keer dit voorkom (herhaal op elke
    bladsy) — as 'n toekomstige lêer se kolomvolgorde per bladsy verskil, sal dit dus
    steeds korrek ontleed word. `ry_nr` herbegin elke bladsy en tel net data-rye.
    """
    pdf_pad = Path(pdf_pad)
    bron_lêer = pdf_pad.name
    kolom_indekse: dict[str, int] | None = None

    with pdfplumber.open(pdf_pad) as pdf:
        for bladsy_idx, bladsy in enumerate(pdf.pages, start=1):
            ry_nr = 0
            for tabel in bladsy.extract_tables():
                for rou_ry in tabel:
                    moontlike_kop = kry_kolom_indekse(rou_ry)
                    if moontlike_kop is not None:
                        kolom_indekse = moontlike_kop
                        continue
                    if is_leeg_of_titel_ry(rou_ry):
                        continue
                    if kolom_indekse is None:
                        raise KandidaatOntledingFout(
                            f"data-ry gevind voor enige kop-ry herken is op {bron_lêer} "
                            f"bladsy {bladsy_idx} ({len(rou_ry)} kolomme)"
                        )
                    if max(kolom_indekse.values()) >= len(rou_ry):
                        raise KandidaatOntledingFout(
                            f"ry op {bron_lêer} bladsy {bladsy_idx} het te min kolomme "
                            f"({len(rou_ry)}) vir die herkende kop-indekse {kolom_indekse}"
                        )
                    ry_nr += 1
                    yield bou_kandidaat(rou_ry, kolom_indekse, bladsy_idx, ry_nr, bron_lêer)


# --- CLI: tellings per stembrief, per munisipaliteit, en 'n kruistabel (nooit name nie) ---


def kruistabel_rye(kandidate: list[Kandidaat]) -> list[tuple[str, int, int, int, int]]:
    """Bou `Counter((muni_naam, stembrief))` en gee dit terug as gesorteerde
    `(muni_naam, wyk, pv_plaaslik, pv_distrik, onafhanklik)`-rye — een ry per
    munisipaliteit, kolomme = stembrief-tellings plus 'n aparte onafhanklik-kolom
    (onafhanklikes is 'n subversameling van `wyk`, nie 'n aparte stembrief nie, so hy
    word ekstra getel eerder as in plaas van `wyk`)."""
    tellings: Counter[tuple[str, str]] = Counter()
    onafhanklik_tellings: Counter[str] = Counter()
    for k in kandidate:
        tellings[(k.muni_naam, k.stembrief)] += 1
        if k.onafhanklik:
            onafhanklik_tellings[k.muni_naam] += 1

    munisipaliteite = sorted({muni for muni, _stembrief in tellings})
    rye: list[tuple[str, int, int, int, int]] = []
    for muni in munisipaliteite:
        rye.append(
            (
                muni,
                tellings[(muni, "wyk")],
                tellings[(muni, "pv_plaaslik")],
                tellings[(muni, "pv_distrik")],
                onafhanklik_tellings[muni],
            )
        )
    return rye


def kies_steekproef(kandidate: list[Kandidaat]) -> list[Kandidaat]:
    """Gestratifiseerde steekproef vir die verslag: tot 3 `wyk` (nie-onafhanklik, om
    oorvleueling met die onafhanklik-emmer te vermy), 3 `pv_plaaslik`, 2 `pv_distrik`, 2
    onafhanklikes — minder as daar nie genoeg beskikbaar is nie. Nooit ID-data nie
    (`Kandidaat` het sowieso geen ID-veld nie)."""
    wyk = [k for k in kandidate if k.stembrief == "wyk" and not k.onafhanklik]
    pv_plaaslik = [k for k in kandidate if k.stembrief == "pv_plaaslik"]
    pv_distrik = [k for k in kandidate if k.stembrief == "pv_distrik"]
    onafhanklik = [k for k in kandidate if k.onafhanklik]

    steekproef: list[Kandidaat] = []
    steekproef.extend(wyk[:3])
    steekproef.extend(pv_plaaslik[:3])
    steekproef.extend(pv_distrik[:2])
    steekproef.extend(onafhanklik[:2])
    return steekproef


def formateer_verslag_teks(kandidate: list[Kandidaat], ontleedtyd: float) -> str:
    """Bou die teks wat die CLI druk: totale, tellings per stembrief, tellings per
    munisipaliteit, en 'n munisipaliteit x stembrief-kruistabel. Bevat doelbewus nooit 'n
    kandidaatnaam nie — net munisipaliteitname en telling-getalle."""
    stembrief_tellings = Counter(k.stembrief for k in kandidate)
    muni_tellings = Counter(k.muni_naam for k in kandidate)
    onafhanklik_tal = sum(1 for k in kandidate if k.onafhanklik)

    reëls = [f"Totaal: {len(kandidate)} kandidate ({ontleedtyd:.1f}s)"]
    reëls.append(f"Onafhanklikes: {onafhanklik_tal}")
    reëls.append("Per stembrief:")
    for stembrief in sorted(stembrief_tellings):
        reëls.append(f"  {stembrief}: {stembrief_tellings[stembrief]}")
    reëls.append("Per munisipaliteit:")
    for muni in sorted(muni_tellings):
        reëls.append(f"  {muni}: {muni_tellings[muni]}")
    reëls.append("Per munisipaliteit x stembrief (wyk / pv_plaaslik / pv_distrik / onafhanklik):")
    for muni, wyk, pv_plaaslik, pv_distrik, onafhanklik in kruistabel_rye(kandidate):
        reëls.append(
            f"  {muni}: wyk={wyk} pv_plaaslik={pv_plaaslik} pv_distrik={pv_distrik} "
            f"onafhanklik={onafhanklik}"
        )
    return "\n".join(reëls)


def skryf_fixture_verslag(
    verslag_pad: Path, bron_lêer: str, kandidate: list[Kandidaat], ontleedtyd: float
) -> None:
    """Skryf die vastrigger-verslag: tellings (via `formateer_verslag_teks`), 'n
    munisipaliteit x stembrief-kruistabel, en 'n gestratifiseerde steekproef (via
    `kies_steekproef`) SONDER enige ID-veld (`Kandidaat` het sowieso geen ID-veld nie —
    sien PERSONAL DATA RULE)."""
    verslag_pad.parent.mkdir(parents=True, exist_ok=True)
    r: list[str] = []
    r.append("# Kandidaatlys-verslag (Task 7)")
    r.append("")
    r.append(f"Bronlêer: `{bron_lêer}`")
    r.append(f"Ontleedtyd: {ontleedtyd:.1f}s")
    r.append("")
    r.append("## Tellings")
    r.append("```")
    r.append(formateer_verslag_teks(kandidate, ontleedtyd))
    r.append("```")
    r.append("")
    r.append("## Munisipaliteit x stembrief")
    r.append("| munisipaliteit | wyk | pv_plaaslik | pv_distrik | onafhanklik |")
    r.append("|---|---:|---:|---:|---:|")
    for muni, wyk, pv_plaaslik, pv_distrik, onafhanklik in kruistabel_rye(kandidate):
        r.append(f"| {muni} | {wyk} | {pv_plaaslik} | {pv_distrik} | {onafhanklik} |")
    r.append("")
    r.append(
        "## Steekproef (gestratifiseer: tot 3 wyk, 3 pv_plaaslik, 2 pv_distrik, "
        "2 onafhanklik — minder as nie genoeg beskikbaar nie; sonder enige ID-veld)"
    )
    r.append("| munisipaliteit | party | onafhanklik | stembrief | wyk_id | lys_posisie | volle_naam | van |")
    r.append("|---|---|---|---|---|---|---|---|")
    for k in kies_steekproef(kandidate):
        r.append(
            f"| {k.muni_naam} | {k.party_naam} | {k.onafhanklik} | {k.stembrief} | "
            f"{k.wyk_id or ''} | {k.lys_posisie if k.lys_posisie is not None else ''} | "
            f"{k.volle_naam} | {k.van} |"
        )
    r.append("")
    verslag_pad.write_text("\n".join(r))


def hoof(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ontleed 'n IEC-kandidaatlys-PDF.")
    parser.add_argument("pdf_pad", type=Path)
    parser.add_argument(
        "--verslag", type=Path, default=None, help="skryf 'n verslag-md na hierdie pad"
    )
    ns = parser.parse_args(argv)

    if not ns.pdf_pad.exists():
        print(f"bronlêer nie gevind nie: {ns.pdf_pad}", file=sys.stderr)
        return 1

    begin = time.monotonic()
    try:
        kandidate = list(ontleed(ns.pdf_pad))
    except KandidaatOntledingFout as fout:
        print(f"ontleding het misluk: {fout}", file=sys.stderr)
        return 1
    ontleedtyd = time.monotonic() - begin

    print(formateer_verslag_teks(kandidate, ontleedtyd))

    if ns.verslag:
        skryf_fixture_verslag(ns.verslag, ns.pdf_pad.name, kandidate, ontleedtyd)
        print(f"Verslag geskryf: {ns.verslag}")

    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
