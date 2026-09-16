import Link from "next/link";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { WykUitslag2021 } from "@/lib/verkiesing/wyksoeker";
import { vulIn } from "./stembriewe";

const GETAL = new Intl.NumberFormat("af-ZA");
const PERSENT = new Intl.NumberFormat("af-ZA", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const KOP =
  "text-grys px-4 py-2.5 font-sans text-[0.6875rem] font-bold tracking-[0.18em] whitespace-nowrap uppercase";
const SEL = "border-rand text-ink border-t px-4 py-3 font-sans text-[0.9375rem]";

function partyNaam(naam: string): string {
  return naam.trim().toUpperCase() === "INDEPENDENT" ? KOPIE.uitslag2021_onafhanklik : naam;
}

function Tabel({ rye, geldig }: { rye: WykUitslag2021["rye"]; geldig: number }) {
  return (
    <div className="border-rand mt-3 overflow-x-auto border-b">
      <table className="w-full table-fixed border-collapse">
        <colgroup>
          <col />
          <col className="w-24 sm:w-28" />
          <col className="w-16 sm:w-20" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className={`${KOP} text-left`}>{KOPIE.uitslag2021_kolom_party}</th>
            <th scope="col" className={`${KOP} text-right`}>{KOPIE.uitslag2021_kolom_stemme}</th>
            <th scope="col" className={`${KOP} text-right`}>{KOPIE.uitslag2021_kolom_persent}</th>
          </tr>
        </thead>
        <tbody>
          {rye.map((r) => (
            <tr key={r.party_naam} data-uitslag-ry>
              <th scope="row" className={`${SEL} text-left font-bold break-words`}>{partyNaam(r.party_naam)}</th>
              <td className={`${SEL} text-right tabular-nums`}>{GETAL.format(r.stemme)}</td>
              <td className={`${SEL} text-right tabular-nums`}>
                {geldig > 0 ? PERSENT.format((r.stemme / geldig) * 100) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * A ward's official 2021 ward-ballot result — only on wards whose voting districts are exactly
 * those of a 2021 ward, so the figures describe this area without estimation (Piet,
 * 2026-09-16). Parties alphabetical, equal weight, no colour and no winner marker: the numbers
 * carry the result. A redrawn ward gets one sentence and a link to the council's 2021 result.
 */
export function Uitslag2021({
  uitslag,
  wykNr,
  muniKode,
}: {
  uitslag: WykUitslag2021 | "verander" | null;
  wykNr: number;
  muniKode: string;
}) {
  if (uitslag === null) return null;

  if (uitslag === "verander") {
    return (
      <section aria-labelledby="uitslag-2021" data-uitslag-2021="verander">
        <h2 id="uitslag-2021" className="text-ink font-sans text-xs font-bold tracking-[0.22em] uppercase">
          {KOPIE.uitslag2021_opskrif}
        </h2>
        <p className="text-grys mt-2.5 font-sans text-[0.9375rem]">
          {KOPIE.uitslag2021_verander}{" "}
          <Link
            href={`/munisipaliteit/${muniKode}`}
            className="text-ink decoration-rand font-bold underline underline-offset-4 hover:decoration-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
          >
            {KOPIE.uitslag2021_verander_skakel}
          </Link>
        </p>
      </section>
    );
  }

  const u = uitslag;
  // Parties under 1% fold away, as 0-seat parties do on the municipality page: every party is
  // still one click away and the list stays alphabetical; nothing is ranked by votes.
  const drempel = u.geldige_stemme * 0.01;
  const groot = u.rye.filter((r) => r.stemme >= drempel);
  const klein = u.rye.filter((r) => r.stemme < drempel);
  const stemdeelname = u.geregistreer > 0 ? ((u.geldige_stemme + u.bedorwe_stemme) / u.geregistreer) * 100 : null;

  return (
    <section aria-labelledby="uitslag-2021" data-uitslag-2021="uitslag">
      <h2 id="uitslag-2021" className="text-ink font-sans text-xs font-bold tracking-[0.22em] uppercase">
        {KOPIE.uitslag2021_opskrif}
      </h2>
      <p className="text-grys mt-1.5 font-sans text-sm">
        {KOPIE.uitslag2021_onderskrif}
        {u.wyk_nr_2021 !== wykNr && <> {vulIn(KOPIE.uitslag2021_hernommer, { n: u.wyk_nr_2021 })}</>}
      </p>

      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 font-sans text-sm">
        <div className="flex gap-1.5">
          <dt className="text-grys">{KOPIE.uitslag2021_geregistreer}</dt>
          <dd className="text-ink font-bold tabular-nums">{GETAL.format(u.geregistreer)}</dd>
        </div>
        {stemdeelname !== null && (
          <div className="flex gap-1.5">
            <dt className="text-grys">{KOPIE.uitslag2021_stemdeelname}</dt>
            <dd className="text-ink font-bold tabular-nums">{PERSENT.format(stemdeelname)}%</dd>
          </div>
        )}
        <div className="flex gap-1.5">
          <dt className="text-grys">{KOPIE.uitslag2021_bedorwe}</dt>
          <dd className="text-ink font-bold tabular-nums">{GETAL.format(u.bedorwe_stemme)}</dd>
        </div>
      </dl>

      <Tabel rye={groot} geldig={u.geldige_stemme} />
      {klein.length > 0 && (
        <details data-klein-partye className="group mt-3.5">
          <summary className="flex w-fit cursor-pointer list-none items-center rounded [&::-webkit-details-marker]:hidden focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi">
            <span className="border-rand text-ink hover:border-ink inline-flex items-center gap-2 border px-3 py-2 font-sans text-xs font-bold tracking-[0.12em] uppercase">
              <span className="group-open:hidden">{vulIn(KOPIE.uitslag2021_wys_klein, { n: klein.length })}</span>
              <span className="hidden group-open:inline">{KOPIE.uitslag2021_versteek_klein}</span>
            </span>
          </summary>
          <Tabel rye={klein} geldig={u.geldige_stemme} />
        </details>
      )}
      <p className="text-grys mt-2 font-sans text-xs">
        {KOPIE.muni_2021_sortering} · {KOPIE.uitslag2021_bron}
      </p>
    </section>
  );
}
