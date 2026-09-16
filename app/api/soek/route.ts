import type { SoekRy } from "@/lib/verkiesing/wyksoeker";

/**
 * Backs the hero search box. Reads go through plain `fetch` (not `lib/supabase-rest.ts`'s
 * `lees`) because this is a POST RPC call, not a PostgREST table read, but the never-throw
 * shape is the same: any missing config or upstream failure degrades to an empty result,
 * never a thrown error the client would have to handle.
 */
function konfig() {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  return url && sleutel ? { url, sleutel } : null;
}

export async function GET(req: Request): Promise<Response> {
  const { searchParams } = new URL(req.url);
  const ruQ = searchParams.get("q");

  // No query yet (the box is empty) — nothing to search, and no reason to touch the database.
  if (ruQ === null) {
    return Response.json({ resultate: [] });
  }

  const q = ruQ.trim();
  if (q.length < 2) {
    return Response.json({ fout: "Tik ten minste 2 karakters" }, { status: 400 });
  }

  const k = konfig();
  if (!k) {
    return Response.json({ resultate: [] });
  }

  try {
    // `q` also rides along in the query string, purely so each distinct search term gets
    // its own entry in Next's fetch cache — the RPC itself only reads the JSON body.
    const res = await fetch(`${k.url}/rest/v1/rpc/soek?q=${encodeURIComponent(q)}`, {
      method: "POST",
      headers: { apikey: k.sleutel, "Content-Type": "application/json" },
      body: JSON.stringify({ q }),
      next: { revalidate: 3600, tags: ["soek"] },
    });
    if (!res.ok) {
      console.error(`[soek] RPC-status ${res.status}`);
      return Response.json({ resultate: [] });
    }
    const resultate = (await res.json()) as SoekRy[];
    return Response.json({ resultate });
  } catch (err) {
    console.error("[soek] RPC-fout:", err);
    return Response.json({ resultate: [] });
  }
}
