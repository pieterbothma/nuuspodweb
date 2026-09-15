import { revalidateTag } from "next/cache";

const TAGS = new Set(["nuusstroom", "episodes"]);

/** Called by the admin when Piet hides a headline or a new episode lands. */
export async function POST(req: Request) {
  const geheim = process.env.HERLAAI_SECRET;
  if (!geheim || req.headers.get("authorization") !== `Bearer ${geheim}`) {
    return Response.json({ fout: "Nie gemagtig nie" }, { status: 401 });
  }
  const { tag } = (await req.json().catch(() => ({}))) as { tag?: string };
  if (!tag || !TAGS.has(tag)) {
    return Response.json({ fout: "Onbekende tag" }, { status: 400 });
  }
  // expire: 0 so a hidden headline is gone on the next request, not after a stale window.
  revalidateTag(tag, { expire: 0 });
  return Response.json({ ok: true, tag });
}
