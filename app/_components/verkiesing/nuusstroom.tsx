import { tydEtiket, type StroomItem } from "@/lib/verkiesing/stroom";

const TIPE: Record<string, string> = {
  nasionaal: "Nasionaal",
  streek: "Streek",
  gemeenskap: "Gemeenskap",
  "openbare uitsaaier": "Openbare uitsaaier",
};

/** Headlines render exactly as stored: never clamp, truncate or restyle their case. */
export function Nuusstroom({ items, nou }: { items: StroomItem[]; nou: Date }) {
  return (
    <section id="wat-ander-berig" aria-labelledby="stroom-kop" className="scroll-mt-24">
      <h2 id="stroom-kop" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Wat ander berig
      </h2>
      <p className="text-grys mt-1 font-sans text-xs">Opskrifte soos gepubliseer, met skakels na die oorspronklike berigte.</p>
      {items.length === 0 ? (
        <p className="text-grys mt-4 font-sans text-sm">Nog geen berigte nie.</p>
      ) : (
        <ol className="border-rand divide-rand mt-4 divide-y border-y">
          {items.map((i) => (
            <li key={i.id}>
              <a href={i.url} target="_blank" rel="noopener noreferrer" className="group block py-3 focus-visible:outline-2 focus-visible:outline-siaan">
                <span className="text-grys flex flex-wrap items-baseline gap-x-2 font-sans text-xs tabular-nums">
                  <span>{tydEtiket(i.gepubliseer_om, nou)}</span>
                  <span aria-hidden>·</span>
                  <span className="text-papier font-bold">{i.bron}</span>
                  <span>{TIPE[i.bron_tipe] ?? i.bron_tipe}</span>
                </span>
                <span className="text-papier group-hover:text-siaan mt-1 block font-sans text-[0.95rem] leading-snug break-words">
                  {i.titel}
                  <span aria-hidden className="text-grys"> ↗</span>
                </span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
