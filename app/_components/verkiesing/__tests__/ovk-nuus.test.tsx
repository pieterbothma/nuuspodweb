import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { OvkNuus } from "../ovk-nuus";

afterEach(cleanup);

describe("OvkNuus", () => {
  it("renders nothing before any release is loaded", () => {
    expect(render(<OvkNuus items={[]} />).container.innerHTML).toBe("");
  });

  it("shows each release with its date and the IEC's headline verbatim, linking to the release", () => {
    const { container } = render(
      <OvkNuus
        items={[
          { id: 5725, titel: "Electoral Commission Certifies 136 790 Candidates", datum: "2026-09-16", url: "https://www.elections.org.za/pw/News-And-Media/News-List/News/IECNews/5725" },
        ]}
      />
    );
    expect(screen.getByText(KOPIE.ovk_nuus_opskrif)).toBeTruthy();
    const skakel = container.querySelector("[data-ovk-nuus='5725'] a")!;
    expect(skakel.getAttribute("href")).toMatch(/\/IECNews\/5725$/);
    expect(skakel.getAttribute("target")).toBe("_blank");
    expect(skakel.textContent).toContain("Electoral Commission Certifies 136 790 Candidates");
    expect(container.querySelector("time")?.getAttribute("dateTime")).toBe("2026-09-16");
  });
});
