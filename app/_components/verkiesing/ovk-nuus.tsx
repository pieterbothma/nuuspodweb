import { KOPIE } from "@/lib/verkiesing/kopie";
import { OVK_NUUSLYS, type OvkNuus as Item } from "@/lib/verkiesing/ovk";

const DATUM = new Intl.DateTimeFormat("af-ZA", { day: "numeric", month: "short", timeZone: "UTC" });

/**
 * The IEC's latest press releases. Headlines exactly as the IEC published them (English stays
 * English, like "Wat ander berig"); only the date and our labels are Afrikaans. Renders nothing
 * until the first releases are loaded.
 */
export function OvkNuus({ items }: { items: Item[] }) {
  if (items.length === 0) return null;
  return (
    <section id="nuutste-van-die-iec" aria-labelledby="ovk-nuus-kop" className="scroll-mt-24">
      <h2 id="ovk-nuus-kop" className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase">
        {KOPIE.ovk_nuus_opskrif}
      </h2>
      <ul className="border-rand mt-3 border-b">
        {items.map((i) => (
          <li key={i.id} data-ovk-nuus={i.id} className="border-rand border-t">
            <a
              href={i.url}
              target="_blank"
              rel="noopener"
              className="group flex items-baseline gap-4 py-3.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
            >
              <time dateTime={i.datum} className="text-grys w-14 shrink-0 font-sans text-sm tabular-nums">
                {DATUM.format(new Date(`${i.datum}T00:00:00Z`))}
              </time>
              <span className="text-ink group-hover:text-rooi min-w-0 flex-1 font-sans text-[0.9375rem] leading-snug font-bold break-words">
                {i.titel} <span aria-hidden className="text-grys font-normal">↗︎</span>
                <span className="sr-only"> (maak in &apos;n nuwe oortjie oop)</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-3 font-sans text-sm">
        <a
          href={OVK_NUUSLYS}
          target="_blank"
          rel="noopener"
          className="text-ink decoration-rand font-bold underline underline-offset-4 hover:decoration-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
        >
          {KOPIE.ovk_nuus_alles} ↗︎
        </a>
      </p>
    </section>
  );
}
