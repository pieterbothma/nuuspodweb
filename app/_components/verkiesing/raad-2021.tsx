import { KOPIE } from "@/lib/verkiesing/kopie";
import { vergelykNaam, type Raad2021, type Raad2021Rooi } from "@/lib/verkiesing/orden";
import { vulIn } from "./stembriewe";
import { Uitvou } from "./uitvou";

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
 *     those two cells hold a dash plus a screen-reader "geen data" rather than an inference.
 *
 * Two layout decisions are load-bearing:
 *
 *  - **`table-fixed` with a shared `<colgroup>`.** Both tables — the seated parties and the
 *    0-seat parties in the disclosure — use the same `<Kolomme />` and the same `<Kop />`, so
 *    the columns line up whichever table a reader is looking at. With auto layout they cannot:
 *    each table would size its party column from its own content, and on most municipalities
 *    the longest 0-seat party name is longer than any seated one.
 *  - **Below `sm` the same cells reflow into one block per party** (`max-sm:` turns the table
 *    parts into blocks), with the column headings repeated as inline labels. Same data, same
 *    order, same space per party, nothing hidden and no horizontal scroll on a phone. The
 *    `overflow-x-auto` container still covers the narrow end of the table band.
 *
 * `geenMeerderheid` is computed in `lib/verkiesing/orden.ts` against the full 2021 council
 * size including independents (Piet's ruling, 2026-09-15) and already applied by `haalMuni`.
 */

/** Headings stay on one line: the 7rem number columns are sized for the longest label. */
const KOP =
  "text-grys px-4 py-2.5 font-sans text-[0.6875rem] font-bold tracking-[0.18em] whitespace-nowrap uppercase";
/** A data cell in table mode; in stacked mode the row owns the rule, so the cell drops it. */
const SEL =
  "border-rand text-ink border-t px-4 py-3 font-sans text-[0.9375rem] max-sm:border-t-0 max-sm:px-0";
/** The inline column label, shown only while the cells are stacked. */
const INLYN_ETIKET =
  "text-grys hidden font-sans text-[0.6875rem] font-bold tracking-[0.14em] uppercase max-sm:inline";
/** The mockup's `.knop`, at 44 px (LEESMY correction). */
const KNOPPIE =
  "border-rand text-ink group-hover:border-ink inline-flex min-h-11 items-center gap-2 rounded border px-3 py-2 font-sans text-xs font-bold tracking-widest uppercase";
const TABEL = "w-full table-fixed border-collapse max-sm:block sm:min-w-[28rem]";
const RY = "max-sm:border-rand max-sm:block max-sm:border-t max-sm:py-2.5";

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
 * The shared column widths. `table-fixed` means these decide the layout rather than the
 * content, which is the whole point: both tables get identical columns. The party column has
 * no width, so it takes whatever the three number columns leave.
 */
function Kolomme() {
  return (
    <colgroup className="max-sm:hidden">
      <col />
      <col className="w-[7rem]" />
      <col className="w-[7rem]" />
      <col className="w-[7rem]" />
    </colgroup>
  );
}

function Kop() {
  return (
    <thead className="max-sm:hidden">
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

/**
 * One number cell: right-aligned and `tabular-nums` in table mode, and a label/value pair on
 * its own line once the row has stacked. The label is real text in the cell, not CSS
 * generated content, so it is in the reading order either way.
 */
function Syfer({
  etiket,
  waarde,
  vet = false,
}: {
  etiket: string;
  waarde: number | null;
  vet?: boolean;
}) {
  return (
    <td
      className={`${SEL} text-right tabular-nums max-sm:flex max-sm:items-baseline max-sm:justify-between max-sm:gap-4 max-sm:py-0.5 max-sm:text-left ${vet ? "font-bold" : ""}`}
    >
      <span className={INLYN_ETIKET}>{etiket}</span>
      {waarde === null ? (
        <span>
          {/* Four cells either way: the dash carries the screen-reader text rather than the
              cell being hidden, which would leave the row with two cells instead of four. */}
          <span aria-hidden>—</span>
          <span className="sr-only">{KOPIE.muni_2021_geen_data}</span>
        </span>
      ) : (
        <span>{waarde}</span>
      )}
    </td>
  );
}

/** One party's line. Equal weight for every party: same height, same three numbers. */
function PartyRy({ ry, merker }: { ry: Raad2021Rooi; merker: "seteld" | "nul" }) {
  const props = merker === "seteld" ? { "data-raad-ry": "" } : { "data-raad-ry-nul": "" };
  return (
    <tr {...props} className={RY}>
      <td className={`${SEL} font-bold max-sm:pb-1.5`} data-party-naam>
        {ry.party_naam}
      </td>
      <Syfer etiket={KOPIE.muni_2021_kolom_wyk} waarde={ry.setels_wyk} />
      <Syfer etiket={KOPIE.muni_2021_kolom_pv} waarde={ry.setels_pv} />
      <Syfer etiket={KOPIE.muni_2021_kolom_totaal} waarde={ry.setels_totaal} vet />
    </tr>
  );
}

export function Raad2021Tabel({ raad }: { raad: Raad2021 }) {
  // Alphabetical, with the shared Afrikaans collator. Never by seats, votes or size.
  const gesorteer = [...raad.rye].sort((a, b) => vergelykNaam(a.party_naam, b.party_naam));
  const seteld = gesorteer.filter((r) => r.setels_totaal > 0);
  const sonder = gesorteer.filter((r) => r.setels_totaal <= 0);
  const sonderEtiket = vulIn(KOPIE.muni_2021_wys_sonder_setels, { n: sonder.length });

  return (
    <section aria-labelledby="raad-2021-opskrif">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2
          id="raad-2021-opskrif"
          className="text-rooi-teks flex-1 font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase"
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

      <div className="mt-4">
        <Uitvou naam="raad-2021" aantal={raad.rye.length + (raad.onafhanklike_setels > 0 ? 1 : 0)} wys={KOPIE.uitvou_wys_uitslag}>
          {/* The rows stack below `sm`, so nothing overflows on a phone; the container covers the
              narrow end of the band where the table itself is still in play. */}
          <div className="border-rand mt-3 border-b sm:overflow-x-auto">
            <table className={TABEL}>
              <Kolomme />
              <Kop />
              <tbody className="max-sm:block">
                {seteld.map((r) => (
                  <PartyRy key={r.party_naam} ry={r} merker="seteld" />
                ))}
                {raad.onafhanklike_setels > 0 && (
                  <tr data-raad-ry className={RY}>
                    <th scope="row" className={`${SEL} text-left font-bold max-sm:block max-sm:pb-1.5`}>
                      {KOPIE.muni_2021_onafhanklikes}
                    </th>
                    <Syfer etiket={KOPIE.muni_2021_kolom_wyk} waarde={null} />
                    <Syfer etiket={KOPIE.muni_2021_kolom_pv} waarde={null} />
                    <Syfer
                      etiket={KOPIE.muni_2021_kolom_totaal}
                      waarde={raad.onafhanklike_setels}
                      vet
                    />
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {sonder.length > 0 && (
            <details data-sonder-setels className="group mt-3.5">
              {/* w-fit: a block-level summary would stretch the focus ring across the whole column
                  instead of drawing it around the button. */}
              <summary className="flex w-fit cursor-pointer list-none items-center rounded [&::-webkit-details-marker]:hidden focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi">
                <span className={KNOPPIE}>
                  <span className="group-open:hidden">{sonderEtiket}</span>
                  <span className="hidden group-open:inline">
                    {KOPIE.muni_2021_versteek_sonder_setels}
                  </span>
                  <Pyltjie />
                </span>
              </summary>
              {/* The same <Kolomme /> and <Kop /> as above: identical columns, and an opened
                  disclosure labels its three number columns instead of showing bare digits. */}
              <div className="border-rand mt-3 border-b sm:overflow-x-auto">
                <table className={TABEL}>
                  <caption className="sr-only">{sonderEtiket}</caption>
                  <Kolomme />
                  <Kop />
                  <tbody className="max-sm:block">
                    {sonder.map((r) => (
                      <PartyRy key={r.party_naam} ry={r} merker="nul" />
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          <p className="text-grys mt-3.5 font-sans text-sm">{KOPIE.muni_2021_sortering}</p>
        </Uitvou>
      </div>
    </section>
  );
}
