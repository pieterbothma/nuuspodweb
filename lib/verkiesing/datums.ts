import { KOPIE } from "./kopie";

/** Voting opens at 07:00 SAST on Wednesday 4 November 2026 (gazetted timetable). */
export const STEMDAG = new Date("2026-11-04T07:00:00+02:00");

/**
 * KOPIE's mylpaal_* strings carry a leading "<datum>: " prefix (the site already shows the
 * date in its own column — see docs/verkiesing/ui-kopie-wysigings.md). Strip everything up to
 * and including the first ": " and capitalise the remainder's first letter if needed. The
 * words after that point stay byte-identical to the KOPIE value.
 */
function sonderDatumVoorvoegsel(s: string): string {
  const i = s.indexOf(": ");
  const rest = i === -1 ? s : s.slice(i + 2);
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

export interface Mylpaal {
  id: string;
  /** Afrikaans date label as shown on the page. */
  wanneer: string;
  /** Afrikaans description as shown on the page. */
  wat: string;
  /** ISO instant after which the milestone is no longer upcoming. */
  einde: string;
}

// Dates verified against the IEC's gazetted LGE 2026 timetable (spec §4). Neutral facts only.
export const MYLPALE: Mylpaal[] = [
  {
    id: "kandidaatlyste",
    wanneer: "Woensdag 16 September",
    wat: sonderDatumVoorvoegsel(KOPIE.mylpaal_kandidaatlyste),
    einde: "2026-09-16T23:59:59+02:00",
  },
  {
    id: "spesiale-aansoeke",
    wanneer: "21 September tot 12 Oktober, 17:00",
    wat: sonderDatumVoorvoegsel(KOPIE.mylpaal_spesiaal_aansoek),
    einde: "2026-10-12T17:00:00+02:00",
  },
  {
    id: "trekking",
    wanneer: "Woensdag 23 September",
    wat: sonderDatumVoorvoegsel(KOPIE.mylpaal_trekking),
    einde: "2026-09-23T23:59:59+02:00",
  },
  {
    id: "spesiale-stemme",
    wanneer: "Maandag 2 en Dinsdag 3 November",
    wat: sonderDatumVoorvoegsel(KOPIE.mylpaal_spesiale_stemme),
    einde: "2026-11-03T17:00:00+02:00",
  },
  {
    id: "stemdag",
    wanneer: "Woensdag 4 November",
    wat: sonderDatumVoorvoegsel(KOPIE.mylpaal_stemdag),
    einde: "2026-11-04T21:00:00+02:00",
  },
];

export function komendeMylpale(nou: Date, aantal = 3): Mylpaal[] {
  return MYLPALE.filter((m) => new Date(m.einde).getTime() > nou.getTime()).slice(0, aantal);
}

const SPESIALE_STEM_OOP = new Date("2026-09-21T00:00:00+02:00");
const SPESIALE_STEM_TOE = new Date("2026-10-12T17:00:00+02:00");

export type SpesialeStemStatus = "toe" | "oop" | "verby";

/** Application window for a special vote: closed until 21 Sep, open until 17:00 on 12 Oct, then closed for good. */
export function spesialeStemStatus(nou: Date): SpesialeStemStatus {
  const t = nou.getTime();
  if (t < SPESIALE_STEM_OOP.getTime()) return "toe";
  if (t < SPESIALE_STEM_TOE.getTime()) return "oop";
  return "verby";
}

export function aftelling(nou: Date, teiken: Date = STEMDAG) {
  const ms = teiken.getTime() - nou.getTime();
  if (ms <= 0) return { dae: 0, ure: 0, minute: 0, verby: true };
  const totaal = Math.floor(ms / 60_000);
  return {
    dae: Math.floor(totaal / 1440),
    ure: Math.floor((totaal % 1440) / 60),
    minute: totaal % 60,
    verby: false,
  };
}
