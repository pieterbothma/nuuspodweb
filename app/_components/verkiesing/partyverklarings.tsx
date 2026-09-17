import Link from "next/link";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { partyLogo, partyTeksKleur, type Partyverklaring } from "@/lib/verkiesing/partye";
import { relatieweTyd } from "@/lib/verkiesing/stroom";
import { vulIn } from "./stembriewe";

/**
 * The parties' own statements, one card per party in alphabetical order (the data layer
 * sorts). Every card is built the same way: logo, party, age, headline, one link. Each logo
 * sits in the same fixed square, and only the party's name carries its colour (Piet,
 * 2026-09-17) — every party gets one. No red, and the card never says which party published
 * most recently. The whole card opens the statement's own page
 * (Piet, 2026-09-17: reading in place was awkward).
 */
export function Partyverklarings({ verklarings, nou }: { verklarings: Partyverklaring[]; nou: Date }) {
  if (verklarings.length === 0) return null;
  return (
    <section id="wat-die-partye-se" aria-labelledby="partye-kop" className="scroll-mt-24">
      <h2 id="partye-kop" className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase">
        {KOPIE.partye_opskrif}
      </h2>
      <p className="text-grys mt-1.5 max-w-3xl font-sans text-sm">{KOPIE.partye_onderskrif}</p>
      <ul className="mt-5 grid gap-4 md:grid-cols-2">
        {verklarings.map((v) => {
          const logo = partyLogo(v.party);
          return (
            <li key={v.party} data-partyverklaring={v.party} className="flex">
              <Link
                href={`/verklaring/${v.id}`}
                className="border-rand hover:border-ink group flex w-full gap-4 border p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                <span className="size-12 shrink-0">
                  {logo && (
                    // eslint-disable-next-line @next/next/no-img-element -- small fixed-size local logos
                    <img src={logo} alt={vulIn(KOPIE.partye_logo_alt, { q: v.party })} width={48} height={48} className="size-12 object-contain" />
                  )}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <span className="flex items-baseline justify-between gap-3">
                    <span data-party-naam className={`${partyTeksKleur(v.party)} font-sans text-xs font-bold tracking-[0.14em] uppercase`}>{v.party}</span>
                    <time dateTime={v.gepubliseer_om} className="text-grys shrink-0 font-sans text-xs tabular-nums">
                      {relatieweTyd(v.gepubliseer_om, nou)}
                    </time>
                  </span>
                  <span className="text-ink font-sans text-[1.0625rem] leading-snug font-bold group-hover:underline">{v.titel_af}</span>
                  <span className="text-grys mt-auto pt-1 font-sans text-xs font-bold tracking-widest uppercase">
                    {KOPIE.partye_lees} →
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
