import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { ordenVerklarings, partyLogo, type Partyverklaring } from "@/lib/verkiesing/partye";
import { Partyverklarings } from "../partyverklarings";

afterEach(cleanup);
const nou = new Date("2026-09-17T10:00:00Z");

function v(party: string, gepubliseer_om = "2026-09-16T12:00:00Z", oorskryf: Partial<Partyverklaring> = {}): Partyverklaring {
  return {
    id: Math.abs([...party].reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 7)),
    party,
    bron_url: `https://x/${encodeURIComponent(party)}/${gepubliseer_om}`,
    titel_oorspronklik: `${party} ORIGINAL HEADLINE`,
    titel_af: `${party} se opskrif`,
    teks_af: "Eerste paragraaf.\n\nTweede paragraaf.",
    vertaal: true,
    gepubliseer_om,
    ...oorskryf,
  };
}

describe("ordenVerklarings", () => {
  it("keeps one statement per party, the latest, in alphabetical party order — never newest first", () => {
    const uit = ordenVerklarings([
      v("Vryheidsfront Plus (VF Plus)", "2026-09-17T09:00:00Z"),
      v("ActionSA", "2026-09-10T09:00:00Z"),
      v("African National Congress (ANC)", "2026-09-16T09:00:00Z"),
      v("ActionSA", "2026-09-12T09:00:00Z"),
      v("Al Jama-ah", "2026-09-01T09:00:00Z"),
    ]);
    expect(uit.map((x) => x.party)).toEqual(["ActionSA", "African National Congress (ANC)", "Al Jama-ah", "Vryheidsfront Plus (VF Plus)"]);
    expect(uit[0].gepubliseer_om).toBe("2026-09-12T09:00:00Z");
  });
});

describe("Partyverklarings", () => {
  it("renders nothing until a statement is approved", () => {
    const { container } = render(<Partyverklarings verklarings={[]} nou={nou} />);
    expect(container.innerHTML).toBe("");
  });

  it("links each whole card to the statement's own page, with the party's logo", () => {
    const { container } = render(
      <Partyverklarings verklarings={[v("ActionSA"), v("Onbekende Party")]} nou={nou} />
    );
    const kaarte = container.querySelectorAll("[data-partyverklaring]");
    expect(kaarte).toHaveLength(2);
    const [asa, onbekend] = [...kaarte];
    const skakel = asa.querySelector("a")!;
    expect(skakel.getAttribute("href")).toBe(`/verklaring/${v("ActionSA").id}`);
    expect(skakel.textContent).toContain("ActionSA se opskrif");
    expect(skakel.textContent).toContain(KOPIE.partye_lees);
    expect(asa.querySelector("img")?.getAttribute("src")).toBe("/partye/actionsa.png");
    // No known logo: no image and no stand-in, but the same slot keeps the card aligned.
    expect(onbekend.querySelector("img")).toBeNull();
    expect(container.querySelector("details")).toBeNull();
  });

  it("has a logo for every party the admin app reads", () => {
    for (const party of [
      "ActionSA", "African Christian Democratic Party (ACDP)", "African National Congress (ANC)", "Al Jama-ah",
      "Build One South Africa (BOSA)", "Democratic Alliance (DA)", "Economic Freedom Fighters (EFF)", "GOOD",
      "Inkatha Freedom Party (IFP)", "uMkhonto weSizwe Party (MK)", "Vryheidsfront Plus (VF Plus)",
    ]) {
      const pad = partyLogo(party);
      expect(pad, party).not.toBeNull();
      expect(existsSync(join(process.cwd(), "public", pad!)), party).toBe(true);
    }
  });

  it("gives no card a colour token, arbitrary colour or inline style", () => {
    const { container } = render(<Partyverklarings verklarings={[v("ActionSA"), v("GOOD")]} nou={nou} />);
    for (const kaart of container.querySelectorAll("[data-partyverklaring]")) {
      for (const el of [kaart, ...kaart.querySelectorAll("*")]) {
        expect(el.getAttribute("class") ?? "").not.toMatch(/rooi|siaan|neon|\[#|#[0-9a-fA-F]{3}/);
        expect(el.getAttribute("style")).toBeNull();
      }
    }
  });
});
