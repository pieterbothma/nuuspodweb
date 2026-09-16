import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { MuniNuus, WykNuus } from "../plaaslike-nuus";
import { vulIn } from "../stembriewe";

afterEach(cleanup);
const nou = new Date("2026-09-16T10:00:00Z");
const storie = (titel: string, plek: string | null, url = `https://x/${titel}`) => ({
  titel, plek: plek as string, bron: "Rekord", url, gepubliseer_om: "2026-09-16T08:00:00Z",
});

describe("WykNuus", () => {
  it("renders nothing when there is no news — no empty heading, no promise", () => {
    const { container } = render(<WykNuus groepe={[]} muniNaam="Tshwane" nou={nou} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows each level under its own heading with verbatim, outbound headlines", () => {
    render(
      <WykNuus
        muniNaam="Tshwane"
        nou={nou}
        groepe={[
          { vlak: "wyk", plek: "Pretoria North", stories: [{ vlak: "wyk", ...storie("Work starts on Pretoria North stormwater repair", "Pretoria North") }] },
          { vlak: "dorp", plek: "Soshanguve", stories: [{ vlak: "dorp", ...storie("Soshanguve library reopens", "Soshanguve") }] },
          { vlak: "munisipaliteit", plek: null, stories: [{ vlak: "munisipaliteit", ...storie("Tshwane water outage", "Tshwane") }] },
        ]}
      />
    );
    expect(screen.getByText(KOPIE.plaaslik_omgewing)).toBeTruthy();
    expect(screen.getByText(vulIn(KOPIE.plaaslik_dorp, { q: "Soshanguve" }))).toBeTruthy();
    expect(screen.getByText(vulIn(KOPIE.plaaslik_munisipaliteit, { q: "Tshwane" }))).toBeTruthy();
    const skakel = screen.getByText("Work starts on Pretoria North stormwater repair").closest("a")!;
    expect(skakel.getAttribute("href")).toBe("https://x/Work starts on Pretoria North stormwater repair");
    expect(skakel.getAttribute("target")).toBe("_blank");
  });
});

describe("MuniNuus", () => {
  it("labels town stories with their place and leaves municipality-wide stories unlabelled", () => {
    const { container } = render(
      <MuniNuus muniNaam="Mogale City" nou={nou} stories={[storie("Krugersdorp museum opens", "Krugersdorp"), storie("Mogale water warning", null)]} />
    );
    expect(screen.getByText(vulIn(KOPIE.plaaslik_muni_opskrif, { q: "Mogale City" }))).toBeTruthy();
    const rye = [...container.querySelectorAll("[data-plaaslike-storie]")].map((r) => r.textContent ?? "");
    expect(rye[0]).toContain("Krugersdorp");
    expect(rye[1]).not.toMatch(/·\s*Mogale/);
  });

  it("uses no colour tokens or inline styles on story rows", () => {
    const { container } = render(<MuniNuus muniNaam="Mogale City" nou={nou} stories={[storie("A", "Krugersdorp")]} />);
    for (const el of container.querySelectorAll("[data-plaaslike-storie], [data-plaaslike-storie] *")) {
      expect(el.getAttribute("style")).toBeNull();
      expect(el.getAttribute("class") ?? "").not.toMatch(/siaan|neon|\[#/);
    }
  });
});
