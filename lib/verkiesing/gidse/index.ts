import { mdNaBlokke, type Gids, type GidsBron } from "./tipes";
import { spesialeStemme } from "./spesiale-stemme";
import { waarStemEk } from "./waar-stem-ek";
import { watOmSaamTeBring } from "./wat-om-saam-te-bring";
import { wykEnPrStembrief } from "./wyk-en-pr-stembrief";

function bou(bron: GidsBron): Gids {
  const blokke = mdNaBlokke(bron.lyf);
  const lede = blokke.find((b) => b.tipe === "p");
  return { ...bron, blokke, opsomming: lede?.tipe === "p" ? lede.teks.replace(/\*\*/g, "") : "" };
}

export const GIDSE: Gids[] = [wykEnPrStembrief, spesialeStemme, watOmSaamTeBring, waarStemEk].map(bou);

export function gepubliseerdeGidse(): Gids[] {
  return GIDSE.filter((g) => g.gepubliseer);
}

export function vindGids(slug: string): Gids | undefined {
  return gepubliseerdeGidse().find((g) => g.slug === slug);
}
