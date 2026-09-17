import { vergelykNaam } from "./orden";

/**
 * "Wat die partye sê": each party's latest statement that an editor approved in Telegram.
 * Spec: docs/superpowers/specs/2026-09-17-partyverklarings-design.md
 *
 * The database function only ever returns approved rows and only their public columns, so
 * nothing unapproved can reach this file.
 */
export interface Partyverklaring {
  party: string;
  bron_url: string;
  titel_oorspronklik: string;
  titel_af: string;
  teks_af: string;
  /** False when the party published in Afrikaans and the text is shown as published. */
  vertaal: boolean;
  gepubliseer_om: string;
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

export async function haalPartyverklarings(): Promise<Partyverklaring[]> {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !sleutel) return [];
  try {
    const res = await fetch(`${url}/rest/v1/rpc/partyverklarings_nuutste`, {
      method: "POST",
      headers: { apikey: sleutel, "Content-Type": "application/json" },
      body: JSON.stringify({ p_dae: DAE }),
      next: { tags: ["partye"], revalidate: 3600 },
    });
    if (!res.ok) {
      console.error(`[partye] partyverklarings_nuutste: ${res.status}`);
      return [];
    }
    return ordenVerklarings((await res.json()) as Partyverklaring[]);
  } catch (err) {
    console.error("[partye] partyverklarings_nuutste:", err);
    return [];
  }
}
