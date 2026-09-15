"""Laai amptelike LGE 2021-raadsetels per party per munisipaliteit na `stg_raad_uitslae_2021`.

Bron: die IEC se per-munisipaliteit "Seat Calculation Detail"-PDF's
(`results.elections.org.za/home/LGEPublicReports/1091/Seat%20Calculation%20Detail/<PROV>/<KODE>.pdf`).
'n Bondel-bron (Excel/CSV) is eers by `results.elections.org.za/home/Downloads/ME-Results`
oorweeg (opsie a in die taakbrief) maar dié bladsy is 'n JS-enkelbladsy-toep sonder enige
statiese aflaai-skakels in die rou HTML — geen Excel/CSV met setels per party per
munisipaliteit is daar gevind nie. Die per-munisipaliteit-PDF's (opsie b) werk wel
betroubaar: elke munisipaliteitskode in `stg_munisipaliteite` (213 plaaslike + metro-rade)
kry sy eie PDF by 'n voorspelbare URL. Sien §Ontdekking in die verslag vir die volle
uiteensetting, ingesluit die provinsie-vouerkodes wat tydens hierdie taak ontdek is
(hulle stem ooreen met die bestaande `lge2021_{EC,FS,GP,KN,MP,NC,NP,NW,WP}.csv`-kodes,
nie met `stg_munisipaliteite`se muni_kode-voorvoegsels nie — bv. Limpopo se vouer is "NP",
Wes-Kaap s'n is "WP", Gauteng s'n is "GP" (nie "GT" nie), KwaZulu-Natal s'n is "KN"
(nie "KZN" nie)).

Die PDF dra twee tabelle wat albei met "Party Name" begin: die kwota-berekeningstabel
(bladsy 1) en die setel-opsplitsingstabel (gewoonlik bladsy 2, kolomme "Total Party
Seats (x)", "Ward Seats (y)", "PR List Seats (x-y)"). Net laasgenoemde word gelaai.
Partynaam word presies soos gedruk gehou, behalwe dat die PDF se gedwonge reëlbreuk
(cel te smal vir die naam) na 'n enkele spasie saamgevou word — dis geen inhoudelike
wysiging nie, net die herstel van die gedrukte naam uit die tabel se veelvuldige fisiese
lyne.

Amptelike setels alleen: setels word NOOIT uit stem-CSV's bereken nie, net gelees soos
die IEC dit gedruk het.

Idempotent: leeg eers `stg_raad_uitslae_2021` via `rpc/stg_leeg`, laai dan vars. PDF's
word na `data/bron/setelberekening-2021/` afgelaai (gitignored) en behou tussen lopies —
'n reeds-afgelaaide lêer word nie weer gehaal nie. Skryf
`data/uitvoer/uitslae-2021-verslag.md`. Termineer met 'n nie-nul afsluitkode as die
Supabase-laai self misluk; individuele PDF-aflaai-/ontledingsmislukkings (bronprobleme)
word in die verslag aangeteken maar veroorsaak nie 'n nie-nul afsluitkode nie, tensy
GEEN enkele raad suksesvol gelaai kon word nie.

Gebruik: cd data && uv run --with pdfplumber,shapely,pyproj,pyshp,httpx python laai_uitslae_2021.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from lib import supabase

BASIS_PAD = Path(__file__).parent
BRON_DIR = BASIS_PAD / "bron" / "setelberekening-2021"
VERSLAG_PAD = BASIS_PAD / "uitvoer" / "uitslae-2021-verslag.md"

IEC_BASIS_URL = (
    "https://results.elections.org.za/home/LGEPublicReports/1091/"
    "Seat%20Calculation%20Detail/{vouer}/{kode}.pdf"
)

# IEC se provinsie-vouerkode vir hierdie PDF-versameling — ontdek deur die EC135-
# vastrigger se werkende URL (`.../EC/EC135.pdf`) en toe elke ander provinsie se vouer
# stuksgewys getoets teen 'n bekende munisipaliteitskode (200 = regte vouer, 404 = nie).
# Val nie saam met stg_munisipaliteite se muni_kode-voorvoegsels nie (sien module-
# dokstring).
PROVINSIE_VOUER: dict[str, str] = {
    "Eastern Cape": "EC",
    "Free State": "FS",
    "Gauteng": "GP",
    "KwaZulu-Natal": "KN",
    "Limpopo": "NP",
    "Mpumalanga": "MP",
    "Northern Cape": "NC",
    "North West": "NW",
    "Western Cape": "WP",
}

MUNISIPALITEIT_PATROON = re.compile(r"Municipality:\s*(\S+)\s*-\s*(.+)")
RAADSGROOTTE_ETIKET = "Total Seats Available in Municipality"
ONAFHANKLIKES_ETIKET = "Independent Ward Councillors Elected"
RY_STOP_ETIKETTE = {"Total Party Seats", "Independents", "Total Seats"}

AFLAAI_VERTRAGING_S = 0.2
AFLAAI_TIMEOUT_S = 30


class OntledingsFout(Exception):
    """Raised when the source can't be mapped or a PDF's structure isn't recognised."""


