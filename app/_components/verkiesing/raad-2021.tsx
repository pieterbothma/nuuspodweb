import { KOPIE } from "@/lib/verkiesing/kopie";
import { vergelykNaam, type Raad2021, type Raad2021Rooi } from "@/lib/verkiesing/orden";
import { vulIn } from "./stembriewe";

/**
 * How the council looked after the 2021 election — `Munisipaliteit.dc.html`'s "Raad ná 2021"
 * block. This is the one place on the ward finder that shows party sizes, so the neutrality
 * rules are stricter here than anywhere else:
 *
 *  1. **Sorted by party name, never by seats.** The sort runs in this component (with the
 *     shared collator, so it matches every other list on the site) rather than trusting the
 *     order the rows arrive in.
 *  2. **No party colours, logos or photos.** `docs/verkiesing/partykleure.json` is never
 *     imported; the only tokens used are `ink` / `grys` / `rand`.
 *  3. **Parties on 0 seats are not dropped, only folded away**, behind a disclosure that says
 *     how many there are — so a reader can see that the list is complete.
 *  4. **Every number comes from a row.** The independents line shows only the seat total the
 *     `raad_grootte_2021` row carries; the ward/PR split of those seats is not in any row, so
 *     those two cells are dashes rather than an inference.
 *
 * `geenMeerderheid` is computed in `lib/verkiesing/orden.ts` against the full 2021 council
 * size including independents (Piet's ruling, 2026-09-15) and already applied by `haalMuni`.
 */

const KOP =
  "text-grys px-4 py-2.5 font-sans text-[0.6875rem] font-bold tracking-[0.18em] uppercase";
const SEL = "border-rand text-ink border-t px-4 py-3 font-sans text-[0.9375rem]";
const NOMMER = `${SEL} text-right tabular-nums`;
/** The mockup's `.knop`, at 44 px (LEESMY correction) and without a red focus ring. */
const KNOPPIE =
  "border-rand text-ink group-hover:border-ink inline-flex min-h-11 items-center gap-2 rounded border px-3 py-2 font-sans text-xs font-bold tracking-widest uppercase";

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

function Kop() {
  return (
    <thead>
      <tr>
        <th scope="col" className={`${KOP} text-left`}>
          {KOPIE.muni_2021_kolom_party}
        </th>
        <th scope="col" className={`${KOP} text-right`}>
          {KOPIE.muni_2021_kolom_wyk}
        </th>
        <th scope="col" className={`${KOP} text-right`}>
          {KOPIE.muni_2021_kolom_pv}
        </th>
        <th scope="col" className={`${KOP} text-right`}>
          {KOPIE.muni_2021_kolom_totaal}
        </th>
      </tr>
    </thead>
  );
}

/** One party's line. Equal weight for every party: same height, same three numbers. */
function PartyRy({ ry, merker }: { ry: Raad2021Rooi; merker: "seteld" | "nul" }) {
  const props = merker === "seteld" ? { "data-raad-ry": "" } : { "data-raad-ry-nul": "" };
  return (
    <tr {...props}>
      <td className={`${SEL} font-bold`} data-party-naam>
        {ry.party_naam}
      </td>
      <td className={NOMMER}>{ry.setels_wyk}</td>
      <td className={NOMMER}>{ry.setels_pv}</td>
      <td className={`${NOMMER} font-bold`}>{ry.setels_totaal}</td>
    </tr>
  );
}

const TABEL = "border-rand w-full min-w-[28rem] border-collapse border-b";

export function Raad2021Tabel({ raad }: { raad: Raad2021 }) {
  // Alphabetical, with the shared Afrikaans collator. Never by seats, votes or size.
  const gesorteer = [...raad.rye].sort((a, b) => vergelykNaam(a.party_naam, b.party_naam));
  const seteld = gesorteer.filter((r) => r.setels_totaal > 0);
  const sonder = gesorteer.filter((r) => r.setels_totaal <= 0);

  return (
    <section aria-labelledby="raad-2021-opskrif">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2
          id="raad-2021-opskrif"
          className="text-ink flex-1 font-sans text-xs font-bold tracking-[0.22em] uppercase"
        >
          {KOPIE.muni_2021_opskrif}
        </h2>
        <span className="text-grys font-sans text-sm tabular-nums">
          {vulIn(KOPIE.muni_2021_raadsgrootte, { n: raad.raadsgrootte })}
        </span>
      </div>

      {/* Rendered only when it is true of this council — it is a fact about the result, not
          a standing caption. */}
      {raad.geenMeerderheid && (
        <p className="text-ink mt-2.5 font-sans text-[0.9375rem]">
          {KOPIE.muni_2021_geen_meerderheid}
        </p>
      )}

      {/* The table is the one element allowed to be wider than the phone; it scrolls inside
          this container so the page body never does. */}
      <div className="mt-3 overflow-x-auto">
        <table className={TABEL}>
          <Kop />
          <tbody>
            {seteld.map((r) => (
              <PartyRy key={r.party_naam} ry={r} merker="seteld" />
            ))}
            {raad.onafhanklike_setels > 0 && (
              <tr data-raad-ry>
                <th scope="row" className={`${SEL} text-left font-bold`}>
                  {KOPIE.muni_2021_onafhanklikes}
                </th>
                {/* The ward/PR split of independent seats is in no row, so it is not shown. */}
                <td className={NOMMER} aria-hidden>
                  —
                </td>
                <td className={NOMMER} aria-hidden>
                  —
                </td>
                <td className={`${NOMMER} font-bold`}>{raad.onafhanklike_setels}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {sonder.length > 0 && (
        <details data-sonder-setels className="group mt-3.5">
          <summary className="flex cursor-pointer list-none items-center [&::-webkit-details-marker]:hidden">
            <span className={KNOPPIE}>
              <span className="group-open:hidden">
                {vulIn(KOPIE.muni_2021_wys_sonder_setels, { n: sonder.length })}
              </span>
              <span className="hidden group-open:inline">
                {KOPIE.muni_2021_versteek_sonder_setels}
              </span>
              <Pyltjie />
            </span>
          </summary>
          <div className="mt-3 overflow-x-auto">
            <table className={TABEL}>
              <caption className="sr-only">
                {vulIn(KOPIE.muni_2021_wys_sonder_setels, { n: sonder.length })}
              </caption>
              <tbody>
                {sonder.map((r) => (
                  <PartyRy key={r.party_naam} ry={r} merker="nul" />
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <p className="text-grys mt-3.5 font-sans text-sm">{KOPIE.muni_2021_sortering}</p>
    </section>
  );
}
