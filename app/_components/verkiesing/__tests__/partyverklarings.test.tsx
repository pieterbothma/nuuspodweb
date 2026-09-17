import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { ordenVerklarings, type Partyverklaring } from "@/lib/verkiesing/partye";
import { Partyverklarings } from "../partyverklarings";

afterEach(cleanup);
const nou = new Date("2026-09-17T10:00:00Z");

function v(party: string, gepubliseer_om = "2026-09-16T12:00:00Z", oorskryf: Partial<Partyverklaring> = {}): Partyverklaring {
  return {
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

  it("shows every party's headline with the full text folded, labelled and linked to the original", () => {
    const { container } = render(
      <Partyverklarings verklarings={[v("ActionSA"), v("Vryheidsfront Plus (VF Plus)", undefined, { vertaal: false })]} nou={nou} />
    );
    const kaarte = container.querySelectorAll("[data-partyverklaring]");
    expect(kaarte).toHaveLength(2);
    for (const kaart of kaarte) {
      const details = kaart.querySelector("details") as HTMLDetailsElement;
      expect(details.open).toBe(false);
      expect(details.querySelectorAll("p")).not.toHaveLength(0);
    }
    expect(screen.getByText("ActionSA se opskrif")).toBeTruthy();
    expect(screen.getByText(KOPIE.partye_vertaal_etiket, { exact: false })).toBeTruthy();
    expect(screen.getByText(KOPIE.partye_afrikaans_etiket, { exact: false })).toBeTruthy();
    const skakel = screen.getByText(/ActionSA ORIGINAL HEADLINE/).closest("a")!;
    expect(skakel.getAttribute("href")).toMatch(/^https:\/\/x\/ActionSA\//);
    expect(skakel.getAttribute("target")).toBe("_blank");
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
