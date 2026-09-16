import { lees } from "@/lib/supabase-rest";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { vulIn } from "./stembriewe";
import { Terugvoer } from "./terugvoer";

/**
 * The attribution strip that closes the ward page and the municipality page: who the rows
 * come from, how old they are, where the reader can check them, and the one-question
 * feedback widget.
 *
 * Both pages read the date once and pass it in, so the strip itself makes no request.
 */

/**
 * The OVK's own ward and voting-station finder — the "list" a reader can check the page
 * against. One constant, so both pages link to the same place.
 */
export const OVK_LYS_SKAKEL = "https://maps.elections.org.za/vsfinder/";

const KAS = { tags: ["wyke"], revalidate: 3600 };

/**
 * The newest `bron_datum` in `data_weergawes` — the publication date of the data behind the
 * page. Lives here rather than in `lib/verkiesing/wyksoeker.ts` because the strip is the only
 * thing that shows it; Task 7 imports it from here too. `lees` returns null rather than
 * throwing, so a missing row or an outage simply drops the "laas bygewerk" clause.
 */
export async function haalBronDatum(): Promise<string | null> {
  const rye = await lees<{ bron_datum: string | null }>(
    "data_weergawes?select=bron_datum&bron_datum=not.is.null&order=bron_datum.desc&limit=1",
    KAS
  );
  return rye?.[0]?.bron_datum ?? null;
}

const AFRIKAANS = new Intl.DateTimeFormat("af-ZA", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

/** "2026-09-16" → "16 September 2026". Midday UTC, so no timezone can shift the day. */
function skryfDatum(datum: string): string | null {
  const t = Date.parse(`${datum}T12:00:00Z`);
  return Number.isNaN(t) ? null : AFRIKAANS.format(new Date(t));
}

export function BronStrook({
  bronDatum,
  bronSkakel,
  /**
   * A page-specific second line, e.g. the municipality page's note about the 2021 seat
   * calculation (`KOPIE.bron_nota_setels_2021`). Unset on the ward page, whose rows need no
   * qualifier beyond the shared attribution.
   */
  nota,
  /**
   * Whether the strip asks the feedback question itself. A page that also mounts `<Voet />`
   * passes `false`, so the reader is asked once — the ward page does exactly that.
   */
  metTerugvoer = true,
}: {
  bronDatum: string | null;
  bronSkakel: string;
  nota?: string;
  metTerugvoer?: boolean;
}) {
  const datum = bronDatum ? skryfDatum(bronDatum) : null;

  return (
    <div className="border-rand mt-12 flex flex-col items-start gap-4 border-t pt-6 sm:flex-row sm:items-center sm:gap-6">
      <div className="text-grys flex-1 font-sans text-sm leading-relaxed">
        <p>
          {KOPIE.bron_ovk}
          {datum ? ` · ${vulIn(KOPIE.laas_bygewerk, { q: datum })}` : ""} ·{" "}
          <a
            href={bronSkakel}
            target="_blank"
            rel="noopener"
            className="text-ink decoration-rand underline underline-offset-4 hover:decoration-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
          >
            {KOPIE.bron_ovk_skakel} ↗︎
          </a>
        </p>
        {nota && <p className="mt-1">{nota}</p>}
      </div>
      {metTerugvoer && <Terugvoer />}
    </div>
  );
}
