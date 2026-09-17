import { lees } from "@/lib/supabase-rest";

/**
 * "Die nuutste van die IEC": the IEC's own press releases, headline verbatim, linked to the
 * release on elections.org.za. The admin job on hq loads them hourly and expires the `ovk` tag.
 */
export interface OvkNuus {
  id: number;
  titel: string;
  datum: string;
  url: string;
}

export const OVK_NUUSLYS = "https://www.elections.org.za/pw/News-And-Media/News-List/IECNews";

export async function haalOvkNuus(perk = 5): Promise<OvkNuus[]> {
  const rye = await lees<OvkNuus>(
    `ovk_nuus?select=id,titel,datum,url&order=datum.desc,id.desc&limit=${perk}`,
    { tags: ["ovk"], revalidate: 3600 }
  );
  return rye ?? [];
}
