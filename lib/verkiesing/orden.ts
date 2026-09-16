/**
 * Neutral ordering for everything the ward finder shows about candidates, parties and
 * 2021 councils.
 *
 * Hard rule (global constraints, "Neutral display"): ordering is alphabetical until the
 * IEC ballot draw on 23 September 2026, then the official ballot position. It must NEVER
 * consider seats, votes, list length or any other measure of a party's size. The
 * "sorteer nooit op setels of lysgrootte nie" test guards that.
 *
 * The row types live here rather than in wyksoeker.ts because this is the lower layer:
 * wyksoeker.ts imports these helpers and re-exports the types, so pages may import either.
 */

export type Kandidaat = {
  volle_naam: string;
  van: string;
  party_naam: string | null;
  onafhanklik: boolean;
  lys_posisie: number | null;
};

export type PartyLys = {
  party_naam: string;
  /** Official ballot position from the IEC draw; null until the draw has happened. */
  posisie: number | null;
  kandidate: Kandidaat[];
};

export type Volgorde = "alfabeties" | "stembrief";

export type Raad2021Rooi = {
  party_naam: string;
  setels_wyk: number;
  setels_pv: number;
  setels_totaal: number;
};

export type Raad2021 = {
  raadsgrootte: number;
  onafhanklike_setels: number;
  rye: Raad2021Rooi[];
  geenMeerderheid: boolean;
};

/**
 * Afrikaans collation. sensitivity "base" folds diacritics and case, so ÅBERG sorts with
 * A rather than after Z; numeric:true keeps "Ward 2" before "Ward 10" in any label reuse.
 */
const KOLLASIE = new Intl.Collator("af-ZA", { sensitivity: "base", numeric: true });

/** Shared collator so every list on every page sorts names identically. */
export function vergelykNaam(a: string, b: string): number {
  return KOLLASIE.compare(a, b);
}

export function sorteerKandidate(
  kandidate: Kandidaat[],
  volgorde: Volgorde = "alfabeties"
): Kandidaat[] {
  // Ordering is neutral: alphabetical until the IEC draw, then the official ballot position.
  // It must never consider seats, votes or list length.
  return [...kandidate].sort((a, b) =>
    volgorde === "stembrief" && a.lys_posisie != null && b.lys_posisie != null
      ? a.lys_posisie - b.lys_posisie
      : KOLLASIE.compare(a.van, b.van) || KOLLASIE.compare(a.volle_naam, b.volle_naam)
  );
}

/**
 * Ballot order only once every list carries a drawn position; a partially drawn ballot
 * would mix two orderings, which is worse than staying alphabetical. Never by list length.
 */
export function sorteerPartyLyste(lyste: PartyLys[]): PartyLys[] {
  const almalGetrek = lyste.length > 0 && lyste.every((l) => l.posisie != null);
  return [...lyste].sort((a, b) =>
    almalGetrek
      ? (a.posisie as number) - (b.posisie as number)
      : KOLLASIE.compare(a.party_naam, b.party_naam)
  );
}

/**
 * True when no single party held more than half of the 2021 council. Measured against the
 * full council size including independent ward councillors (Piet's ruling, 2026-09-15):
 * the party seat totals alone under-count a council that seated independents.
 *
 * A majority is strictly more than half, so 6 of 11 is a majority and 5 of 11 is not.
 * Returns false — no claim — when the council size or the party rows are missing, because
 * every number on a page must come from a real row.
 */
export function geenMeerderheid(raad: Omit<Raad2021, "geenMeerderheid">): boolean {
  const grootte = raad.raadsgrootte;
  if (!Number.isFinite(grootte) || grootte <= 0) return false;
  if (raad.rye.length === 0) return false;
  const grootste = Math.max(...raad.rye.map((r) => r.setels_totaal));
  return grootste * 2 <= grootte;
}
