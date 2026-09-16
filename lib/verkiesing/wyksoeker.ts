import { lees } from "@/lib/supabase-rest";
import {
  geenMeerderheid,
  sorteerKandidate,
  sorteerPartyLyste,
  vergelykNaam,
  type Kandidaat,
  type PartyLys,
  type Raad2021,
  type Raad2021Rooi,
  type Volgorde,
} from "./orden";

/**
 * Data layer for the ward finder: the ward page, the municipality page, the API routes and
 * the sitemap all read through here, so every page gets the same rows, the same cache tags
 * and the same neutral ordering.
 *
 * Three rules hold everywhere in this file:
 *  1. `lees` returns null instead of throwing, so a database outage must degrade to an empty
 *     result the page can render as a fallback — never a thrown error page.
 *  2. Candidates and the ballot draw are not loaded yet, so every candidate read must return
 *     a sensible empty result; the pages render that as "not yet loaded".
 *  3. Ordering goes through orden.ts and never considers seats, votes or list length.
 */

export type { Kandidaat, PartyLys, Raad2021, Raad2021Rooi } from "./orden";

export type Wyk = {
  wyk_id: string;
  wyk_nr: number;
  muni_kode: string;
  muni_naam: string;
  muni_tipe: "metro" | "plaaslik" | "distrik";
  distrik_kode: string | null;
  distrik_naam: string | null;
  provinsie: string;
};

export type Stemstasie = {
  vd_nommer: string;
  naam: string;
  /** null when the source row has no usable address — the page then shows the name only. */
  adres: string | null;
};

/**
 * One row of the `soek` RPC's result — a place (main place or municipality) or a voting
 * station matched by name. `wyk_ids`/`wyk_nrs` are parallel arrays: a place can span more
 * than one ward, a station belongs to exactly one. `teiken` is the id to navigate to
 * (a ward id for a single-ward match, otherwise null and the UI offers a municipality/list
 * view instead). Re-exported here so `/api/soek` and its callers share one type.
 */
export type SoekRy = {
  soort: "plek" | "stemlokaal";
  etiket: string;
  muni_kode: string;
  muni_naam: string;
  /** The municipality's province, on every row — the search's second subtitle line. */
  provinsie: string;
  /** A station's street address; null for a place row, and null for a station whose
   * source address is empty (that station shows its name and municipality only). */
  adres: string | null;
  wyk_ids: string[];
  wyk_nrs: number[];
  teiken: string | null;
  rang: number;
};

export type Stembriewe = {
  wyk: Kandidaat[];
  pv_plaaslik: PartyLys[];
  pv_distrik: PartyLys[];
  volgorde: Volgorde;
};

export type MuniOpsomming = {
  kode: string;
  naam: string;
  tipe: string;
  provinsie: string;
  distrik_naam: string | null;
  wyke: { wyk_id: string; wyk_nr: number }[];
  partye: string[];
  raad2021: Raad2021 | null;
};

// ---------------------------------------------------------------------------
// Cache + paging
// ---------------------------------------------------------------------------

const REVALIDEER = 3600;
/** Geography: ward, municipality and voting-station rows. Revalidated by the loader. */
const KAS_WYKE = { tags: ["wyke"], revalidate: REVALIDEER };
/** Candidate lists and the IEC ballot draw — the rows that change during nomination season. */
const KAS_KANDIDATE = { tags: ["kandidate"], revalidate: REVALIDEER };

/** PostgREST caps a response at 1,000 rows, so anything unbounded has to be paged. */
const BLADSY = 1000;
/** 4,485 wards need 5 pages; the cap only stops a runaway loop. */
const MAX_BLADSYE = 40;

/**
 * Pages a read until a short page arrives. `pad` must already carry its query string and a
 * stable `order=`, otherwise offset paging can repeat or skip rows. A null page (database
 * down) ends the loop and returns what was collected — a partial sitemap beats no sitemap.
 */
async function leesAlles<T>(pad: string, opts: { tags: string[]; revalidate: number }): Promise<T[]> {
  const uit: T[] = [];
  for (let bladsy = 0; bladsy < MAX_BLADSYE; bladsy++) {
    const rye = await lees<T>(`${pad}&limit=${BLADSY}&offset=${bladsy * BLADSY}`, opts);
    if (!rye) break;
    uit.push(...rye);
    if (rye.length < BLADSY) break;
  }
  return uit;
}

