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

function getal(v: unknown): number {
  if (typeof v === "number") return v;
  if (typeof v === "string") return Number.parseFloat(v);
  return Number.NaN;
}

/**
 * "Find my ward" from a browser geolocation point.
 *
 * **POST, not GET, and that is a privacy decision, not a REST one.** Coordinates are
 * personal data (global constraints: "Geolocation coordinates are never stored or logged")
 * and the hosting platform logs full request URLs, so a point may never ride in a query
 * string. It arrives in the JSON body instead. Beyond that, this handler never writes
 * `lat`/`lng` into a console line, an error message or a cache key, and reads upstream with
 * `cache: "no-store"` so the point never enters Next's fetch cache either.
 */
export async function POST(req: Request): Promise<Response> {
  let lat = Number.NaN;
  let lng = Number.NaN;
  try {
    const liggaam = (await req.json()) as unknown;
    if (liggaam && typeof liggaam === "object") {
      lat = getal((liggaam as Record<string, unknown>).lat);
      lng = getal((liggaam as Record<string, unknown>).lng);
    }
  } catch {
    // Unparseable body — nothing logged, since a parse error can quote the body.
    return Response.json({ fout: "Ongeldige koördinate" }, { status: 400 });
  }

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

/** A GET would put the point in a URL the platform logs. Refuse it outright. */
export function GET(): Response {
  return Response.json({ fout: "Gebruik POST" }, { status: 405 });
}
