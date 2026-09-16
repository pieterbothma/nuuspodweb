/**
 * Community-paper headlines linked to a ward or a municipality by place name. The admin cron
 * fills `plaaslike_nuus`; matching and de-duplication happen in the database
 * (`plaaslike_nuus_vir_wyk` / `plaaslike_nuus_vir_muni`). Headlines are shown verbatim.
 */

export type NuusVlak = "wyk" | "dorp" | "munisipaliteit";

export type PlaaslikeStorie = {
  vlak: NuusVlak;
  plek: string;
  titel: string;
  bron: string;
  url: string;
  gepubliseer_om: string;
};

export type NuusGroep = { vlak: NuusVlak; plek: string | null; stories: PlaaslikeStorie[] };

const KAS = { tags: ["plaaslik"], revalidate: 900 };
const ORDE: NuusVlak[] = ["wyk", "dorp", "munisipaliteit"];

async function rpc<T>(naam: string, args: Record<string, unknown>): Promise<T[]> {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !sleutel) return [];
  try {
    const res = await fetch(`${url}/rest/v1/rpc/${naam}`, {
      method: "POST",
      headers: { apikey: sleutel, "Content-Type": "application/json" },
      body: JSON.stringify(args),
      next: KAS,
    });
    if (!res.ok) {
      console.error(`[plaaslik] ${naam}: ${res.status}`);
      return [];
    }
    return (await res.json()) as T[];
  } catch (err) {
    console.error(`[plaaslik] ${naam}:`, err);
    return [];
  }
}

/**
 * Groups a ward's stories by level, narrowest first. Within one level the heading can only
 * name a place when every story shares it ("In Krugersdorp"); otherwise `plek` is null and each
 * story carries its own place.
 */
export function groepeer(stories: PlaaslikeStorie[]): NuusGroep[] {
  return ORDE.flatMap((vlak) => {
    const hier = stories.filter((s) => s.vlak === vlak);
    if (hier.length === 0) return [];
    const plekke = new Set(hier.map((s) => s.plek));
    return [{ vlak, plek: plekke.size === 1 ? hier[0].plek : null, stories: hier }];
  });
}

export async function haalWykNuus(wykId: string): Promise<NuusGroep[]> {
  return groepeer(await rpc<PlaaslikeStorie>("plaaslike_nuus_vir_wyk", { p_wyk_id: wykId, p_perk: 3 }));
}

/** A municipality's stories; `plek` is null when the story names the municipality itself. */
export type MuniStorie = Omit<PlaaslikeStorie, "vlak" | "plek"> & { plek: string | null };

export async function haalMuniNuus(kode: string): Promise<MuniStorie[]> {
  return rpc<MuniStorie>("plaaslike_nuus_vir_muni", { p_kode: kode, p_perk: 8 });
}
