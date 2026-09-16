import { KOPIE } from "@/lib/verkiesing/kopie";
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
 *  2. **Colour tokens are limited to `ink` / `grys` / `rand`.** No party colour, no logo, no
 *     photo, no red — not even a focus ring — inside a candidate or party row.
 *     `docs/verkiesing/partykleure.json` is never imported.
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
/** One ballot row. `min-h-11` plus identical padding is what makes the rows equal-height. */
const RY = "border-rand flex min-h-11 items-center gap-4 border-t px-5 py-3.5 sm:px-6";

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

/** A ward candidate: name in ink, party (or "Onafhanklik") in grey. Nothing else. */
function KandidaatRy({ kandidaat }: { kandidaat: Kandidaat }) {
  return (
    <div data-ry="kandidaat" className={RY}>
      <div className="min-w-0 flex-1">
        <p className="text-ink font-sans text-base font-bold">{kandidaat.volle_naam}</p>
        <p className="text-grys font-sans text-sm">
          {kandidaat.party_naam ?? KOPIE.onafhanklik}
        </p>
      </div>
    </div>
  );
}

/**
 * One party on a PR ballot, with its list behind a disclosure. `<details>` keeps the whole
 * page server-rendered; the two labels swap with `group-open`, so no state is involved.
 */
function PartyRy({ lys }: { lys: PartyLys }) {
  return (
    <details data-ry="party" className="border-rand group border-t">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-2 sm:px-6 [&::-webkit-details-marker]:hidden">
        <span className="text-ink min-w-0 flex-1 font-sans text-base font-bold">
          {lys.party_naam}
        </span>
        <span className={KNOPPIE}>
          <span className="group-open:hidden">{KOPIE.wys_lys}</span>
          <span className="hidden group-open:inline">{KOPIE.versteek_lys}</span>
          <Pyltjie />
        </span>
      </summary>
      {lys.kandidate.length === 0 ? (
        <p className="text-grys px-5 pb-3.5 font-sans text-[0.9375rem] sm:px-6">
          {KOPIE.kandidate_nog_nie_gelaai}
        </p>
      ) : (
        <ol className="px-5 pb-3.5 sm:px-6">
          {lys.kandidate.map((k, i) => (
            <li key={`${k.volle_naam}-${i}`} className="flex gap-3.5 py-1.5">
              <span className="text-grys w-5 shrink-0 text-right font-sans text-sm tabular-nums">
                {k.lys_posisie ?? i + 1}
              </span>
              <span className="text-ink font-sans text-[0.9375rem]">{k.volle_naam}</span>
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
      titel: vulIn(KOPIE.stembrief_pv, { q: wyk.muni_naam }),
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
      titel: vulIn(KOPIE.stembrief_distrik, { q: wyk.distrik_naam ?? wyk.distrik_kode }),
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
      <h2 id="stembriewe-opskrif" className="text-ink font-sans text-xs font-bold tracking-[0.22em] uppercase">
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
                  <KandidaatRy key={`${k.volle_naam}-${j}`} kandidaat={k} />
                ))
              )
            ) : blok.lyste.length === 0 ? (
              <NogGeenKandidate />
            ) : (
              blok.lyste.map((l) => <PartyRy key={l.party_naam} lys={l} />)
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
