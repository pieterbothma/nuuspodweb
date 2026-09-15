export interface StroomItem {
  id: number;
  titel: string;
  bron: string;
  bron_tipe: string;
  url: string;
  gepubliseer_om: string;
}

/** Newest-first input; no single outlet may dominate the visible rail. */
export function balanseer(items: StroomItem[], top = 15, perBron = 3): StroomItem[] {
  const tel = new Map<string, number>();
  const uit: StroomItem[] = [];
  for (const item of items) {
    const n = tel.get(item.bron) ?? 0;
    if (n >= perBron) continue;
    tel.set(item.bron, n + 1);
    uit.push(item);
    if (uit.length === top) break;
  }
  return uit;
}

const MAANDE = ["Jan", "Feb", "Mrt", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"];

function sast(d: Date) {
  const dele = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Africa/Johannesburg",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(d)
      .map((p) => [p.type, p.value])
  );
  return { datum: `${dele.year}-${dele.month}-${dele.day}`, maand: Number(dele.month), dag: Number(dele.day), tyd: `${dele.hour}:${dele.minute}` };
}

/** "14:20" for today (SAST), otherwise "12 Sep". Month names are fixed so ICU data can't change them. */
export function tydEtiket(iso: string, nou: Date): string {
  const item = sast(new Date(iso));
  return item.datum === sast(nou).datum ? item.tyd : `${item.dag} ${MAANDE[item.maand - 1]}`;
}

/** "nou" / "37 min" / "5 u", falling back to the `tydEtiket` date form after a day. */
export function relatieweTyd(iso: string, nou: Date): string {
  const minute = Math.floor((nou.getTime() - new Date(iso).getTime()) / 60_000);
  if (minute < 1) return "nou";
  if (minute < 60) return `${minute} min`;
  const uur = Math.floor(minute / 60);
  if (uur < 24) return `${uur} u`;
  return tydEtiket(iso, nou);
}

const BEKENDE_BRONNE: Record<string, string> = {
  "Daily Maverick": "DM",
  "SABC News": "SABC",
  "The Citizen": "TC",
  Politicsweb: "PW",
  Lowvelder: "LV",
  Rekord: "RK",
  "Mail & Guardian": "M&G",
  "Maroela Media": "MM",
};

/** A short monogram for a source name, e.g. for an avatar. */
export function bronAfkorting(bron: string): string {
  return BEKENDE_BRONNE[bron] ?? bron.slice(0, 2).toUpperCase();
}
