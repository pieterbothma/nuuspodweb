import { lees } from "@/lib/supabase-rest";
import { balanseer, type StroomItem } from "./stroom";

export interface Episode {
  video_id: string;
  titel: string;
  uitsaaidatum: string;
}

/** The first Verkiesings-Vrydag, shown if the episodes table is empty or unreachable. */
export const TERUGVAL_EPISODE: Episode = {
  video_id: "Y9HiKkP7Rmo",
  titel: "Verkiesings-Vrydag: Die DA se skynheiligheid Vrydag 11 September 2026",
  uitsaaidatum: "2026-09-11",
};

export async function haalStroom(): Promise<StroomItem[]> {
  const rye = await lees<StroomItem>(
    "nuusstroom?select=id,titel,bron,bron_tipe,url,gepubliseer_om&order=gepubliseer_om.desc&limit=60",
    { tags: ["nuusstroom"], revalidate: 300 }
  );
  return balanseer(rye ?? []);
}

export async function haalEpisodes(): Promise<Episode[]> {
  const rye = await lees<Episode>(
    "episodes?select=video_id,titel,uitsaaidatum&order=uitsaaidatum.desc&limit=12",
    { tags: ["episodes"], revalidate: 3600 }
  );
  return rye && rye.length > 0 ? rye : [TERUGVAL_EPISODE];
}
