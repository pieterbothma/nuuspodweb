import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { MuniOpsomming, Raad2021, Raad2021Rooi } from "@/lib/verkiesing/wyksoeker";
import { vulIn } from "@/app/_components/verkiesing/stembriewe";
import MuniBladsy, { generateMetadata } from "../[kode]/page";

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
    distrik_kode: "DC2",
    distrik_naam: "Cape Winelands",
    wyke: wyke(23),
    partye: [],
    volgorde: "alfabeties",
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
    // A district's own page shows its Afrikaans name where one exists.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Kaapse Wynland");
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

  it("wys partye alfabeties voor die trekking, selfs as die invoer nie gesorteer is nie", async () => {
    haalMuni.mockResolvedValue(muni({ partye: ["ZZZ", "AAA"], volgorde: "alfabeties" }));
    const { container } = await wys("WC024");
    expect([...container.querySelectorAll("[data-kontesterende-party]")].map((e) => e.textContent))
      .toEqual(["AAA", "ZZZ"]);
    expect(screen.getByText(KOPIE.volgorde_alfabeties)).toBeTruthy();
  });

  it("wys partye in stembriefvolgorde ná die trekking, met die ooreenstemmende etiket", async () => {
    haalMuni.mockResolvedValue(muni({ partye: ["ZZZ", "AAA"], volgorde: "stembrief" }));
    const { container } = await wys("WC024");
    expect([...container.querySelectorAll("[data-kontesterende-party]")].map((e) => e.textContent))
      .toEqual(["ZZZ", "AAA"]);
    expect(screen.getByText(KOPIE.volgorde_stembrief)).toBeTruthy();
    expect(screen.queryByText(KOPIE.volgorde_alfabeties)).toBeNull();
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
  it("gee die distriksnaam in Afrikaans in die onderskrif", async () => {
    haalMuni.mockResolvedValue(muni());
    const { container } = await wys("WC024");
    expect(container.querySelector("[data-distrik]")?.textContent).toBe(
      vulIn(KOPIE.muni_onderskrif_distrik, { q: "Kaapse Wynland" })
    );
    expect(screen.queryByText(/Cape Winelands/)).toBeNull();
    cleanup();

    // A district whose name is a proper name keeps it.
    haalMuni.mockResolvedValue(muni({ kode: "EC109", distrik_kode: "DC10", distrik_naam: "Sarah Baartman" }));
    const tweede = await wys("EC109");
    expect(tweede.container.querySelector("[data-distrik]")?.textContent).toBe(
      vulIn(KOPIE.muni_onderskrif_distrik, { q: "Sarah Baartman" })
    );
  });

  it("gee die ontvoude tabel dieselfde kolomme en opskrifte as die hooftabel", async () => {
    haalMuni.mockResolvedValue(
      muni({
        raad2021: {
          ...STELLENBOSCH_RAAD,
          rye: [...STELLENBOSCH_RAAD.rye, ry("'N BAIE LANG PARTYNAAM SONDER ENIGE SETELS", 0, 0)],
        },
      })
    );
    const { container } = await wys("WC024");
    const tabelle = container.querySelectorAll("table");
    expect(tabelle).toHaveLength(2);
    const [hoof, ontvou] = [...tabelle];
    // Fixed layout with identical column definitions is what makes the columns line up:
    // auto layout sizes each table's party column from its own content.
    for (const t of [hoof, ontvou]) expect(t.className).toContain("table-fixed");
    const kolomme = (t: Element) =>
      [...t.querySelectorAll("colgroup col")].map((c) => c.getAttribute("class") ?? "");
    expect(kolomme(ontvou)).toEqual(kolomme(hoof));
    expect(kolomme(hoof)).toHaveLength(4);
    // An opened disclosure labels its number columns rather than showing bare digits.
    const opskrifte = (t: Element) => [...t.querySelectorAll("thead th")].map((c) => c.textContent);
    expect(opskrifte(ontvou)).toEqual([
      KOPIE.muni_2021_kolom_party,
      KOPIE.muni_2021_kolom_wyk,
      KOPIE.muni_2021_kolom_pv,
      KOPIE.muni_2021_kolom_totaal,
    ]);
    expect(opskrifte(ontvou)).toEqual(opskrifte(hoof));
  });

  it("gee elke party se syfers hul eie etiket vir die gestapelde foonuitleg", async () => {
    haalMuni.mockResolvedValue(muni());
    const { container } = await wys("WC024");
    for (const r of container.querySelectorAll("[data-raad-ry]")) {
      const selle = r.querySelectorAll("td");
      expect(selle).toHaveLength(4);
      // The three figures each carry their column's label as real text in the cell.
      expect(selle[1].textContent).toContain(KOPIE.muni_2021_kolom_wyk);
      expect(selle[2].textContent).toContain(KOPIE.muni_2021_kolom_pv);
      expect(selle[3].textContent).toContain(KOPIE.muni_2021_kolom_totaal);
    }
  });

  it("hou vier selle in die onafhanklike-ry en sê 'geen data' vir die strepies", async () => {
    haalMuni.mockResolvedValue(
      muni({ raad2021: { ...STELLENBOSCH_RAAD, onafhanklike_setels: 2 } })
    );
    const { container } = await wys("WC024");
    const ry = [...container.querySelectorAll("[data-raad-ry]")].find((r) =>
      r.textContent?.includes(KOPIE.muni_2021_onafhanklikes)
    )!;
    expect(ry).toBeTruthy();
    // One row header plus three data cells — none of them hidden from assistive technology.
    expect(ry.querySelectorAll("th, td")).toHaveLength(4);
    for (const sel of ry.querySelectorAll("th, td")) expect(sel.getAttribute("aria-hidden")).toBeNull();
    expect(ry.querySelectorAll(".sr-only")).toHaveLength(2);
    expect([...ry.querySelectorAll(".sr-only")].map((e) => e.textContent)).toEqual([
      KOPIE.muni_2021_geen_data,
      KOPIE.muni_2021_geen_data,
    ]);
    // The row header is a <th>, so the data cells are ward, PR, total.
    const [wyk, pv, totaal] = [...ry.querySelectorAll("td")];
    expect(wyk.textContent).toContain("—");
    expect(pv.textContent).toContain("—");
    expect(totaal.textContent).not.toContain("—");
    expect(totaal.textContent).toContain("2");
  });

  it("vra die terugvoervraag net een keer en dra die 2021-nota in die bronstrook", async () => {
    haalMuni.mockResolvedValue(muni());
    const { container } = await wys("WC024");
    expect(screen.getAllByText(KOPIE.terugvoer_vraag)).toHaveLength(1);
    expect(container.querySelector("footer")).toBeTruthy();
    expect(screen.getByText(KOPIE.bron_nota_setels_2021)).toBeTruthy();
    expect(screen.getByRole("navigation", { name: KOPIE.kruimelspoor_etiket })).toBeTruthy();
  });

  it("gee die 404 se eie titel vir 'n onbekende of ongeldige kode", async () => {
    haalMuni.mockResolvedValue(null);
    for (const kode of ["ZZ999", "nonsens-123"]) {
      const meta = await generateMetadata({ params: Promise.resolve({ kode }) });
      expect(meta.title).toBe(KOPIE.nie_gevind_titel);
      expect(meta.robots).toEqual({ index: false, follow: true });
    }
    haalMuni.mockResolvedValue(muni({ kode: "DC2", naam: "Cape Winelands", tipe: "distrik" }));
    const meta = await generateMetadata({ params: Promise.resolve({ kode: "DC2" }) });
    expect(meta.title).toBe(vulIn(KOPIE.muni_bladtitel, { q: "Kaapse Wynland" }));
  });

  it("vou 'n lang partylys heeltemal toe, maar nie 'n kort een nie", async () => {
    const lank = ["F", "E", "D", "C", "B", "A"].map((l) => `PARTY ${l}`);
    haalMuni.mockResolvedValue(muni({ partye: lank }));
    const { container } = await wys("WC024");
    const partye = container.querySelector("details[data-uitvou='partye']") as HTMLDetailsElement;
    expect(partye.open).toBe(false);
    expect(partye.querySelector("summary")?.textContent).toContain(vulIn(KOPIE.uitvou_wys_partye, { n: 6 }));
    expect(partye.querySelectorAll("[data-kontesterende-party]")).toHaveLength(6);
    cleanup();

    haalMuni.mockResolvedValue(muni({ partye: ["PARTY A", "PARTY B"] }));
    const kort = await wys("WC024");
    expect(kort.container.querySelector("[data-uitvou='partye']")).toBeNull();
  });
});