// ---------------------------------------------------------------------------
// Id validation — an invalid id never reaches the database
// ---------------------------------------------------------------------------

const WYK_ID = /^\d{8}$/;
/** WC024, TSH, DC2, NW383 — the IEC/MDB code shapes, letters always upper case. */
const MUNI_KODE = /^[A-Z]{2,3}\d{0,3}$/;

export function geldigeWykId(wykId: string): boolean {
  return WYK_ID.test(wykId);
}

export function geldigeMuniKode(kode: string): boolean {
  return MUNI_KODE.test(kode);
}

// ---------------------------------------------------------------------------
// Row shapes as PostgREST returns them
// ---------------------------------------------------------------------------

type Ingebed<T> = T | T[] | null;

/** A many-to-one embed comes back as an object, but older PostgREST wraps it in an array. */
function een<T>(v: Ingebed<T>): T | null {
  if (v == null) return null;
  return Array.isArray(v) ? (v[0] ?? null) : v;
}

type WykRy = {
  wyk_id: string;
  wyk_nr: number;
  muni_kode: string;
  munisipaliteite: Ingebed<{
    naam: string;
    tipe: string;
    distrik_kode: string | null;
    provinsie: string;
  }>;
};

type KandidaatRy = {
  volle_naam: string;
  van: string;
  onafhanklik: boolean;
  lys_posisie: number | null;
  partye: Ingebed<{ naam: string }>;
};

type VolgordeRy = {
  muni_kode: string;
  stembrief: string;
  posisie: number;
  partye: Ingebed<{ naam: string }>;
};

const KANDIDAAT_KOLOMME = "volle_naam,van,onafhanklik,lys_posisie,partye(naam)";

function naKandidaat(ry: KandidaatRy): Kandidaat {
  return {
    volle_naam: ry.volle_naam,
    van: ry.van,
    party_naam: een(ry.partye)?.naam ?? null,
    onafhanklik: ry.onafhanklik,
    lys_posisie: ry.lys_posisie ?? null,
  };
}

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

/** The district's name, read separately — see the comment in `haalWyk`. */
async function haalMuniNaam(kode: string): Promise<string | null> {
  if (!geldigeMuniKode(kode)) return null;
  const rye = await lees<{ naam: string }>(
    `munisipaliteite?kode=eq.${kode}&select=naam&limit=1`,
    KAS_WYKE
  );
  return rye?.[0]?.naam ?? null;
}

export async function haalWyk(wykId: string): Promise<Wyk | null> {
  if (!geldigeWykId(wykId)) return null;
  const rye = await lees<WykRy>(
    `wyke?wyk_id=eq.${wykId}&select=wyk_id,wyk_nr,muni_kode,munisipaliteite!inner(naam,tipe,distrik_kode,provinsie)&limit=1`,
    KAS_WYKE
  );
  const ry = rye?.[0];
  const muni = ry ? een(ry.munisipaliteite) : null;
  if (!ry || !muni) return null;

  // munisipaliteite.distrik_kode is a self-referencing FK, and PostgREST cannot
  // disambiguate the direction of that self-relation when it is nested a second level
  // deep under wyke — so the district's name comes from a second, separately cached read
  // rather than from a nested embed. One extra request per ward page, cached for an hour.
  const distrik_naam = muni.distrik_kode ? await haalMuniNaam(muni.distrik_kode) : null;

  return {
    wyk_id: ry.wyk_id,
    wyk_nr: ry.wyk_nr,
    muni_kode: ry.muni_kode,
    muni_naam: muni.naam,
    muni_tipe: muni.tipe as Wyk["muni_tipe"],
    distrik_kode: muni.distrik_kode ?? null,
    distrik_naam,
    provinsie: muni.provinsie,
  };
}