@dataclass
class MuniOntledingResultaat:
    muni_kode: str
    party_rye: list[dict]
    raadsgrootte: int | None
    raadsgrootte_koptekst: int | None
    onafhanklike_setels: int | None = None
    waarskuwings: list[str] = field(default_factory=list)
    # Raadsgrootte-verskille wat presies deur onafhanklike raadslede (C) verklaar word —
    # nie 'n ontledingsfout nie, party_naam-tabelle dra per ontwerp net partye.
    verklaarde_verskille: list[str] = field(default_factory=list)


# --- provinsie -> vouer, URL-bou -----------------------------------------------------


def provinsie_na_vouer(provinsie: str) -> str:
    """`stg_munisipaliteite.provinsie` (volle naam) -> IEC-vouerkode vir hierdie PDF-pad."""
    try:
        return PROVINSIE_VOUER[provinsie]
    except KeyError as fout:
        raise OntledingsFout(f"onbekende provinsie: {provinsie!r}") from fout


def bou_url(muni_kode: str, provinsie: str) -> str:
    return IEC_BASIS_URL.format(vouer=provinsie_na_vouer(provinsie), kode=muni_kode)


# --- munisipaliteitslys uit stg_munisipaliteite --------------------------------------


def kry_munisipaliteite() -> list[dict]:
    """Elke 213 plaaslike/metro-raad (kode, naam, tipe, provinsie) — distrikte uitgesluit."""
    rye = supabase.kry_alles("stg_munisipaliteite", {"select": "kode,naam,tipe,provinsie"})
    return [r for r in rye if r["tipe"] in ("plaaslik", "metro")]


# --- aflaai (politely: klein vertraging, herbruik reeds-afgelaaide lêers) -----------


