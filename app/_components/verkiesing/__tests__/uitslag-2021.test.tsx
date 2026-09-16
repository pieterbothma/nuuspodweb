import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { Uitslag2021 } from "../uitslag-2021";
import { vulIn } from "../stembriewe";

afterEach(cleanup);

const UITSLAG = {
  wyk_id_2021: "19100027",
  wyk_nr_2021: 27,
  geregistreer: 1000,
  geldige_stemme: 400,
  bedorwe_stemme: 10,
  rye: [
    { party_naam: "INDEPENDENT", stemme: 100 },
    { party_naam: "PARTY A", stemme: 300 },
  ],
};

describe("Uitslag2021", () => {
  it("wys stemme, persentasies en stemdeelname sonder kleur", () => {
    const { container } = render(<Uitslag2021 uitslag={UITSLAG} wykNr={27} muniKode="CPT" />);
    const rye = [...container.querySelectorAll("[data-uitslag-ry]")].map((r) => r.textContent);
    expect(rye[0]).toContain(KOPIE.uitslag2021_onafhanklik);
    expect(rye[0]).toContain("25,0");
    expect(rye[1]).toContain("PARTY A");
    expect(rye[1]).toContain("75,0");
    expect(container.textContent).toContain("41,0%"); // (400 + 10) / 1000
    expect(container.textContent).not.toContain(vulIn(KOPIE.uitslag2021_hernommer, { n: 27 }));
    for (const el of container.querySelectorAll("[data-uitslag-ry], [data-uitslag-ry] *")) {
      expect(el.getAttribute("class") ?? "").not.toMatch(/rooi|siaan|neon|\[#/);
      expect(el.getAttribute("style")).toBeNull();
    }
  });

  it("vou partye onder 1% weg, steeds alfabeties en een klik ver", () => {
    const { container } = render(
      <Uitslag2021
        uitslag={{ ...UITSLAG, geldige_stemme: 1000, rye: [{ party_naam: "A KLEIN", stemme: 5 }, { party_naam: "B GROOT", stemme: 995 }] }}
        wykNr={27}
        muniKode="CPT"
      />
    );
    const klein = container.querySelector("[data-klein-partye]")!;
    expect(klein.textContent).toContain("A KLEIN");
    expect(klein.textContent).toContain(vulIn(KOPIE.uitslag2021_wys_klein, { n: 1 }));
    const sigbaar = [...container.querySelectorAll("[data-uitslag-ry]")].filter((r) => !klein.contains(r));
    expect(sigbaar.map((r) => r.textContent)).toEqual([expect.stringContaining("B GROOT")]);
  });

  it("noem die ou wyknommer as die wyk hernommer is", () => {
    render(<Uitslag2021 uitslag={UITSLAG} wykNr={31} muniKode="CPT" />);
    expect(screen.getByText(new RegExp(vulIn(KOPIE.uitslag2021_hernommer, { n: 27 }).replace(/[.]/g, "\\.")))).toBeTruthy();
  });

  it("verwys 'n veranderde wyk na die raad se 2021-uitslag", () => {
    render(<Uitslag2021 uitslag="verander" wykNr={5} muniKode="WC024" />);
    expect(screen.getByText(KOPIE.uitslag2021_verander_skakel).closest("a")?.getAttribute("href")).toBe("/munisipaliteit/WC024");
  });

  it("wys niks by 'n databasisonderbreking nie", () => {
    const { container } = render(<Uitslag2021 uitslag={null} wykNr={5} muniKode="WC024" />);
    expect(container.innerHTML).toBe("");
  });
});