export async function haalStemstasies(wykId: string): Promise<Stemstasie[]> {
  if (!geldigeWykId(wykId)) return [];
  const rye = await lees<{ vd_nommer: string; naam: string; adres: string | null }>(
    `stemstasies?wyk_id=eq.${wykId}&select=vd_nommer,naam,adres&order=naam.asc`,
    KAS_WYKE
  );
  return (rye ?? []).map((r) => ({
    vd_nommer: r.vd_nommer,
    naam: r.naam,
    // An empty address shows the station name only (Piet's ruling, 2026-09-15).
    adres: r.adres?.trim() ? r.adres.trim() : null,
  }));
}

/** Groups PR candidates per party and attaches each party's drawn ballot position. */
function groepeerPerParty(
  rye: KandidaatRy[],
  posisies: Map<string, number>,
  volgorde: Volgorde
): PartyLys[] {
  const perParty = new Map<string, Kandidaat[]>();
  for (const ry of rye) {
    const k = naKandidaat(ry);
    // A PR list always belongs to a party; an unnamed party would be an unusable row.
    const naam = k.party_naam;
    if (!naam) continue;
    const lys = perParty.get(naam);
    if (lys) lys.push(k);
    else perParty.set(naam, [k]);
  }
  const lyste: PartyLys[] = [...perParty].map(([party_naam, kandidate]) => ({
    party_naam,
    posisie: posisies.get(party_naam) ?? null,
    // Within one list the ordering follows the same flag the page shows the reader:
    // alphabetical before the draw, the official list position after it. Comparing
    // candidates inside a single party never ranks parties against each other.
    kandidate: sorteerKandidate(kandidate, volgorde),
  }));
  return sorteerPartyLyste(lyste);
}

export async function haalStembriewe(wyk: Wyk): Promise<Stembriewe> {
  const leeg: Stembriewe = { wyk: [], pv_plaaslik: [], pv_distrik: [], volgorde: "alfabeties" };
  if (!geldigeWykId(wyk.wyk_id) || !geldigeMuniKode(wyk.muni_kode)) return leeg;
  const distrik = wyk.distrik_kode && geldigeMuniKode(wyk.distrik_kode) ? wyk.distrik_kode : null;

  // The district PR ballot is drawn by the district council, so its order rows are keyed by
  // the district's own code — read both councils' draw rows in one request.
  const kodes = distrik ? `in.(${wyk.muni_kode},${distrik})` : `eq.${wyk.muni_kode}`;

  const [wykRye, plaaslikRye, distrikRye, volgordeRye] = await Promise.all([
    lees<KandidaatRy>(
      `kandidate?wyk_id=eq.${wyk.wyk_id}&stembrief=eq.wyk&select=${KANDIDAAT_KOLOMME}`,
      KAS_KANDIDATE
    ),
    lees<KandidaatRy>(
      `kandidate?muni_kode=eq.${wyk.muni_kode}&stembrief=eq.pv_plaaslik&select=${KANDIDAAT_KOLOMME}`,
      KAS_KANDIDATE
    ),
    distrik
      ? lees<KandidaatRy>(
          `kandidate?muni_kode=eq.${distrik}&stembrief=eq.pv_distrik&select=${KANDIDAAT_KOLOMME}`,
          KAS_KANDIDATE
        )
      : Promise.resolve<KandidaatRy[]>([]),
    lees<VolgordeRy>(
      `stembrief_volgorde?muni_kode=${kodes}&select=muni_kode,stembrief,posisie,partye(naam)`,
      KAS_KANDIDATE
    ),
  ]);

  const trekking = volgordeRye ?? [];
  // "stembrief" only once the draw has actually landed for this council; a half-drawn
  // ballot would mix two orderings, which is worse than staying alphabetical.
  const volgorde: Volgorde = trekking.length > 0 ? "stembrief" : "alfabeties";

  const posisies = (stembrief: string, muniKode: string) =>
    new Map(
      trekking
        .filter((v) => v.stembrief === stembrief && v.muni_kode === muniKode)
        .flatMap((v) => {
          const naam = een(v.partye)?.naam;
          return naam ? ([[naam, v.posisie]] as [string, number][]) : [];
        })
    );

  return {
    wyk: sorteerKandidate((wykRye ?? []).map(naKandidaat), volgorde),
    pv_plaaslik: groepeerPerParty(
      plaaslikRye ?? [],
      posisies("pv_plaaslik", wyk.muni_kode),
      volgorde
    ),
    pv_distrik: distrik
      ? groepeerPerParty(distrikRye ?? [], posisies("pv_distrik", distrik), volgorde)
      : [],
    volgorde,
  };
}

