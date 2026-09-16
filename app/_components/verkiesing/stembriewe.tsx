import { KOPIE } from "@/lib/verkiesing/kopie";
import { distrikNaam, muniNaam } from "@/lib/verkiesing/name";
import { kandidaatNaam } from "@/lib/verkiesing/orden";
import type {
  Kandidaat,
  PartyLys,
  Stembriewe as StembriefData,
  Wyk,
} from "@/lib/verkiesing/wyksoeker";

/**
 * The voter's ballots: one bordered block per ballot paper they will be handed.
 *
 * Neutrality is the whole point of this file, so four rules hold throughout:
 *  1. **Equal space per candidate.** Every candidate row is the same height and carries the
 *     same two lines; no row is emphasised, ranked or annotated.
 *  2. **Colour tokens are limited to `ink` / `grys` / `rand` / `paneel`.** No party colour,
 *     no photo, no red — not even a focus ring — inside a candidate or party row.
 *     `docs/verkiesing/partykleure.json` is never imported. Logos (Piet, 2026-09-16) sit in
 *     one fixed-size slot per row, identical for every party; until the IEC's official logos
 *     are loaded every slot shows the same empty frame, independents included.
 *  3. **The order comes from the data layer.** `haalStembriewe` returns everything already
 *     sorted and says which ordering that is; this component shows the label and never
 *     re-sorts.
 *  4. **No Afrikaans here.** Every visible string comes from `KOPIE`.
 *
 * Server-rendered end to end: the party lists use `<details>`, so the disclosure needs no
 * client JavaScript.
 */

/**
 * Substitutes `{n}` / `{m}` / `{w}` / `{q}` placeholders in a copy slot. Unknown keys are
 * left alone.
 *
 * A deliberate second copy of the same three lines in `wyk-soeker.tsx`: that file is a
 * `"use client"` module, and importing from it would drag the search box (and Motion) into
 * the ward page's client bundle. Every server component in this folder imports it from here.
 */
export function vulIn(sjabloon: string, waardes: Record<string, string | number>): string {
  return sjabloon.replace(/\{(\w+)\}/g, (heel, sleutel: string) =>
    sleutel in waardes ? String(waardes[sleutel]) : heel
  );
}

const ETIKET_KLEIN =
  "font-sans text-[0.6875rem] font-bold tracking-[0.2em] text-grys uppercase";
/** The order chip: what the reader is looking at, alphabetical or the drawn ballot order. */
const KENTEKEN =
  "border-rand text-grys shrink-0 border px-2.5 py-1 font-sans text-[0.6875rem] font-bold tracking-[0.16em] whitespace-nowrap uppercase";
/** The mockup's `.knop`, at 44 px (LEESMY correction) and without the red focus ring. */
const KNOPPIE =
  "border-rand text-ink inline-flex min-h-11 shrink-0 items-center gap-2 rounded border px-3 py-2 font-sans text-xs font-bold tracking-widest uppercase group-hover:border-ink";
/**
 * One ballot-paper row: the text cell, then a logo cell and a mark cell divided by hairlines,
 * like the IEC's paper ballot. Every row has the same three cells at the same widths, so no
 * party or candidate takes more room than another.
 */
const RY = "border-rand grid min-h-16 grid-cols-[minmax(0,1fr)_4rem_3.5rem] border-t sm:grid-cols-[minmax(0,1fr)_4.5rem_4rem]";
const SEL_TEKS = "flex min-w-0 flex-col justify-center px-5 py-3.5 sm:px-6";
const SEL_VAK = "border-rand flex items-center justify-center border-l";

/**
 * The party logo slot. `logoUrl` stays unset until official IEC logos are loaded; until then
 * every row, independents included, shows the same empty frame so no party stands out.
 */
function LogoVak({ partyNaam, logoUrl }: { partyNaam: string | null; logoUrl?: string | null }) {
  return (
    <div className={SEL_VAK} data-logo-vak={logoUrl ? "logo" : "leeg"}>
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- small fixed-size logos, no layout shift
        <img src={logoUrl} alt={partyNaam ?? ""} width={40} height={40} className="size-10 object-contain" />
      ) : (
        <span aria-hidden className="border-rand bg-paneel block size-10 border" />
      )}
    </div>
  );
}

