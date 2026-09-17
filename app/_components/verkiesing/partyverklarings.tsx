import { KOPIE } from "@/lib/verkiesing/kopie";
import type { Partyverklaring } from "@/lib/verkiesing/partye";
import { relatieweTyd } from "@/lib/verkiesing/stroom";

/**
 * The parties' own statements, one card per party in alphabetical order (the data layer
 * sorts). Every card is built the same way and the same size when closed: party, headline,
 * date, one button. No party colour, logo or red anywhere inside a card, and the card never
 * says which party published most recently.
 *
 * The full text sits behind `<details>`, so the section stays server-rendered and a phone
 * reader sees every party's headline before any one party's statement.
 */
export function Partyverklarings({ verklarings, nou }: { verklarings: Partyverklaring[]; nou: Date }) {
  if (verklarings.length === 0) return null;
  return (
    <section id="wat-die-partye-se" aria-labelledby="partye-kop" className="scroll-mt-24">
      <h2 id="partye-kop" className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase">
        {KOPIE.partye_opskrif}
      </h2>
      <p className="text-grys mt-1.5 max-w-3xl font-sans text-sm">{KOPIE.partye_onderskrif}</p>
      <ul className="mt-5 grid items-start gap-4 md:grid-cols-2">
        {verklarings.map((v) => (
          <li key={v.party} data-partyverklaring={v.party} className="border-rand border">
            <details className="group">
              <summary className="flex cursor-pointer list-none flex-col gap-2 p-5 [&::-webkit-details-marker]:hidden focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink">
                <span className="flex items-baseline justify-between gap-3">
                  <span className="text-ink font-sans text-xs font-bold tracking-[0.14em] uppercase">{v.party}</span>
                  <time dateTime={v.gepubliseer_om} className="text-grys shrink-0 font-sans text-xs tabular-nums">
                    {relatieweTyd(v.gepubliseer_om, nou)}
                  </time>
                </span>
                <span className="text-ink font-sans text-[1.0625rem] leading-snug font-bold">{v.titel_af}</span>
                <span className="text-ink mt-1 inline-flex w-fit items-center gap-2 font-sans text-xs font-bold tracking-widest uppercase">
                  <span className="group-open:hidden">{KOPIE.partye_lees}</span>
                  <span className="hidden group-open:inline">{KOPIE.partye_versteek}</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="group-open:-rotate-180">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </span>
              </summary>
              <div className="border-rand border-t px-5 pt-4 pb-5">
                <div className="text-ink grid gap-3 font-sans text-[0.9375rem] leading-relaxed">
                  {v.teks_af.split(/\n\s*\n/).map((p, i) => (
                    <p key={i} className="whitespace-pre-line break-words">{p}</p>
                  ))}
                </div>
                <p className="text-grys mt-4 font-sans text-sm">
                  {v.vertaal ? KOPIE.partye_vertaal_etiket : KOPIE.partye_afrikaans_etiket}{" "}
                  <a
                    href={v.bron_url}
                    target="_blank"
                    rel="noopener"
                    className="text-ink decoration-rand underline underline-offset-4 hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
                  >
                    {v.titel_oorspronklik} ↗︎
                  </a>
                </p>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}
