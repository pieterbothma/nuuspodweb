import { afterEach, describe, expect, it, vi } from "vitest";

const haalAlleWykIds = vi.fn();
const haalAlleMuniKodes = vi.fn();

// The sitemap only reads through the data layer's paged listers — never the database
// directly — so stubbing those two functions is enough to control what it sees.
vi.mock("@/lib/verkiesing/wyksoeker", () => ({
  haalAlleWykIds: (...args: unknown[]) => haalAlleWykIds(...args),
  haalAlleMuniKodes: (...args: unknown[]) => haalAlleMuniKodes(...args),
}));

import sitemap from "../sitemap";

describe("sitemap", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("lys die tuisblad, elke gids, elke wyk en elke munisipaliteit", async () => {
    haalAlleWykIds.mockResolvedValue([{ wyk_id: "19100055" }, { wyk_id: "19100056" }]);
    haalAlleMuniKodes.mockResolvedValue([{ kode: "WC024" }, { kode: "TSH" }]);

    const uit = await sitemap();

    expect(uit.map((u) => u.url)).toEqual(
      expect.arrayContaining([
        "https://www.nuuspod.co.za/",
        "https://www.nuuspod.co.za/adverteer",
        "https://www.nuuspod.co.za/wyk/19100055",
        "https://www.nuuspod.co.za/munisipaliteit/WC024",
      ])
    );
  });

  it("val terug na die statiese blaaie wanneer die databasis stil is", async () => {
    haalAlleWykIds.mockResolvedValue([]);
    haalAlleMuniKodes.mockResolvedValue([]);

    const uit = await sitemap();

    expect(uit.map((u) => u.url)).toEqual(
      expect.arrayContaining(["https://www.nuuspod.co.za/", "https://www.nuuspod.co.za/adverteer"])
    );
    expect(uit.some((u) => u.url.includes("/wyk/"))).toBe(false);
    expect(uit.some((u) => u.url.includes("/munisipaliteit/"))).toBe(false);
  });

  it("val terug na die statiese blaaie wanneer die datalaag gooi in plaas van faal", async () => {
    // Belt-and-braces: haalAlleWykIds/haalAlleMuniKodes never throw in practice (`lees`
    // swallows every error), but the sitemap must survive even an unexpected rejection.
    haalAlleWykIds.mockRejectedValue(new Error("databasis weg"));
    haalAlleMuniKodes.mockResolvedValue([{ kode: "WC024" }]);

    const uit = await sitemap();

    expect(uit.map((u) => u.url)).toEqual(
      expect.arrayContaining(["https://www.nuuspod.co.za/", "https://www.nuuspod.co.za/adverteer"])
    );
    expect(uit.some((u) => u.url.includes("/wyk/"))).toBe(false);
  });
});
