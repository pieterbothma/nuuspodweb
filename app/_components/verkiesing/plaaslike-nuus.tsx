import { KOPIE } from "@/lib/verkiesing/kopie";
import type { NuusGroep, PlaaslikeStorie } from "@/lib/verkiesing/plaaslik";
import { relatieweTyd } from "@/lib/verkiesing/stroom";
import { vulIn } from "./stembriewe";

type Storie = Omit<PlaaslikeStorie, "vlak" | "plek"> & { plek: string | null };

/**
 * Community-paper headlines, verbatim, each linking out. Plain monochrome rows: no party names
 * reach this list (the admin drops them) and nothing here is coloured by who it is about.
 * Renders nothing at all when there is nothing to show — never an empty heading, and never a
 * promise that news is coming.
 */
function Lys({ stories, nou, wysPlek }: { stories: Storie[]; nou: Date; wysPlek: boolean }) {
  return (
    <ul className="border-rand mt-3 border-b">
      {stories.map((s) => (
        <li key={s.url} data-plaaslike-storie className="border-rand border-t">
          <a
            href={s.url}
            target="_blank"
            rel="noopener"
            className="group block py-3.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
          >
            <span className="text-ink group-hover:text-rooi block font-sans text-[0.9375rem] leading-snug font-bold break-words">
              {s.titel}
            </span>
            <span className="text-grys mt-1 flex flex-wrap gap-x-1.5 font-sans text-sm">
              <span>{s.bron}</span>
              {wysPlek && s.plek && (
                <>
                  <span aria-hidden>·</span>
                  <span>{s.plek}</span>
                </>
              )}
              <span aria-hidden>·</span>
              <time dateTime={s.gepubliseer_om} className="tabular-nums">
                {relatieweTyd(s.gepubliseer_om, nou)}
              </time>
              <span aria-hidden>↗</span>
              <span className="sr-only"> (maak in &apos;n nuwe oortjie oop)</span>
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

function groepOpskrif(g: NuusGroep, muniNaam: string): string {
  if (g.vlak === "wyk") return KOPIE.plaaslik_omgewing;
  if (g.vlak === "dorp" && g.plek) return vulIn(KOPIE.plaaslik_dorp, { q: g.plek });
  return vulIn(KOPIE.plaaslik_munisipaliteit, { q: muniNaam });
}

export function WykNuus({ groepe, muniNaam, nou }: { groepe: NuusGroep[]; muniNaam: string; nou: Date }) {
  if (groepe.length === 0) return null;
  return (
    <section aria-labelledby="plaaslike-nuus" data-plaaslike-nuus className="scroll-mt-24">
      <h2 id="plaaslike-nuus" className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase">
        {KOPIE.plaaslik_opskrif}
      </h2>
      <p className="text-grys mt-1.5 font-sans text-sm">{KOPIE.plaaslik_onderskrif}</p>
      <div className="mt-5 grid gap-7 md:grid-cols-2 lg:grid-cols-3">
        {groepe.map((g) => (
          <div key={g.vlak} data-nuus-vlak={g.vlak}>
            <h3 className="text-ink font-sans text-sm font-bold">{groepOpskrif(g, muniNaam)}</h3>
            {/* The neighbourhood group always names each story's place: "Uit jou omgewing"
                alone does not say which suburb a headline is about. */}
            <Lys stories={g.stories} nou={nou} wysPlek={g.vlak === "wyk" || (g.vlak === "dorp" && g.plek === null)} />
          </div>
        ))}
      </div>
    </section>
  );
}

export function MuniNuus({ stories, muniNaam, nou }: { stories: Storie[]; muniNaam: string; nou: Date }) {
  if (stories.length === 0) return null;
  return (
    <section aria-labelledby="plaaslike-nuus" data-plaaslike-nuus className="scroll-mt-24">
      <h2 id="plaaslike-nuus" className="text-rooi-teks font-sans text-[0.8125rem] font-black tracking-[0.22em] uppercase">
        {vulIn(KOPIE.plaaslik_muni_opskrif, { q: muniNaam })}
      </h2>
      <p className="text-grys mt-1.5 font-sans text-sm">{KOPIE.plaaslik_onderskrif}</p>
      <div className="max-w-3xl">
        <Lys stories={stories} nou={nou} wysPlek />
      </div>
    </section>
  );
}