/**
 * The distinct party names contesting a municipality. PostgREST has no DISTINCT, so prefer
 * the ballot draw (exactly one row per contesting party) and fall back to paging the
 * candidate rows before the draw. Empty until candidate lists are loaded.
 */
async function haalKontesterendePartye(kode: string): Promise<string[]> {
  const trekking = await lees<{ partye: Ingebed<{ naam: string }> }>(
    `stembrief_volgorde?muni_kode=eq.${kode}&select=partye(naam)`,
    KAS_KANDIDATE
  );
  const bron =
    trekking && trekking.length > 0
      ? trekking
      : await leesAlles<{ partye: Ingebed<{ naam: string }> }>(
          `kandidate?muni_kode=eq.${kode}&select=partye(naam)&order=id.asc`,
          KAS_KANDIDATE
        );
  const name = new Set<string>();
  for (const ry of bron) {
    const naam = een(ry.partye)?.naam;
    if (naam) name.add(naam);
  }
  return [...name].sort(vergelykNaam);
}

async function haalRaad2021(kode: string): Promise<Raad2021 | null> {
  const [uitslae, grootte] = await Promise.all([
    lees<Raad2021Rooi>(
      `raad_uitslae_2021?muni_kode=eq.${kode}&select=party_naam,setels_wyk,setels_pv,setels_totaal`,
      KAS_WYKE
    ),
    lees<{ raadsgrootte_totaal: number; onafhanklike_setels: number }>(
      `raad_grootte_2021?muni_kode=eq.${kode}&select=raadsgrootte_totaal,onafhanklike_setels&limit=1`,
      KAS_WYKE
    ),
  ]);
  const g = grootte?.[0];
  // No 2021 row for this council (a new or re-demarcated one, or the data is not loaded):
  // show nothing rather than a half-assembled council.
  if (!uitslae || uitslae.length === 0 || !g) return null;

  const rye = [...uitslae].sort((a, b) => vergelykNaam(a.party_naam, b.party_naam));
  const kern = {
    raadsgrootte: g.raadsgrootte_totaal,
    onafhanklike_setels: g.onafhanklike_setels ?? 0,
    rye,
  };
  return { ...kern, geenMeerderheid: geenMeerderheid(kern) };
}

export async function haalMuni(kode: string): Promise<MuniOpsomming | null> {
  if (!geldigeMuniKode(kode)) return null;
  const rye = await lees<{
    kode: string;
    naam: string;
    tipe: string;
    distrik_kode: string | null;
    provinsie: string;
  }>(
    `munisipaliteite?kode=eq.${kode}&select=kode,naam,tipe,distrik_kode,provinsie&limit=1`,
    KAS_WYKE
  );
  const muni = rye?.[0];
  if (!muni) return null;

  const [distrik_naam, wyke, partye, raad2021] = await Promise.all([
    muni.distrik_kode ? haalMuniNaam(muni.distrik_kode) : Promise.resolve(null),
    leesAlles<{ wyk_id: string; wyk_nr: number }>(
      `wyke?muni_kode=eq.${kode}&select=wyk_id,wyk_nr&order=wyk_nr.asc`,
      KAS_WYKE
    ),
    haalKontesterendePartye(kode),
    haalRaad2021(kode),
  ]);

  return {
    kode: muni.kode,
    naam: muni.naam,
    tipe: muni.tipe,
    provinsie: muni.provinsie,
    distrik_naam,
    wyke,
    partye,
    raad2021,
  };
}

/** Sitemap: every ward id, paged. */
export async function haalAlleWykIds(): Promise<{ wyk_id: string }[]> {
  return leesAlles<{ wyk_id: string }>("wyke?select=wyk_id&order=wyk_id.asc", KAS_WYKE);
}

/** Sitemap: every municipality code, paged. */
export async function haalAlleMuniKodes(): Promise<{ kode: string }[]> {
  return leesAlles<{ kode: string }>("munisipaliteite?select=kode&order=kode.asc", KAS_WYKE);
}
