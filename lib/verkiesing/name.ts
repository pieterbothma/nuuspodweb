/**
 * Afrikaans display names for the two proper nouns that reach the site in English.
 *
 * The MDB and the IEC publish municipality and province names in English ("City of Cape
 * Town", "Western Cape"), and every name on a page must come from a database row — so the
 * rows keep the official English name and these two helpers decide only what a reader sees.
 * Nothing here is written back to the database, used in a query, or used as a key.
 *
 * Scope is deliberately narrow (Piet's ruling, 2026-09-16):
 *  - all nine provinces, because "Wes-Kaap" reads as Afrikaans and "Western Cape" does not;
 *  - the eight metros only, because their official names are English descriptions ("City
 *    of …") rather than place names;
 *  - every other municipality keeps its official name, because Stellenbosch, Kou-Kamma and
 *    Mafikeng are the same word in both languages and inventing translations for 250-odd
 *    councils would be a model-generated claim about a place.
 *
 * An unknown key always falls back to the input rather than to an empty string: a missing
 * translation must never blank a heading.
 */

/** Province names exactly as `munisipaliteite.provinsie` stores them. */
const PROVINSIES: Record<string, string> = {
  "Eastern Cape": "Oos-Kaap",
  "Free State": "Vrystaat",
  Gauteng: "Gauteng",
  "KwaZulu-Natal": "KwaZulu-Natal",
  Limpopo: "Limpopo",
  Mpumalanga: "Mpumalanga",
  "North West": "Noordwes",
  "Northern Cape": "Noord-Kaap",
  "Western Cape": "Wes-Kaap",
};

/**
 * The eight metros, keyed on the IEC code rather than the English name, so a local
 * municipality that happens to share a name is never renamed. Verified against
 * `munisipaliteite` (2026-09-16): BUF, CPT, EKU, ETH, JHB, MAN, NMA, TSH.
 */
const METROS: Record<string, string> = {
  BUF: "Buffalo City",
  CPT: "Stad Kaapstad",
  EKU: "Ekurhuleni",
  ETH: "eThekwini",
  JHB: "Stad Johannesburg",
  MAN: "Mangaung",
  NMA: "Nelson Mandela Baai",
  TSH: "Stad Tshwane",
};

/** "Western Cape" → "Wes-Kaap". Anything else comes back unchanged. */
export function provinsieNaam(provinsie: string): string {
  return PROVINSIES[provinsie] ?? provinsie;
}

/**
 * The name to show for a municipality. `kode` is the IEC/MDB code and `naam` the official
 * name from the row; a metro gets its Afrikaans name, everything else keeps `naam`. Falls
 * back to the code if a row ever arrives without a name, so a heading is never empty.
 */
export function muniNaam(kode: string, naam: string): string {
  return METROS[kode] ?? (naam || kode);
}
