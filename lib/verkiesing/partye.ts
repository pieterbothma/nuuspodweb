import { vergelykNaam } from "./orden";

/**
 * "Wat die partye sê": each party's latest statement that an editor approved in Telegram.
 * Spec: docs/superpowers/specs/2026-09-17-partyverklarings-design.md
 *
 * The database function only ever returns approved rows and only their public columns, so
 * nothing unapproved can reach this file.
 */
export interface Partyverklaring {
  id: number;
  party: string;
  bron_url: string;
  titel_oorspronklik: string;
  titel_af: string;
  teks_af: string;
  /** False when the party published in Afrikaans and the text is shown as published. */
  vertaal: boolean;
  gepubliseer_om: string;
}

/**
 * Each party's logo, taken from the party's own website and normalised to the same 256 px
 * square (public/partye/). Every card and page shows its party's logo at the same size, so no
 * party is set apart. A party without an entry shows no image — never a stand-in.
 */
const LOGO: Record<string, string> = {
  ActionSA: "actionsa",
  "African Christian Democratic Party (ACDP)": "acdp",
  "African National Congress (ANC)": "anc",
  "Al Jama-ah": "al-jama-ah",
  "Build One South Africa (BOSA)": "bosa",
  "Democratic Alliance (DA)": "da",
  "Economic Freedom Fighters (EFF)": "eff",
  GOOD: "good",
  "Inkatha Freedom Party (IFP)": "ifp",
  "uMkhonto weSizwe Party (MK)": "mk",
  "Vryheidsfront Plus (VF Plus)": "vf-plus",
};

export function partyLogo(party: string): string | null {
  return LOGO[party] ? `/partye/${LOGO[party]}.png` : null;
}

/** The statement's paragraphs, as the translation separated them. */
export function paragrawe(teks: string): string[] {
  return teks.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
}

/** Statements older than this leave the home page: it is about this fortnight. */
const DAE = 14;

/**
 * One card per party, in alphabetical party order with the shared Afrikaans collator. Never
 * newest first: how often a party publishes must not decide where it stands.
 */
export function ordenVerklarings(lys: Partyverklaring[]): Partyverklaring[] {
  const perParty = new Map<string, Partyverklaring>();
  for (const v of lys) {
    const bestaande = perParty.get(v.party);
    if (!bestaande || v.gepubliseer_om > bestaande.gepubliseer_om) perParty.set(v.party, v);
  }
  return [...perParty.values()].sort((a, b) => vergelykNaam(a.party, b.party));
}

async function rpc(naam: string, args: Record<string, unknown>): Promise<Partyverklaring[]> {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !sleutel) return [];
  try {
    const res = await fetch(`${url}/rest/v1/rpc/${naam}`, {
      method: "POST",
      headers: { apikey: sleutel, "Content-Type": "application/json" },
      body: JSON.stringify(args),
      next: { tags: ["partye"], revalidate: 3600 },
    });
    if (!res.ok) {
      console.error(`[partye] ${naam}: ${res.status}`);
      return [];
    }
    return (await res.json()) as Partyverklaring[];
  } catch (err) {
    console.error(`[partye] ${naam}:`, err);
    return [];
  }
}

export async function haalPartyverklarings(): Promise<Partyverklaring[]> {
  return ordenVerklarings(await rpc("partyverklarings_nuutste", { p_dae: DAE }));
}

/** An id from the URL: digits only, so nothing else ever reaches the database. */
export function geldigeVerklaringId(id: string): boolean {
  return /^[1-9]\d{0,15}$/.test(id);
}

export async function haalPartyverklaring(id: string): Promise<Partyverklaring | null> {
  if (!geldigeVerklaringId(id)) return null;
  const [v] = await rpc("partyverklaring", { p_id: Number(id) });
  return v ?? null;
}
