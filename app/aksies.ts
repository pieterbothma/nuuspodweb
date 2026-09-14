"use server";

import { voegIn } from "@/lib/supabase-rest";

/** Anonymous yes/no only: the page path and the answer, nothing that identifies the reader. */
export async function stuurTerugvoer(bladsy: string, gevind: boolean): Promise<boolean> {
  if (typeof bladsy !== "string" || !bladsy.startsWith("/") || bladsy.length > 200) return false;
  if (typeof gevind !== "boolean") return false;
  return voegIn("terugvoer", { bladsy, gevind });
}