/** The empty square a voter marks with an X. Decorative: nothing is voted on this site. */
function MerkVak() {
  return (
    <div className={SEL_VAK} data-merk-vak aria-hidden>
      <span className="border-ink block size-7 border-[1.5px] sm:size-8" />
    </div>
  );
}

function Pyltjie() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="group-open:-rotate-180"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

/**
 * First names and surname as the IEC lists them. A row the IEC published without a name is
 * still a line on the ballot, so it shows a grey placeholder rather than disappearing.
 */
function Naam({
  kandidaat,
  className,
  as = "p",
}: {
  kandidaat: Kandidaat;
  className: string;
  as?: "p" | "span";
}) {
  const naam = kandidaatNaam(kandidaat);
  const Tag = as;
  return naam ? (
    <Tag data-kandidaat-naam className={`text-ink ${className}`}>{naam}</Tag>
  ) : (
    <Tag data-kandidaat-sonder-naam className={`text-grys italic ${className} font-normal`}>
      {KOPIE.kandidaat_sonder_naam}
    </Tag>
  );
}

/** A ward candidate: name in ink, party (or "Onafhanklik") in grey, logo slot, mark box. */
function KandidaatRy({ kandidaat }: { kandidaat: Kandidaat }) {
  return (
    <div data-ry="kandidaat" className={RY}>
      <div className={SEL_TEKS}>
        <Naam kandidaat={kandidaat} className="font-sans text-base font-bold" />
        <p className="text-grys font-sans text-sm">
          {kandidaat.party_naam ?? KOPIE.onafhanklik}
        </p>
      </div>
      <LogoVak partyNaam={kandidaat.party_naam} />
      <MerkVak />
    </div>
  );
}

/**
 * One party on a PR ballot, with its list behind a disclosure. `<details>` keeps the whole
 * page server-rendered; the two labels swap with `group-open`, so no state is involved.
 *
 * `volgorde` decides whether the list shows numbers at all. Before the 23 September draw the
 * rows are alphabetical, so a "1, 2, 3" beside them would be a number the database does not
 * have — and a real `lys_posisie` printed next to an alphabetical list would contradict the
 * "Alfabeties" label above it. The array index is never used as a stand-in.
 */
