import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { Partyverklaring } from "@/lib/verkiesing/partye";

const { haalPartyverklaring, geenGevind } = vi.hoisted(() => ({
  haalPartyverklaring: vi.fn(),
  geenGevind: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/lib/verkiesing/partye", async (oorspronklik) => ({
  ...(await oorspronklik<typeof import("@/lib/verkiesing/partye")>()),
  haalPartyverklaring,
}));
vi.mock("@/lib/supabase-rest", () => ({ lees: vi.fn(async () => null), voegIn: vi.fn(async () => false) }));
vi.mock("next/navigation", () => ({ notFound: geenGevind, usePathname: () => "/verklaring/5" }));
vi.mock("next/image", () => ({
  // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
  default: (p: Record<string, unknown>) => <img {...(p as object)} />,
}));

import VerklaringBladsy, { generateMetadata } from "../[id]/page";

const DA: Partyverklaring = {
  id: 5,
  party: "Democratic Alliance (DA)",
  bron_url: "https://www.da.org.za/2026/09/x",
  titel_oorspronklik: "DA notes USA’s visa restriction",
  titel_af: "DA neem kennis van VSA se visumbeperking",
  teks_af: "Eerste paragraaf.\n\nTweede paragraaf.",
  vertaal: true,
  gepubliseer_om: "2026-09-16T13:16:01Z",
};

const wys = async (id: string) => render(await VerklaringBladsy({ params: Promise.resolve({ id }) }));

beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

describe("/verklaring/[id]", () => {
  it("is the site's 404 for anything not approved or not found", async () => {
    haalPartyverklaring.mockResolvedValue(null);
    await expect(wys("999")).rejects.toThrow("NEXT_NOT_FOUND");
    const meta = await generateMetadata({ params: Promise.resolve({ id: "999" }) });
    expect(meta.title).toBe(KOPIE.nie_gevind_titel);
  });

  it("shows the logo, party, headline, every paragraph and the labelled link to the original", async () => {
    haalPartyverklaring.mockResolvedValue(DA);
    const { container } = await wys("5");
    expect(container.querySelector("h1")?.textContent).toBe(DA.titel_af);
    expect(container.querySelector("article img")?.getAttribute("src")).toBe("/partye/da.png");
    expect(screen.getByText("Eerste paragraaf.")).toBeTruthy();
    expect(screen.getByText("Tweede paragraaf.")).toBeTruthy();
    const bron = container.querySelector("[data-bron]")!;
    expect(bron.textContent).toContain(KOPIE.partye_vertaal_etiket);
    const skakel = bron.querySelector("a")!;
    expect(skakel.getAttribute("href")).toBe(DA.bron_url);
    expect(skakel.textContent).toContain(DA.titel_oorspronklik);
    const meta = await generateMetadata({ params: Promise.resolve({ id: "5" }) });
    expect(meta.title).toBe(`${DA.titel_af} — Verkiesing 2026`);
  });

  it("says a party's own Afrikaans statement was not translated", async () => {
    haalPartyverklaring.mockResolvedValue({ ...DA, party: "Vryheidsfront Plus (VF Plus)", vertaal: false });
    const { container } = await wys("5");
    expect(container.querySelector("[data-bron]")!.textContent).toContain(KOPIE.partye_afrikaans_etiket);
  });
});

describe("geldigeVerklaringId", () => {
  it("accepts only positive whole numbers", async () => {
    const { geldigeVerklaringId } = await vi.importActual<typeof import("@/lib/verkiesing/partye")>("@/lib/verkiesing/partye");
    expect(geldigeVerklaringId("5")).toBe(true);
    for (const sleg of ["0", "-1", "5a", "1.5", "", "99999999999999999"]) expect(geldigeVerklaringId(sleg)).toBe(false);
  });
});
