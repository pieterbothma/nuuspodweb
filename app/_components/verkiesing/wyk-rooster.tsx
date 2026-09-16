import Link from "next/link";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { vulIn } from "./stembriewe";

/**
 * Every ward in a municipality, as a grid of bordered links — `Munisipaliteit.dc.html`'s
 * "Wyke" block. 6 columns on desktop, 3 on a phone, which keeps "Wyk 107" on one line at
 * 400 px.
 *
 * The label reuses `soek_wyk_nommer`, the same slot the search results and the ward page's
 * own heading use, so the three can never disagree about what a ward is called.
 *
 * A district council has no wards of its own, and `haalMuni` returns an empty list for it —
 * that renders as one plain sentence rather than an empty grid.
 */
export function WykRooster({ wyke }: { wyke: { wyk_id: string; wyk_nr: number }[] }) {
  return (
    <section aria-labelledby="wyke-opskrif">
      <h2
        id="wyke-opskrif"
        className="text-ink font-sans text-xs font-bold tracking-[0.22em] uppercase"
      >
        {KOPIE.muni_wyke_opskrif}
      </h2>
      {wyke.length === 0 ? (
        <p className="text-grys mt-3 font-sans text-[0.9375rem]">{KOPIE.muni_geen_wyke}</p>
      ) : (
        <div
          data-wyk-rooster
          className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6"
        >
          {wyke.map((w) => (
            <Link
              key={w.wyk_id}
              href={`/wyk/${w.wyk_id}`}
              className="border-rand text-ink hover:border-ink flex min-h-13 items-center justify-center border font-sans text-[0.9375rem] font-bold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
            >
              {vulIn(KOPIE.soek_wyk_nommer, { n: w.wyk_nr })}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
