export type Blok =
  | { tipe: "p"; teks: string }
  | { tipe: "h2"; teks: string }
  | { tipe: "ul"; items: string[] };

/** Generated from docs/verkiesing/konsepte/<slug>.md; `lyf` is the approved Markdown body verbatim. */
export interface GidsBron {
  slug: string;
  titel: string;
  lyf: string;
  bronne: string[];
  nagegaan: string;
  gepubliseer: boolean;
}

export interface Gids extends GidsBron {
  blokke: Blok[];
  opsomming: string;
}

export function vetDele(teks: string): { teks: string; vet: boolean }[] {
  const dele: { teks: string; vet: boolean }[] = [];
  let laaste = 0;
  for (const m of teks.matchAll(/\*\*(.+?)\*\*/g)) {
    const begin = m.index ?? 0;
    if (begin > laaste) dele.push({ teks: teks.slice(laaste, begin), vet: false });
    dele.push({ teks: m[1], vet: true });
    laaste = begin + m[0].length;
  }
  if (laaste < teks.length) dele.push({ teks: teks.slice(laaste), vet: false });
  return dele;
}

/** The explainers use only paragraphs, `## ` headings and `* ` bullets; nothing else is supported. */
export function mdNaBlokke(md: string): Blok[] {
  const blokke: Blok[] = [];
  let para: string[] = [];
  let lys: string[] | null = null;
  const spoelPara = () => {
    if (para.length) blokke.push({ tipe: "p", teks: para.join(" ") });
    para = [];
  };
  const spoelLys = () => {
    if (lys) blokke.push({ tipe: "ul", items: lys });
    lys = null;
  };
  for (const rou of md.split("\n")) {
    const reël = rou.trim();
    if (reël === "") {
      spoelPara();
      spoelLys();
      continue;
    }
    if (reël.startsWith("## ")) {
      spoelPara();
      spoelLys();
      blokke.push({ tipe: "h2", teks: reël.slice(3).trim() });
      continue;
    }
    const item = reël.match(/^[*-]\s+(.*)$/);
    if (item) {
      spoelPara();
      (lys ??= []).push(item[1]);
      continue;
    }
    spoelLys();
    para.push(reël);
  }
  spoelPara();
  spoelLys();
  return blokke;
}
