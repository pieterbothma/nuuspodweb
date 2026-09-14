/** Voting opens at 07:00 SAST on Wednesday 4 November 2026 (gazetted timetable). */
export const STEMDAG = new Date("2026-11-04T07:00:00+02:00");

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
    wat: "Die finale kandidaatlyste word gepubliseer.",
    einde: "2026-09-16T23:59:59+02:00",
  },
  {
    id: "spesiale-aansoeke",
    wanneer: "21 September tot 12 Oktober, 17:00",
    wat: "Doen aansoek om 'n spesiale stem as jy nie op stemdag by jou stemlokaal kan stem nie.",
    einde: "2026-10-12T17:00:00+02:00",
  },
  {
    id: "trekking",
    wanneer: "Woensdag 23 September",
    wat: "Die trekking bepaal die volgorde van partye op die stembriewe.",
    einde: "2026-09-23T23:59:59+02:00",
  },
  {
    id: "spesiale-stemme",
    wanneer: "Maandag 2 en Dinsdag 3 November",
    wat: "Spesiale stemme, 08:00 tot 17:00.",
    einde: "2026-11-03T17:00:00+02:00",
  },
  {
    id: "stemdag",
    wanneer: "Woensdag 4 November",
    wat: "Stemdag. Stemlokale is oop van 07:00 tot 21:00.",
    einde: "2026-11-04T21:00:00+02:00",
  },
];

export function komendeMylpale(nou: Date, aantal = 3): Mylpaal[] {
  return MYLPALE.filter((m) => new Date(m.einde).getTime() > nou.getTime()).slice(0, aantal);
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
