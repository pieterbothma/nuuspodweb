import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { Kandidaat, PartyLys, Stembriewe, Stemstasie, Wyk } from "@/lib/verkiesing/wyksoeker";
import WykBladsy from "../[wykId]/page";
import { vulIn } from "@/app/_components/verkiesing/stembriewe";

/**
 * The ward page is an async server component, so it is invoked as a function and the element
 * tree it returns is handed to Testing Library. Everything below the page is synchronous.
 *
 * The data layer is stubbed per test — `geldigeWykId` stays real, because the page's 404 path
 * is the regex plus `haalWyk`, and stubbing the regex away would test nothing.
 */

const { haalWyk, haalStemstasies, haalStembriewe, geenGevind } = vi.hoisted(() => ({
  haalWyk: vi.fn(),
  haalStemstasies: vi.fn(),
  haalStembriewe: vi.fn(),
  geenGevind: vi.fn(() => {
    // The real notFound() throws; a stub that returns would let the page render on.
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/lib/verkiesing/wyksoeker", async (oorspronklik) => ({
  ...(await oorspronklik<typeof import("@/lib/verkiesing/wyksoeker")>()),
  haalWyk,
  haalStemstasies,
  haalStembriewe,
}));

// The strip's own read must never reach PostgREST from a test, env vars set or not.
vi.mock("@/lib/supabase-rest", () => ({
  lees: vi.fn(async () => null),
  voegIn: vi.fn(async () => false),
}));

vi.mock("next/navigation", () => ({
  notFound: geenGevind,
  usePathname: () => "/wyk/10204009",
}));

// next/image needs the Next build pipeline; the masthead only needs an <img> here.
vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

const STELLENBOSCH: Wyk = {
  wyk_id: "10204009",
  wyk_nr: 9,
  muni_kode: "WC024",
  muni_naam: "Stellenbosch",
  muni_tipe: "plaaslik",
  distrik_kode: "DC2",
  distrik_naam: "Cape Winelands",
  provinsie: "Wes-Kaap",
};

// The row keeps the IEC's official English name; the page shows the Afrikaans display name.
const KAAPSTAD: Wyk = {
  wyk_id: "19100055",
  wyk_nr: 55,
  muni_kode: "CPT",
  muni_naam: "City of Cape Town",
  muni_tipe: "metro",
  distrik_kode: null,
  distrik_naam: null,
  provinsie: "Wes-Kaap",
};

const LEEG: Stembriewe = { wyk: [], pv_plaaslik: [], pv_distrik: [], volgorde: "alfabeties" };

function kandidaat(oorskryf: Partial<Kandidaat> = {}): Kandidaat {
  return {
    volle_naam: "VOORBEELD, Kandidaat Een",
    van: "VOORBEELD",
    party_naam: "PARTY A",
    onafhanklik: false,
    lys_posisie: null,
    ...oorskryf,
  };
}

function partyLys(oorskryf: Partial<PartyLys> = {}): PartyLys {
  return { party_naam: "PARTY A", posisie: null, kandidate: [kandidaat()], ...oorskryf };
}

function stasie(oorskryf: Partial<Stemstasie> = {}): Stemstasie {
  return { vd_nommer: "10204009001", naam: "KAYA MANDI HIGH SCHOOL", adres: null, ...oorskryf };
}

function stel(wyk: Wyk | null, stasies: Stemstasie[] = [], briewe: Stembriewe = LEEG) {
  haalWyk.mockResolvedValue(wyk);
  haalStemstasies.mockResolvedValue(stasies);
  haalStembriewe.mockResolvedValue(briewe);
}

async function wys(wykId: string) {
  const boom = await WykBladsy({ params: Promise.resolve({ wykId }) });
  return render(boom);
}

beforeEach(() => {
  vi.clearAllMocks();
  // No SUPABASE_* env in the test run, so the source-strip read returns null without a fetch.
});

afterEach(() => cleanup());

describe("/wyk/[wykId]", () => {
  it("gee 404 vir 'n onbekende of ongeldige wyk-id", async () => {
    stel(null);
    await expect(wys("12345678")).rejects.toThrow("NEXT_NOT_FOUND");
    expect(geenGevind).toHaveBeenCalled();

    geenGevind.mockClear();
    haalWyk.mockClear();
    await expect(wys("12345")).rejects.toThrow("NEXT_NOT_FOUND");
    expect(geenGevind).toHaveBeenCalled();
    // An id that cannot be a ward never reaches the database.
    expect(haalWyk).not.toHaveBeenCalled();
  });

  it("wys 3 stembriefblokke vir 'n plaaslike munisipaliteit", async () => {
    stel(STELLENBOSCH, [stasie()]);
    const { container } = await wys("10204009");
    expect(container.querySelectorAll("[data-stembrief]")).toHaveLength(3);
    expect(screen.getByText(vulIn(KOPIE.stembrief_teller, { n: 1, m: 3 }))).toBeTruthy();
    expect(screen.getByText(vulIn(KOPIE.stembrief_teller, { n: 3, m: 3 }))).toBeTruthy();
    expect(screen.getByText(KOPIE.stembrief_wyk)).toBeTruthy();
    expect(screen.getByText(vulIn(KOPIE.stembrief_pv, { q: "Stellenbosch" }))).toBeTruthy();
    expect(
      screen.getByText(vulIn(KOPIE.stembrief_distrik, { q: "Cape Winelands" }))
    ).toBeTruthy();
  });

  it("wys 2 stembriefblokke vir 'n metro", async () => {
    stel(KAAPSTAD, [stasie()]);
    const { container } = await wys("19100055");
    expect(container.querySelectorAll("[data-stembrief]")).toHaveLength(2);
    expect(screen.getByText(vulIn(KOPIE.stembrief_teller, { n: 2, m: 2 }))).toBeTruthy();
    expect(screen.queryByText(/distriksraad/)).toBeNull();
    // The metro's English row name never reaches the reader.
    expect(screen.getByText(vulIn(KOPIE.stembrief_pv, { q: "Stad Kaapstad" }))).toBeTruthy();
    expect(screen.queryByText(/City of Cape Town/)).toBeNull();
  });

  it("wys 'n stasie sonder adres met net sy naam", async () => {
    stel(STELLENBOSCH, [
      stasie({ vd_nommer: "1", naam: "ARK OF GLORY MINISTRIES CHURCH", adres: null }),
      stasie({ vd_nommer: "2", naam: "KAYA MANDI HIGH SCHOOL", adres: "MAIN ROAD KAYA MANDI" }),
    ]);
    const { container } = await wys("10204009");
    const rye = container.querySelectorAll("#stemlokale [data-stasie]");
    expect(rye).toHaveLength(2);
    expect(rye[0].textContent).toBe("ARK OF GLORY MINISTRIES CHURCH");
    expect(rye[1].textContent).toContain("MAIN ROAD KAYA MANDI");
  });

  it("wys die kandidate-nog-nie-gelaai-boodskap wanneer daar geen kandidate is nie", async () => {
    stel(STELLENBOSCH, [stasie()], LEEG);
    await wys("10204009");
    // One per ballot block — the state is a fact about the IEC's publication, not an error.
    expect(screen.getAllByText(KOPIE.kandidate_nog_nie_gelaai)).toHaveLength(3);
  });

  it("gebruik geen partykleur- of rooi-klasse op kandidaat- of partyrye nie", async () => {
    stel(STELLENBOSCH, [stasie()], {
      wyk: [kandidaat(), kandidaat({ volle_naam: "VOORBEELD, Twee", party_naam: null, onafhanklik: true })],
      pv_plaaslik: [partyLys(), partyLys({ party_naam: "PARTY B" })],
      pv_distrik: [partyLys({ party_naam: "PARTY C" })],
      volgorde: "alfabeties",
    });
    const { container } = await wys("10204009");
    const rye = container.querySelectorAll("[data-ry]");
    expect(rye.length).toBeGreaterThan(0);
    for (const ry of rye) {
      for (const el of [ry, ...ry.querySelectorAll("*")]) {
        const klasse = el.getAttribute("class") ?? "";
        expect(klasse).not.toMatch(/rooi|siaan|neon|#[0-9a-fA-F]{3}/);
        expect(el.getAttribute("style")).toBeNull();
      }
    }
    // The independent row names no party, so it cannot be mistaken for one.
    expect(screen.getByText(KOPIE.onafhanklik)).toBeTruthy();
  });

  it("wys geen lysnommers voor die trekking nie", async () => {
    // Real list positions exist in the rows, but the ballot is still alphabetical: printing
    // them would contradict the "Alfabeties" label and put them in the wrong order.
    stel(STELLENBOSCH, [stasie()], {
      ...LEEG,
      pv_plaaslik: [
        partyLys({
          kandidate: [
            kandidaat({ volle_naam: "VOORBEELD, Abel", lys_posisie: 7 }),
            kandidaat({ volle_naam: "VOORBEELD, Zelda", lys_posisie: 3 }),
          ],
        }),
      ],
      volgorde: "alfabeties",
    });
    const { container } = await wys("10204009");
    expect(container.querySelectorAll("[data-lys-nr]")).toHaveLength(0);
    const lys = container.querySelector("[data-ry='party'] ol");
    expect(lys?.textContent).toBe("VOORBEELD, AbelVOORBEELD, Zelda");
    expect(lys?.textContent).not.toMatch(/\d/);
  });

  it("wys die werklike lysposisies ná die trekking, nooit die arrayindeks nie", async () => {
    stel(STELLENBOSCH, [stasie()], {
      ...LEEG,
      pv_plaaslik: [
        partyLys({
          posisie: 1,
          kandidate: [
            kandidaat({ volle_naam: "VOORBEELD, Een", lys_posisie: 3 }),
            kandidaat({ volle_naam: "VOORBEELD, Twee", lys_posisie: 7 }),
            // A row without a position leaves its cell empty rather than borrowing "3".
            kandidaat({ volle_naam: "VOORBEELD, Drie", lys_posisie: null }),
          ],
        }),
      ],
      volgorde: "stembrief",
    });
    const { container } = await wys("10204009");
    const nrs = [...container.querySelectorAll("[data-lys-nr]")].map((e) => e.textContent);
    expect(nrs).toEqual(["3", "7", ""]);
  });

  it("wys 'Alfabeties' sonder stembriefvolgorde en 'Volgorde soos op die stembrief' daarmee", async () => {
    stel(STELLENBOSCH, [stasie()], { ...LEEG, wyk: [kandidaat()] });
    await wys("10204009");
    expect(screen.getAllByText(KOPIE.volgorde_alfabeties)).toHaveLength(3);
    expect(screen.queryByText(KOPIE.volgorde_stembrief)).toBeNull();
    cleanup();

    stel(STELLENBOSCH, [stasie()], {
      wyk: [kandidaat({ lys_posisie: 1 })],
      pv_plaaslik: [partyLys({ posisie: 1 })],
      pv_distrik: [partyLys({ posisie: 1 })],
      volgorde: "stembrief",
    });
    await wys("10204009");
    expect(screen.getAllByText(KOPIE.volgorde_stembrief)).toHaveLength(3);
    expect(screen.queryByText(KOPIE.volgorde_alfabeties)).toBeNull();
  });
});
