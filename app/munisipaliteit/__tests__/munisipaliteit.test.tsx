import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { MuniOpsomming, Raad2021, Raad2021Rooi } from "@/lib/verkiesing/wyksoeker";
import { vulIn } from "@/app/_components/verkiesing/stembriewe";
import MuniBladsy from "../[kode]/page";

/**
 * The municipality page is an async server component, so it is invoked as a function and the
 * tree it returns handed to Testing Library. `geldigeMuniKode` stays real — the 404 path is
 * the regex plus `haalMuni`, and stubbing the regex away would test nothing.
 */

const { haalMuni, geenGevind } = vi.hoisted(() => ({
  haalMuni: vi.fn(),
  geenGevind: vi.fn(() => {
    // The real notFound() throws; a stub that returns would let the page render on.
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/lib/verkiesing/wyksoeker", async (oorspronklik) => ({
  ...(await oorspronklik<typeof import("@/lib/verkiesing/wyksoeker")>()),
  haalMuni,
}));

vi.mock("next/navigation", () => ({
  notFound: geenGevind,
  usePathname: () => "/munisipaliteit/WC024",
}));

vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

function ry(party_naam: string, setels_wyk: number, setels_pv: number): Raad2021Rooi {
  return { party_naam, setels_wyk, setels_pv, setels_totaal: setels_wyk + setels_pv };
}

/** Stellenbosch's real 2021 shape, cut down: 45 seats, DA 28, no independents. */
const STELLENBOSCH_RAAD: Raad2021 = {
  raadsgrootte: 45,
  onafhanklike_setels: 0,
  // Deliberately handed to the component in seat order, biggest first: the table must not
  // keep this order.
  rye: [
    ry("DEMOCRATIC ALLIANCE", 19, 9),
    ry("AFRICAN NATIONAL CONGRESS", 4, 4),
    ry("ECONOMIC FREEDOM FIGHTERS", 0, 2),
    ry("AFRICAN CHRISTIAN DEMOCRATIC PARTY", 0, 1),
  ],
  geenMeerderheid: false,
};

function wyke(aantal: number) {
  return Array.from({ length: aantal }, (_, i) => ({
    wyk_id: `102040${String(i + 1).padStart(2, "0")}`,
    wyk_nr: i + 1,
  }));
}

function muni(oorskryf: Partial<MuniOpsomming> = {}): MuniOpsomming {
  return {
    kode: "WC024",
    naam: "Stellenbosch",
    tipe: "plaaslik",
    provinsie: "Western Cape",
    distrik_naam: "Cape Winelands",
    wyke: wyke(23),
    partye: [],
    raad2021: STELLENBOSCH_RAAD,
    ...oorskryf,
  };
}

async function wys(kode: string) {
  const boom = await MuniBladsy({ params: Promise.resolve({ kode }) });
  return render(boom);
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => cleanup());

describe("/munisipaliteit/[kode]", () => {
  it("gee 404 vir 'n onbekende kode", async () => {
    haalMuni.mockResolvedValue(null);
    await expect(wys("ZZ999")).rejects.toThrow("NEXT_NOT_FOUND");
    expect(geenGevind).toHaveBeenCalled();

    geenGevind.mockClear();
    haalMuni.mockClear();
    // A code that cannot be a municipality never reaches the database.
    await expect(wys("nonsens-123")).rejects.toThrow("NEXT_NOT_FOUND");
    expect(geenGevind).toHaveBeenCalled();
    expect(haalMuni).not.toHaveBeenCalled();
  });

  it("wys elke wyk as 'n skakel", async () => {
    haalMuni.mockResolvedValue(muni());
    const { container } = await wys("WC024");
    const skakels = container.querySelectorAll("[data-wyk-rooster] a");
    expect(skakels).toHaveLength(23);
    expect(skakels[0].getAttribute("href")).toBe("/wyk/10204001");
    expect(skakels[0].textContent).toBe(vulIn(KOPIE.soek_wyk_nommer, { n: 1 }));
    expect(skakels[22].getAttribute("href")).toBe("/wyk/10204023");
    expect(skakels[22].textContent).toBe(vulIn(KOPIE.soek_wyk_nommer, { n: 23 }));
  });

  it("sorteer die 2021-tabel op partynaam, nie op setels nie", async () => {
    haalMuni.mockResolvedValue(muni());
    const { container } = await wys("WC024");
    const name = [...container.querySelectorAll("[data-raad-ry] [data-party-naam]")].map(
      (el) => el.textContent
    );
    expect(name).toEqual([
      "AFRICAN CHRISTIAN DEMOCRATIC PARTY",
      "AFRICAN NATIONAL CONGRESS",
      "DEMOCRATIC ALLIANCE",
      "ECONOMIC FREEDOM FIGHTERS",
    ]);
    // The seat leader is not first — which is exactly what "never by seats" means.
    expect(name[0]).not.toBe("DEMOCRATIC ALLIANCE");
    expect(screen.getByText(KOPIE.muni_2021_sortering)).toBeTruthy();
  });

  it("versteek partye sonder setels totdat jy hulle wys", async () => {
    haalMuni.mockResolvedValue(
      muni({
        raad2021: {
          ...STELLENBOSCH_RAAD,
          rye: [
            ...STELLENBOSCH_RAAD.rye,
            ry("PARTY SONDER SETELS A", 0, 0),
            ry("PARTY SONDER SETELS B", 0, 0),
          ],
        },
      })
    );
    const { container } = await wys("WC024");

    // The table itself carries only the parties that hold seats.
    const sigbaar = [...container.querySelectorAll("[data-raad-ry] [data-party-naam]")].map(
      (el) => el.textContent
    );
    expect(sigbaar).toHaveLength(4);
    expect(sigbaar).not.toContain("PARTY SONDER SETELS A");

    // The rest sit behind a disclosure that names how many there are.
    const toggle = container.querySelector("[data-sonder-setels]");
    expect(toggle).toBeTruthy();
    expect(toggle?.textContent).toContain(vulIn(KOPIE.muni_2021_wys_sonder_setels, { n: 2 }));
    const versteek = [...toggle!.querySelectorAll("[data-party-naam]")].map(
      (el) => el.textContent
    );
    expect(versteek).toEqual(["PARTY SONDER SETELS A", "PARTY SONDER SETELS B"]);
    // A closed <details> is closed by default, so nothing is on screen until it is opened.
    expect((toggle as HTMLDetailsElement).open).toBe(false);
  });

  it("wys die geen-meerderheid-reël net wanneer dit waar is", async () => {
    haalMuni.mockResolvedValue(muni());
    await wys("WC024");
    expect(screen.queryByText(KOPIE.muni_2021_geen_meerderheid)).toBeNull();
    cleanup();

    haalMuni.mockResolvedValue(
      muni({
        kode: "EC109",
        naam: "Kou-Kamma",
        provinsie: "Eastern Cape",
        distrik_naam: "Sarah Baartman",
        wyke: wyke(6),
        raad2021: {
          raadsgrootte: 12,
          onafhanklike_setels: 1,
          rye: [ry("PARTY A", 3, 3), ry("PARTY B", 2, 3)],
          geenMeerderheid: true,
        },
      })
    );
    await wys("EC109");
    expect(screen.getByText(KOPIE.muni_2021_geen_meerderheid)).toBeTruthy();
    // The independents row appears exactly when the council seated independents.
    expect(screen.getByText(KOPIE.muni_2021_onafhanklikes)).toBeTruthy();
  });

  it("wys geen distriksafdeling vir 'n metro nie", async () => {
    haalMuni.mockResolvedValue(
      muni({
        kode: "TSH",
        naam: "City of Tshwane",
        tipe: "metro",
        provinsie: "Gauteng",
        distrik_naam: null,
        wyke: wyke(107),
        raad2021: null,
      })
    );
    const { container } = await wys("TSH");

    expect(container.querySelector("[data-distrik]")).toBeNull();
    expect(screen.getByText(KOPIE.muni_tipe_metro)).toBeTruthy();
    expect(screen.queryByText(KOPIE.muni_tipe_plaaslik)).toBeNull();
    // A metro's name is shown in Afrikaans, in the heading and in the breadcrumb.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Stad Tshwane");
    expect(screen.getAllByText("Stad Tshwane")).toHaveLength(2);
    expect(screen.queryByText("City of Tshwane")).toBeNull();
    expect(container.querySelector("[data-onderskrif]")?.textContent).toContain("Gauteng");
    expect(container.querySelector("[data-onderskrif]")?.textContent).not.toContain("distrik");
  });

  it("wys 'n distriksraad sonder wyke en sonder 2021-tabel verstaanbaar", async () => {
    haalMuni.mockResolvedValue(
      muni({
        kode: "DC2",
        naam: "Cape Winelands",
        tipe: "distrik",
        provinsie: "Western Cape",
        distrik_naam: null,
        wyke: [],
        raad2021: null,
      })
    );
    const { container } = await wys("DC2");
    expect(screen.getByText(KOPIE.muni_tipe_distrik)).toBeTruthy();
    expect(screen.getByText(KOPIE.muni_geen_wyke)).toBeTruthy();
    expect(container.querySelectorAll("[data-wyk-rooster] a")).toHaveLength(0);
    // No 2021 council row exists, so no heading promises a table that is not there.
    expect(screen.queryByText(KOPIE.muni_2021_opskrif)).toBeNull();
    expect(container.querySelector("[data-onderskrif]")?.textContent).toBe("Wes-Kaap");
  });

  it("wys die partye-nog-nie-gelaai-boodskap totdat kandidate gelaai is", async () => {
    haalMuni.mockResolvedValue(muni({ partye: [] }));
    await wys("WC024");
    expect(screen.getByText(KOPIE.muni_partye_nog_nie_gelaai)).toBeTruthy();
    cleanup();

    haalMuni.mockResolvedValue(muni({ partye: ["PARTY A", "PARTY B"] }));
    const { container } = await wys("WC024");
    expect(screen.queryByText(KOPIE.muni_partye_nog_nie_gelaai)).toBeNull();
    expect([...container.querySelectorAll("[data-kontesterende-party]")].map((e) => e.textContent))
      .toEqual(["PARTY A", "PARTY B"]);
  });

  it("gebruik geen partykleure op die raadstabel of die partylys nie", async () => {
    haalMuni.mockResolvedValue(muni({ partye: ["PARTY A"] }));
    const { container } = await wys("WC024");
    const rye = container.querySelectorAll("[data-raad-ry], [data-kontesterende-party]");
    expect(rye.length).toBeGreaterThan(0);
    for (const r of rye) {
      for (const el of [r, ...r.querySelectorAll("*")]) {
        expect(el.getAttribute("class") ?? "").not.toMatch(/rooi|siaan|neon|#[0-9a-fA-F]{3}/);
        expect(el.getAttribute("style")).toBeNull();
      }
    }
  });
});
