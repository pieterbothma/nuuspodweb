/**
 * PostgREST over plain fetch, so Next's fetch cache (revalidate + tags) applies and the site needs
 * no database client. Reads use the publishable key; row access is enforced by RLS.
 */
function konfig() {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  return url && sleutel ? { url, sleutel } : null;
}

/** Returns null (never throws) so a database outage renders fallbacks instead of an error page. */
export async function lees<T>(
  pad: string,
  opts: { tags: string[]; revalidate: number }
): Promise<T[] | null> {
  const k = konfig();
  if (!k) return null;
  try {
    const res = await fetch(`${k.url}/rest/v1/${pad}`, {
      headers: { apikey: k.sleutel },
      next: { tags: opts.tags, revalidate: opts.revalidate },
    });
    if (!res.ok) {
      console.error(`[supabase] GET ${pad}: ${res.status}`);
      return null;
    }
    return (await res.json()) as T[];
  } catch (err) {
    console.error(`[supabase] GET ${pad}:`, err);
    return null;
  }
}

export async function voegIn(tabel: string, ry: Record<string, unknown>): Promise<boolean> {
  const k = konfig();
  if (!k) return false;
  try {
    const res = await fetch(`${k.url}/rest/v1/${tabel}`, {
      method: "POST",
      headers: { apikey: k.sleutel, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify(ry),
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}
