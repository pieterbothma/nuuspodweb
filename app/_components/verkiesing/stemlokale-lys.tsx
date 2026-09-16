import { KOPIE } from "@/lib/verkiesing/kopie";
import type { Stemstasie } from "@/lib/verkiesing/wyksoeker";
import { vulIn } from "./stembriewe";

/**
 * The ward's voting stations, exactly as the IEC publishes them — capitals and all. A station
 * whose source address is empty shows its name only (Piet's ruling, 2026-09-15); the data
 * layer already turns a blank address into `null`, so there is nothing to trim here.
 *
 * `id="stemlokale"` is the anchor the search results and the municipality page link to.
 */
export function StemlokaleLys({ wykNr, stasies }: { wykNr: number; stasies: Stemstasie[] }) {
  const opskrif =
    stasies.length === 1
      ? vulIn(KOPIE.wyk_stemlokale_opskrif_een, { w: wykNr })
      : vulIn(KOPIE.wyk_stemlokale_opskrif, { n: stasies.length, w: wykNr });

  return (
    <section id="stemlokale" aria-labelledby="stemlokale-opskrif" className="scroll-mt-24">
      <h2
        id="stemlokale-opskrif"
        className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase"
      >
        {opskrif}
      </h2>
      <p className="text-grys mt-1.5 font-sans text-sm">{KOPIE.wyk_stemlokale_nota}</p>
      {stasies.length === 0 ? (
        // Empty is also what a database outage looks like, so this says what is on the page
        // rather than diagnosing why.
        <p className="text-grys mt-3 font-sans text-[0.9375rem]">{KOPIE.wyk_stemlokale_geen}</p>
      ) : (
        <ul className="border-rand mt-3 border-b">
          {stasies.map((s) => (
            <li key={s.vd_nommer} data-stasie={s.vd_nommer} className="border-rand border-t py-3.5">
              <p className="text-ink font-sans text-[0.9375rem] font-bold">{s.naam}</p>
              {s.adres && <p className="text-grys mt-0.5 font-sans text-sm">{s.adres}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
