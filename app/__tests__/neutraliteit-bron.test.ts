import fs from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

/**
 * Neutrality at the source level: the share card names no party, nothing in the site imports
 * the party colours (those are for results graphics in a later drop), and no ordering
 * function looks at seats, votes or list size.
 */

const WORTEL = path.resolve(__dirname, "../..");

function bronLeers(gids: string): string[] {
  const uit: string[] = [];
  for (const inskrywing of fs.readdirSync(path.join(WORTEL, gids), { withFileTypes: true })) {
    const rel = path.join(gids, inskrywing.name);
    if (inskrywing.isDirectory()) {
      if (inskrywing.name === "node_modules" || inskrywing.name.startsWith(".")) continue;
      uit.push(...bronLeers(rel));
    } else if (/\.(ts|tsx|js|mjs)$/.test(inskrywing.name)) {
      uit.push(rel);
    }
  }
  return uit;
}

const { vang, stembriewe } = vi.hoisted(() => ({
  vang: { boom: null as unknown },
  stembriewe: vi.fn(),
}));

vi.mock("next/og", () => ({
  ImageResponse: class {
    constructor(boom: unknown) {
      vang.boom = boom;
    }
  },
}));

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

vi.mock("@/lib/verkiesing/wyksoeker", async (oorspronklik) => ({
  ...(await oorspronklik<typeof import("@/lib/verkiesing/wyksoeker")>()),
  haalWyk: vi.fn(async () => ({
    wyk_id: "10204009",
    wyk_nr: 9,
    muni_kode: "WC024",
    muni_naam: "Stellenbosch",
    muni_tipe: "plaaslik",
    distrik_kode: "DC2",
    distrik_naam: "Cape Winelands",
    provinsie: "Western Cape",
  })),
  haalStembriewe: stembriewe,
}));

/** Every string and number in a React element tree (the text Satori would paint). */
function teks(knoop: unknown): string[] {
  if (knoop == null || typeof knoop === "boolean") return [];
  if (typeof knoop === "string" || typeof knoop === "number") return [String(knoop)];
  if (Array.isArray(knoop)) return knoop.flatMap(teks);
  if (typeof knoop === "object" && "props" in knoop) {
    const props = (knoop as { props: Record<string, unknown> }).props;
    return [...teks(props.children), ...(typeof props.alt === "string" ? [props.alt] : [])];
  }
  return [];
}

describe("neutraliteit in die bron", () => {
  it("die deelkaart bevat geen partynaam nie", async () => {
    stembriewe.mockResolvedValue({
      wyk: [
        { volle_naam: "A", van: "A", party_naam: "UNIEKE PARTY XYZ", onafhanklik: false, lys_posisie: 1 },
        { volle_naam: "B", van: "B", party_naam: null, onafhanklik: true, lys_posisie: 2 },
      ],
      pv_plaaslik: [{ party_naam: "ANDER PARTY QRS", posisie: 1, kandidate: [] }],
      pv_distrik: [],
      volgorde: "stembrief",
    });
    const { default: DeelKaart } = await import("@/app/wyk/[wykId]/opengraph-image");
    await DeelKaart({ params: Promise.resolve({ wykId: "10204009" }) });
    const geverf = teks(vang.boom).join(" ");
    expect(geverf).toContain("9"); // the card did render
    expect(geverf).not.toMatch(/UNIEKE PARTY XYZ|ANDER PARTY QRS/);
  });

  it("geen komponent of biblioteek voer partykleure.json in nie", () => {
    // An import, require or file read — comments that say it is never imported are fine.
    const laai = /(import[^;]*|require\(|readFileSync\()[^;\n]*partykleure/;
    const treffers = [...bronLeers("app"), ...bronLeers("lib")].filter(
      (l) => !l.includes("__tests__") && laai.test(fs.readFileSync(path.join(WORTEL, l), "utf8"))
    );
    expect(treffers).toEqual([]);
  });

  it("ordening gebruik nooit setels, stemme of lysgrootte nie", () => {
    const orden = fs.readFileSync(path.join(WORTEL, "lib/verkiesing/orden.ts"), "utf8");
    const funksies = [...orden.matchAll(/export function (sorteer\w+|vergelykNaam)[\s\S]*?\n}\n/g)];
    expect(funksies.map((f) => f[1]).sort()).toEqual(
      ["sorteerKandidate", "sorteerLysKandidate", "sorteerPartyLyste", "vergelykNaam"].sort()
    );
    for (const [liggaam, naam] of funksies) {
      // Comments may explain what is NOT used; only the code counts.
      const kode = liggaam.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
      // `lyste.length > 0` (is there anything at all) is fine; a party's list size is not.
      expect(kode, naam).not.toMatch(/setels|stemme|kandidate\.length/);
    }
  });
});
