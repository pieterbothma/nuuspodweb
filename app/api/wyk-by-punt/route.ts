type WykByPunt = {
  wyk_id: string;
  wyk_nr: number;
  muni_kode: string;
  muni_naam: string;
};

function konfig() {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  return url && sleutel ? { url, sleutel } : null;
}

// A generous bounding box around South Africa (including Prince Edward Islands' longitude
// span is not needed here — this only has to reject obviously-wrong points, not draw a
// precise border; the `vind_wyk` RPC is the real authority on what falls inside a ward).
const LAT_MIN = -35;
const LAT_MAX = -21;
const LNG_MIN = 15;
const LNG_MAX = 34;

/**
 * "Find my ward" from a browser geolocation point. Coordinates are personal data (global
 * constraints: "Geolocation coordinates are never stored or logged") — this handler never
 * writes `lat`/`lng` into a console line, an error message or a cache key, and reads with
 * `cache: "no-store"` so the point itself never enters Next's fetch cache either.
 */
export async function GET(req: Request): Promise<Response> {
  const { searchParams } = new URL(req.url);
  const lat = Number.parseFloat(searchParams.get("lat") ?? "");
  const lng = Number.parseFloat(searchParams.get("lng") ?? "");

  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng) ||
    lat < LAT_MIN ||
    lat > LAT_MAX ||
    lng < LNG_MIN ||
    lng > LNG_MAX
  ) {
    return Response.json({ fout: "Ongeldige koördinate" }, { status: 400 });
  }

  const k = konfig();
  if (!k) {
    return Response.json({ wyk: null });
  }

  try {
    const res = await fetch(`${k.url}/rest/v1/rpc/vind_wyk`, {
      method: "POST",
      headers: { apikey: k.sleutel, "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lng }),
      cache: "no-store",
    });
    if (!res.ok) {
      // Status only — never the point that produced it.
      console.error(`[wyk-by-punt] opsoek misluk: ${res.status}`);
      return Response.json({ wyk: null });
    }
    const rye = (await res.json()) as WykByPunt[];
    return Response.json({ wyk: rye[0] ?? null });
  } catch {
    // No error detail logged: the caught error can itself carry the request body/URL,
    // which would leak the coordinates into the log.
    console.error("[wyk-by-punt] opsoek misluk");
    return Response.json({ wyk: null });
  }
}