def laai_pdf(url: str, teiken_pad: Path) -> tuple[bool, int | None, str | None]:
    """Laai `url` af na `teiken_pad`. Gee (geslaag, http_kode, fout) terug.

    Slaan die aflaai oor (geslaag=True, http_kode=None) as die lêer reeds bestaan —
    die 2021-resultate is histories onveranderlik, so 'n herlaai is nie nodig nie.
    """
    if teiken_pad.exists():
        return True, None, None

    teiken_pad.parent.mkdir(parents=True, exist_ok=True)
    try:
        proses = subprocess.run(
            ["curl", "-sL", "-A", "Mozilla/5.0", url, "-o", str(teiken_pad), "-w", "%{http_code}"],
            capture_output=True,
            text=True,
            timeout=AFLAAI_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as fout:
        if teiken_pad.exists():
            teiken_pad.unlink()
        return False, None, str(fout)

    http_kode = int(proses.stdout.strip() or "0")
    if http_kode != 200 or proses.returncode != 0:
        if teiken_pad.exists():
            teiken_pad.unlink()
        return False, http_kode, f"curl-afsluitkode {proses.returncode}, http {http_kode}"
    return True, http_kode, None


# --- PDF-ontleding ---------------------------------------------------------------


def _skoon_sel(sel: Any) -> str:
    return re.sub(r"\s+", " ", (sel or "")).strip()


def is_setel_tabel_kop(kop: list | None) -> bool:
    """Onderskei die setel-opsplitsingstabel (bladsy 2) van die kwota-tabel (bladsy 1).

    Albei begin met kolom "Party Name"; net die opsplitsingstabel dra "Total Party
    Seats (x)", "Ward Seats (y)", "PR List Seats (x-y)" as kolomme 2-4.
    """
    if not kop or len(kop) < 4:
        return False
    velde = [_skoon_sel(c) for c in kop[:4]]
    return (
        velde[0] == "Party Name"
        and velde[1].startswith("Total Party Seats")
        and velde[2].startswith("Ward Seats")
        and velde[3].startswith("PR List Seats")
    )


def _heelgetal(sel: Any) -> int | None:
    skoon = _skoon_sel(sel).replace(",", "")
    if not skoon:
        return None
    try:
        return int(skoon)
    except ValueError:
        return None


def ontleed_setel_tabel(tabel: list[list], muni_kode: str) -> tuple[list[dict], int | None, list[str]]:
    """Ontleed die setel-opsplitsingstabel se rye (kopry uitgesluit).

    Gee (party_rye, raadsgrootte, waarskuwings) terug. `raadsgrootte` kom van die
    "Total Party Seats"-somry (kolom "Total Party Seats (x)"). 'n Ry waar
    setels_wyk + setels_pv != setels_totaal word steeds gelaai (die brondata bly
    ongewysig) maar kry 'n waarskuwing vir die verslag.
    """
    party_rye: list[dict] = []
    raadsgrootte: int | None = None
    waarskuwings: list[str] = []

    for ry in tabel[1:]:
        if not ry:
            continue
        etiket = _skoon_sel(ry[0])
        if not etiket:
            continue
        if etiket in RY_STOP_ETIKETTE:
            if etiket == "Total Party Seats":
                raadsgrootte = _heelgetal(ry[1] if len(ry) > 1 else None)
            continue

        totaal = _heelgetal(ry[1] if len(ry) > 1 else None)
        wyk = _heelgetal(ry[2] if len(ry) > 2 else None)
        pv = _heelgetal(ry[3] if len(ry) > 3 else None)
        if totaal is None or wyk is None or pv is None:
            waarskuwings.append(f"onleesbare ry vir {muni_kode}: {ry!r}")
            continue

        if wyk + pv != totaal:
            waarskuwings.append(
                f"{muni_kode}: {etiket!r} setels_wyk({wyk})+setels_pv({pv})={wyk + pv} "
                f"!= setels_totaal({totaal})"
            )

        party_rye.append(
            {
                "muni_kode": muni_kode,
                "party_naam": etiket,
                "setels_wyk": wyk,
                "setels_pv": pv,
                "setels_totaal": totaal,
            }
        )

    return party_rye, raadsgrootte, waarskuwings


def _kry_koptekstal(pdf: "pdfplumber.PDF", etiket: str) -> int | None:
    """Soek die header-tabel (bladsy 1) vir 'n ry wat met `etiket` begin, gee kolom 2 terug."""
    for bladsy in pdf.pages:
        for tabel in bladsy.extract_tables():
            for ry in tabel:
                if ry and ry[0] and _skoon_sel(ry[0]).startswith(etiket):
                    return _heelgetal(ry[1] if len(ry) > 1 else None)
    return None


def _kry_raadsgrootte_koptekst(pdf: "pdfplumber.PDF") -> int | None:
    return _kry_koptekstal(pdf, RAADSGROOTTE_ETIKET)


def _kry_onafhanklike_setels_koptekst(pdf: "pdfplumber.PDF") -> int | None:
    """"Independent Ward Councillors Elected - (C)" — wyksetels sonder party-affiliasie.

    `stg_raad_uitslae_2021` dra net partye, dus is 'n raadsgrootte-koptekssyfer (B) wat
    presies `onafhanklike_setels` hoër is as die som van party-setels GEEN ontledingsfout
    nie — dis die C-onafhanklikes wat, per ontwerp, nie in die setel-opsplitsingstabel se
    party-ry's voorkom nie.
    """
    return _kry_koptekstal(pdf, ONAFHANKLIKES_ETIKET)


def _kry_setel_tabel(pdf: "pdfplumber.PDF") -> list[list] | None:
    """Vind en kombineer die setel-opsplitsingstabel se rye oor alle bladsye.

    Groot rade (bv. metro's met tientalle klein partye) se opsplitsingstabel loop oor
    2-3 bladsye; elke bladsy herhaal die kopry ("Party Name", "Total Party Seats (x)",
    ...) maar dra net 'n deel van die partye — die som-/"Total Party Seats"-ry (en dus
    die raadsgrootte) verskyn net op die laaste bladsy. Sonder hierdie samevoeging tel
    net die eerste bladsy se partye (kyk §Ontledingsanomalië in die eerste lopie se
    verslag: elke metro se som setels_totaal het toe ver onder die koptekssyfer B geval).
    """
    saamgevoegde_rye: list[list] | None = None
    for bladsy in pdf.pages:
        for tabel in bladsy.extract_tables():
            if not tabel or not is_setel_tabel_kop(tabel[0]):
                continue
            if saamgevoegde_rye is None:
                saamgevoegde_rye = list(tabel)
            else:
                saamgevoegde_rye.extend(tabel[1:])
    return saamgevoegde_rye


def ontleed_pdf(pdf_pad: Path, verwagte_muni_kode: str) -> MuniOntledingResultaat:
    """Ontleed een munisipaliteit se "Seat Calculation Detail"-PDF.

    Gooi `OntledingsFout` as geen setel-opsplitsingstabel gevind kon word nie (die PDF
    is dan nie in die verwagte formaat nie — 'n opgemerkte bronprobleem, nie 'n
    stille dataverlies nie).
    """
    with pdfplumber.open(pdf_pad) as pdf:
        waarskuwings: list[str] = []

        eerste_bladsy_teks = pdf.pages[0].extract_text() or ""
        muni_treffer = MUNISIPALITEIT_PATROON.search(eerste_bladsy_teks)
        if muni_treffer and muni_treffer.group(1) != verwagte_muni_kode:
            waarskuwings.append(
                f"PDF-koptekst dra munisipaliteitskode {muni_treffer.group(1)!r}, "
                f"verwag {verwagte_muni_kode!r} ({pdf_pad.name})"
            )

        raadsgrootte_koptekst = _kry_raadsgrootte_koptekst(pdf)
        onafhanklike_setels = _kry_onafhanklike_setels_koptekst(pdf)

        setel_tabel = _kry_setel_tabel(pdf)
        if setel_tabel is None:
            raise OntledingsFout(f"geen setel-opsplitsingstabel gevind nie in {pdf_pad.name}")

        party_rye, raadsgrootte, tabel_waarskuwings = ontleed_setel_tabel(
            setel_tabel, verwagte_muni_kode
        )
        waarskuwings.extend(tabel_waarskuwings)

        verklaarde_verskille: list[str] = []

        def _tel_verskil(bron: str, party_syfer: int, koptekst_syfer: int) -> None:
            verskil = koptekst_syfer - party_syfer
            if verskil == 0:
                return
            if onafhanklike_setels is not None and verskil == onafhanklike_setels:
                verklaarde_verskille.append(
                    f"{verwagte_muni_kode}: {bron} ({party_syfer}) is {verskil} minder as "
                    f"koptekssyfer B={koptekst_syfer} — presies die {onafhanklike_setels} "
                    "onafhanklike wykraadslid/-lede (C), nie 'n ontledingsfout nie."
                )
            else:
                waarskuwings.append(
                    f"{verwagte_muni_kode}: {bron} ({party_syfer}) != koptekssyfer "
                    f"B={koptekst_syfer} (verskil {verskil}, onafhanklikes(C)="
                    f"{onafhanklike_setels})"
                )

        if raadsgrootte is not None and raadsgrootte_koptekst is not None:
            _tel_verskil("raadsgrootte uit setel-tabel", raadsgrootte, raadsgrootte_koptekst)

        somtotaal = sum(r["setels_totaal"] for r in party_rye)
        vergelyk = raadsgrootte if raadsgrootte is not None else raadsgrootte_koptekst
        if vergelyk is not None and somtotaal != vergelyk and raadsgrootte is None:
            # somtotaal vs raadsgrootte_koptekst is reeds hierbo getoets as raadsgrootte
            # self bestaan (dieselfde syfer); hier net vir die geval die "Total Party
            # Seats"-somry self ontbreek het.
            _tel_verskil("som setels_totaal", somtotaal, vergelyk)

        return MuniOntledingResultaat(
            muni_kode=verwagte_muni_kode,
            party_rye=party_rye,
            raadsgrootte=raadsgrootte,
            raadsgrootte_koptekst=raadsgrootte_koptekst,
            onafhanklike_setels=onafhanklike_setels,
            waarskuwings=waarskuwings,
            verklaarde_verskille=verklaarde_verskille,
        )


# --- geen-meerderheid-statistiek (verslag-statistiek; die werf bereken sy eie) -------


def kry_geen_meerderheid_rade(alle_party_rye: list[dict]) -> list[dict]:
    """Rade waar geen party > 50% van die raad se setels het nie.

    Gee 'n lys van {"muni_kode", "raadsgrootte", "grootste_party", "grootste_setels"}
    terug, een per raad sonder meerderheid, gesorteer op muni_kode.
    """
    per_muni: dict[str, list[dict]] = {}
    for ry in alle_party_rye:
        per_muni.setdefault(ry["muni_kode"], []).append(ry)

    geen_meerderheid: list[dict] = []
    for muni_kode, rye in sorted(per_muni.items()):
        raadsgrootte = sum(r["setels_totaal"] for r in rye)
        if raadsgrootte == 0:
            continue
        grootste = max(rye, key=lambda r: r["setels_totaal"])
        het_meerderheid = grootste["setels_totaal"] * 2 > raadsgrootte
        if not het_meerderheid:
            geen_meerderheid.append(
                {
                    "muni_kode": muni_kode,
                    "raadsgrootte": raadsgrootte,
                    "grootste_party": grootste["party_naam"],
                    "grootste_setels": grootste["setels_totaal"],
                }
            )
    return geen_meerderheid


# --- verslag --------------------------------------------------------------------


def skryf_verslag(**kw) -> None:
    VERSLAG_PAD.parent.mkdir(parents=True, exist_ok=True)

    r: list[str] = []
    r.append("# Raadsetels 2021-verslag (Task 6)")
    r.append("")
    r.append(f"Gegenereer: {kw['tydstempel']}")
    r.append("")

    r.append("## Bronkeuse")
    r.append(
        "- Opsie (a) uit die taakbrief — 'n IEC-bondelaflaai (Excel/CSV) van setels per "
        "party per munisipaliteit by `results.elections.org.za/home/Downloads/ME-Results` "
        "— is eers oorweeg. Die bladsy se rou HTML dra geen statiese aflaai-skakel na so "
        "'n tabel nie (dis 'n JS-enkelbladsy-toep wat data via 'n API laai); binne hierdie "
        "taak se bestek is dit nie verder ontrafel nie."
    )
    r.append(
        "- Gebruik dus opsie (b): die per-munisipaliteit \"Seat Calculation Detail\"-PDF's. "
        "URL-patroon: `.../Seat%20Calculation%20Detail/<VOUER>/<KODE>.pdf`. Die "
        "provinsie-vouerkode is ontdek deur die EC135-vastrigger se werkende URL "
        "(`.../EC/EC135.pdf`) en toe elke ander provinsie stuksgewys getoets teen 'n "
        "bekende munisipaliteitskode (200 = regte vouer). Resultaat: "
        f"`{kw['vouer_tabel_teks']}`."
    )
    r.append("")

    r.append("## Aflaai")
    r.append(f"- Munisipaliteite in `stg_munisipaliteite` (plaaslik + metro): {kw['munisipaliteite_totaal']}")
    r.append(f"- PDF's reeds plaaslik teenwoordig (nie herhaal nie): {kw['reeds_afgelaai']}")
    r.append(f"- PDF's nuut afgelaai hierdie lopie: {kw['nuut_afgelaai']}")
    r.append(f"- Aflaai-mislukkings: {len(kw['aflaai_mislukkings'])}")
    for m in kw["aflaai_mislukkings"]:
        r.append(f"  - `{m['muni_kode']}` ({m['url']}): {m['fout']}")
    r.append("")

    r.append("## Dekking")
    r.append(
        f"- Rade suksesvol ontleed en gelaai: **{kw['rade_gedek']} / {kw['munisipaliteite_totaal']}** "
        "(213 verwag: 8 metro's + 205 plaaslike rade)."
    )
    if kw["rade_nie_gedek"]:
        r.append(f"- Rade NIE gedek nie ({len(kw['rade_nie_gedek'])}):")
        for m in kw["rade_nie_gedek"]:
            r.append(f"  - `{m}`")
    else:
        r.append("- Geen rade ontbreek nie.")
    r.append(f"- Kode-teenstrydighede (2021-kode ≠ stg_munisipaliteite-kode): {len(kw['kode_teenstrydighede'])}")
    for t in kw["kode_teenstrydighede"]:
        r.append(f"  - {t}")
    r.append("")

    r.append("## Rye gelaai")
    r.append(f"- Party-rye na `stg_raad_uitslae_2021`: **{kw['rye_gelaai']}**")
    r.append("")

    r.append("## Rade sonder meerderheid (geen party > 50% van die raad se setels nie)")
    r.append(f"- Telling: **{len(kw['geen_meerderheid'])}**")
    if kw["geen_meerderheid"]:
        r.append("")
        r.append("| Munisipaliteit | Raadsgrootte | Grootste party | Setels |")
        r.append("|---|---:|---|---:|")
        for gm in kw["geen_meerderheid"]:
            r.append(
                f"| {gm['muni_kode']} | {gm['raadsgrootte']} | {gm['grootste_party']} | "
                f"{gm['grootste_setels']} |"
            )
    r.append("")

    r.append("## Verklaarde raadsgrootte-verskille (onafhanklike wykraadslede)")
    r.append(
        "`stg_raad_uitslae_2021` dra net partye; 'n raad se koptekssyfer (B, totale "
        "setels) kan hoër wees as die som van party-setels wanneer een of meer "
        "onafhanklike kandidate 'n wyk gewen het (\"Independent Ward Councillors "
        "Elected - (C)\" in die bron). Dis GEEN ontledingsfout nie — hieronder is dit "
        "geverifieer dat die verskil presies ooreenstem met C."
    )
    r.append(f"- Rade met so 'n verklaarde verskil: **{len(kw['verklaarde_verskille'])}**")
    for v in kw["verklaarde_verskille"]:
        r.append(f"  - {v}")
    r.append("")

    r.append("## Ontledingsanomalië (onverklaarde verskille — moontlike bronprobleme)")
    if kw["ontledings_waarskuwings"]:
        r.append(f"- Totaal: {len(kw['ontledings_waarskuwings'])}")
        for w in kw["ontledings_waarskuwings"]:
            r.append(f"  - {w}")
    else:
        r.append(
            "- Geen — elke gelaaide raad se wyk+PV klop met totaal per party, en elke "
            "raadsgrootte-verskil met die koptekssyfer (B) is volledig deur onafhanklike "
            "wykraadslede (C) verklaar (sien vorige afdeling)."
        )
    r.append("")

    r.append("## Tydsberekening")
    r.append(f"- Aflaai (213 PDF's, of oorslaan waar reeds plaaslik): {kw['aflaai_tyd']:.1f}s")
    r.append(f"- Ontleding (pdfplumber, alle rade): {kw['ontleding_tyd']:.1f}s")
    r.append(f"- Supabase-laai (leeg + plaas_bondels): {kw['laai_tyd']:.1f}s")
    r.append("")

    r.append("## Kommentaar")
    for c in kw["kommentaar"]:
        r.append(f"- {c}")
    r.append("")

    VERSLAG_PAD.write_text("\n".join(r))


# --- hoofvloei --------------------------------------------------------------------


def hoof() -> int:
    tydstempel = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    try:
        munisipaliteite = kry_munisipaliteite()
    except supabase.SupabaseFout as fout:
        print(f"Kon nie stg_munisipaliteite lees nie: {fout}", file=sys.stderr)
        return 1

    vouer_tabel_teks = ", ".join(f"{k}->{v}" for k, v in sorted(PROVINSIE_VOUER.items()))

    # --- aflaai ---
    aflaai_begin = time.monotonic()
    reeds_afgelaai = 0
    nuut_afgelaai = 0
    aflaai_mislukkings: list[dict] = []
    pdf_pad_per_muni: dict[str, Path] = {}

    for m in munisipaliteite:
        try:
            url = bou_url(m["kode"], m["provinsie"])
        except OntledingsFout as fout:
            aflaai_mislukkings.append({"muni_kode": m["kode"], "url": "", "fout": str(fout)})
            continue

        teiken_pad = BRON_DIR / f"{m['kode']}.pdf"
        was_reeds_daar = teiken_pad.exists()
        geslaag, _http_kode, fout = laai_pdf(url, teiken_pad)
        if was_reeds_daar:
            reeds_afgelaai += 1
        elif geslaag:
            nuut_afgelaai += 1
            time.sleep(AFLAAI_VERTRAGING_S)

        if geslaag:
            pdf_pad_per_muni[m["kode"]] = teiken_pad
        else:
            aflaai_mislukkings.append({"muni_kode": m["kode"], "url": url, "fout": fout or "onbekende fout"})

    aflaai_tyd = time.monotonic() - aflaai_begin

    # --- ontleed ---
    ontleding_begin = time.monotonic()
    alle_party_rye: list[dict] = []
    ontledings_waarskuwings: list[str] = []
    verklaarde_verskille: list[str] = []
    kode_teenstrydighede: list[str] = []
    rade_gedek: list[str] = []

    for m in munisipaliteite:
        pdf_pad = pdf_pad_per_muni.get(m["kode"])
        if pdf_pad is None:
            continue
        try:
            resultaat = ontleed_pdf(pdf_pad, m["kode"])
        except OntledingsFout as fout:
            aflaai_mislukkings.append({"muni_kode": m["kode"], "url": "", "fout": f"ontleding: {fout}"})
            continue

        for w in resultaat.waarskuwings:
            if w.startswith("PDF-koptekst dra munisipaliteitskode"):
                kode_teenstrydighede.append(w)
            else:
                ontledings_waarskuwings.append(w)
        verklaarde_verskille.extend(resultaat.verklaarde_verskille)

        alle_party_rye.extend(resultaat.party_rye)
        rade_gedek.append(m["kode"])

    ontleding_tyd = time.monotonic() - ontleding_begin

    alle_kodes = {m["kode"] for m in munisipaliteite}
    rade_nie_gedek = sorted(alle_kodes - set(rade_gedek))

    # --- laai (idempotent: leeg eers) ---
    laai_begin = time.monotonic()
    try:
        supabase.rpc("stg_leeg", {"tabel": "stg_raad_uitslae_2021"})
        supabase.plaas_bondels("stg_raad_uitslae_2021", alle_party_rye, grootte=500)
    except supabase.SupabaseFout as fout:
        print(f"Laai het misluk: {fout}", file=sys.stderr)
        return 1
    laai_tyd = time.monotonic() - laai_begin

    geen_meerderheid = kry_geen_meerderheid_rade(alle_party_rye)

    kommentaar = [
        "Die 'geen-meerderheid'-toets hierbo is 'n verslag-statistiek vir hierdie taak; "
        "die werf bereken sy eie meerderheidstatus later uit dieselfde stg-data.",
        "Party_naam word presies soos deur die IEC gedruk gehou (net PDF-reëlbreuk na "
        "spasie saamgevou, en rand-whitespace gestroop) — geen normalisering of "
        "afkorting-uitbreiding nie.",
        f"Provinsie-vouerkodes wat gebruik is: {vouer_tabel_teks}.",
    ]
    if aflaai_mislukkings:
        kommentaar.append(
            f"{len(aflaai_mislukkings)} raad/rade kon nie afgelaai/ontleed word nie — "
            "sien §Aflaai. Bronprobleem, nie 'n laaifout nie."
        )

    skryf_verslag(
        tydstempel=tydstempel,
        vouer_tabel_teks=vouer_tabel_teks,
        munisipaliteite_totaal=len(munisipaliteite),
        reeds_afgelaai=reeds_afgelaai,
        nuut_afgelaai=nuut_afgelaai,
        aflaai_mislukkings=aflaai_mislukkings,
        rade_gedek=len(rade_gedek),
        rade_nie_gedek=rade_nie_gedek,
        kode_teenstrydighede=kode_teenstrydighede,
        rye_gelaai=len(alle_party_rye),
        geen_meerderheid=geen_meerderheid,
        ontledings_waarskuwings=ontledings_waarskuwings,
        verklaarde_verskille=verklaarde_verskille,
        aflaai_tyd=aflaai_tyd,
        ontleding_tyd=ontleding_tyd,
        laai_tyd=laai_tyd,
        kommentaar=kommentaar,
    )

    print(f"Munisipaliteite: {len(munisipaliteite)}; rade gedek: {len(rade_gedek)}")
    print(f"Aflaai-mislukkings: {len(aflaai_mislukkings)}")
    print(f"Rye gelaai na stg_raad_uitslae_2021: {len(alle_party_rye)}")
    print(f"Rade sonder meerderheid: {len(geen_meerderheid)}")
    print(f"Aflaai-tyd: {aflaai_tyd:.1f}s, ontleding-tyd: {ontleding_tyd:.1f}s, laai-tyd: {laai_tyd:.1f}s")
    print(f"Verslag: {VERSLAG_PAD}")

    if not rade_gedek:
        print("Fout: geen enkele raad kon gelaai word nie.", file=sys.stderr)
        return 1

    if aflaai_mislukkings:
        print(
            f"Waarskuwing: {len(aflaai_mislukkings)} raad/rade kon nie afgelaai/ontleed "
            "word nie — sien die verslag.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(hoof())
