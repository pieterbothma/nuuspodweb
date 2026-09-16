import { bronAfkorting, relatieweTyd, type StroomItem } from "@/lib/verkiesing/stroom";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { NuusstroomLys, type StroomPos } from "./nuusstroom-lys";

const TIPE: Record<string, string> = {
  nasionaal: "Nasionaal",
  streek: "Streek",
  gemeenskap: "Gemeenskap",
  "openbare uitsaaier": "Openbare uitsaaier",
};

/** Server component: computes the relative time server-side so the client never has to guess "nou" and risk a hydration mismatch. */
export function Nuusstroom({ items, nou }: { items: StroomItem[]; nou: Date }) {
  const posse: StroomPos[] = items.map((i) => ({
    id: i.id,
    titel: i.titel,
    bron: i.bron,
    bronTipe: TIPE[i.bron_tipe] ?? i.bron_tipe,
    afkorting: bronAfkorting(i.bron),
    tyd: relatieweTyd(i.gepubliseer_om, nou),
    iso: i.gepubliseer_om,
    url: i.url,
  }));

  return (
    <section id="wat-ander-berig" aria-labelledby="stroom-kop" className="scroll-mt-24">
      <h2 id="stroom-kop" className="font-sans text-[0.8125rem] font-black tracking-[0.22em] text-rooi-teks uppercase">
        {KOPIE.stroom_opskrif}
      </h2>
      <p className="text-grys mt-1 font-sans text-xs">{KOPIE.stroom_onderskrif}</p>
      <NuusstroomLys items={posse} />
    </section>
  );
}