function PartyRy({ lys, volgorde }: { lys: PartyLys; volgorde: StembriefData["volgorde"] }) {
  // The column is present for the whole list once the draw has landed, so the names stay
  // aligned even if a single row arrives without a position; that row's cell stays empty.
  const wysNommers = volgorde === "stembrief";
  return (
    <details data-ry="party" className="border-rand group border-t">
      <summary className="grid min-h-16 cursor-pointer list-none grid-cols-[minmax(0,1fr)_4rem_3.5rem] sm:grid-cols-[minmax(0,1fr)_4.5rem_4rem] [&::-webkit-details-marker]:hidden">
        <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3 sm:px-6">
          <span className="text-ink min-w-0 flex-1 basis-40 font-sans text-base font-bold">
            {lys.party_naam}
          </span>
          <span className={KNOPPIE}>
            <span className="group-open:hidden">{KOPIE.wys_lys}</span>
            <span className="hidden group-open:inline">{KOPIE.versteek_lys}</span>
            <Pyltjie />
          </span>
        </span>
        <LogoVak partyNaam={lys.party_naam} />
        <MerkVak />
      </summary>
      {lys.kandidate.length === 0 ? (
        <p className="text-grys px-5 pb-3.5 font-sans text-[0.9375rem] sm:px-6">
          {KOPIE.kandidate_nog_nie_gelaai}
        </p>
      ) : (
        <ol className="border-rand bg-paneel border-t px-5 py-2.5 sm:px-6">
          {lys.kandidate.map((k, i) => (
            <li key={`${k.volle_naam}-${k.van}-${i}`} className="flex gap-3.5 py-1.5">
              {wysNommers && (
                <span
                  data-lys-nr={k.lys_posisie ?? ""}
                  className="text-grys w-5 shrink-0 text-right font-sans text-sm tabular-nums"
                >
                  {k.lys_posisie ?? ""}
                </span>
              )}
              <Naam kandidaat={k} className="font-sans text-[0.9375rem]" as="span" />
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

/**
 * The "not loaded yet" body of a ballot block. It states a fact about the IEC's publication
 * of the final candidate lists and promises nothing about Nuuspod — which also makes it the
 * right text when the database is unreachable, because that returns the same empty list.
 */
function NogGeenKandidate() {
  return (
    <p className="border-rand text-grys border-t px-5 py-4 font-sans text-[0.9375rem] sm:px-6">
      {KOPIE.kandidate_nog_nie_gelaai}
    </p>
  );
}

type Blok =
  | { sleutel: string; titel: string; uitleg: string; soort: "wyk"; kandidate: Kandidaat[] }
  | { sleutel: string; titel: string; uitleg: string; soort: "pv"; lyste: PartyLys[] };

/** The blocks a voter in this ward gets: 3 in a local municipality, 2 in a metro. */
function blokke(wyk: Wyk, data: StembriefData): Blok[] {
  // Council names reach the site in English ("City of Cape Town"); `muniNaam` decides what a
  // reader sees without touching the row. Task 9 still owns the sentence around it.
  const raadNaam = muniNaam(wyk.muni_kode, wyk.muni_naam);
  const uit: Blok[] = [
    {
      sleutel: "wyk",
      titel: KOPIE.stembrief_wyk,
      uitleg: vulIn(KOPIE.stembrief_wyk_uitleg, { w: wyk.wyk_nr }),
      soort: "wyk",
      kandidate: data.wyk,
    },
    {
      sleutel: "pv_plaaslik",
      titel: vulIn(KOPIE.stembrief_pv, { q: raadNaam }),
      uitleg: KOPIE.stembrief_pv_uitleg,
      soort: "pv",
      lyste: data.pv_plaaslik,
    },
  ];
  // A district council ballot exists exactly when the municipality sits inside a district;
  // a metro's voter gets two ballots and `pv_distrik` is empty.
  if (wyk.distrik_kode) {
    uit.push({
      sleutel: "pv_distrik",
      titel: vulIn(KOPIE.stembrief_distrik, {
        q: distrikNaam(wyk.distrik_kode, wyk.distrik_naam ?? wyk.distrik_kode),
      }),
      uitleg: KOPIE.stembrief_distrik_uitleg,
      soort: "pv",
      lyste: data.pv_distrik,
    });
  }
  return uit;
}

export function Stembriewe({ wyk, stembriewe }: { wyk: Wyk; stembriewe: StembriefData }) {
  const lys = blokke(wyk, stembriewe);
  const volgorde =
    stembriewe.volgorde === "stembrief" ? KOPIE.volgorde_stembrief : KOPIE.volgorde_alfabeties;

  return (
    <section aria-labelledby="stembriewe-opskrif" className="flex flex-col gap-5">
      <h2 id="stembriewe-opskrif" className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase">
        {KOPIE.wyk_stembriewe_opskrif}
      </h2>
      {lys.map((blok, i) => (
        <div key={blok.sleutel} data-stembrief={blok.sleutel} className="border-ink border">
          <div className="border-rand flex items-start gap-4 border-b px-5 py-5 sm:px-6">
            <div className="min-w-0 flex-1">
              <p className={ETIKET_KLEIN}>
                {vulIn(KOPIE.stembrief_teller, { n: i + 1, m: lys.length })}
              </p>
              <h3 className="text-ink mt-1 font-display text-2xl leading-tight text-balance sm:text-[1.75rem]">
                {blok.titel}
              </h3>
              <p className="text-grys mt-1 font-sans text-[0.9375rem]">{blok.uitleg}</p>
            </div>
            <span className={KENTEKEN}>{volgorde}</span>
          </div>
          {/* -mt-px so the header's bottom border and the first row's top border are one line. */}
          <div className="-mt-px">
            {blok.soort === "wyk" ? (
              blok.kandidate.length === 0 ? (
                <NogGeenKandidate />
              ) : (
                blok.kandidate.map((k, j) => (
                  <KandidaatRy key={`${k.volle_naam}-${k.van}-${j}`} kandidaat={k} />
                ))
              )
            ) : blok.lyste.length === 0 ? (
              <NogGeenKandidate />
            ) : (
              blok.lyste.map((l) => (
                <PartyRy key={l.party_naam} lys={l} volgorde={stembriewe.volgorde} />
              ))
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
