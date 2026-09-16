import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { groepeer, haalMuniNuus, haalWykNuus, type PlaaslikeStorie } from "../plaaslik";

const s = (o: Partial<PlaaslikeStorie>): PlaaslikeStorie => ({
  vlak: "wyk",
  plek: "Pretoria North",
  titel: "Opskrif",
  bron: "Rekord",
  url: `https://x/${Math.random()}`,
  gepubliseer_om: "2026-09-16T08:00:00Z",
  ...o,
});

describe("groepeer", () => {
  it("orders levels narrowest first and drops empty levels", () => {
    const uit = groepeer([s({ vlak: "munisipaliteit", plek: "Tshwane" }), s({ vlak: "wyk" })]);
    expect(uit.map((g) => g.vlak)).toEqual(["wyk", "munisipaliteit"]);
  });

  it("names the place in the heading only when every story in the level shares it", () => {
    expect(groepeer([s({ vlak: "dorp", plek: "Krugersdorp" }), s({ vlak: "dorp", plek: "Krugersdorp" })])[0].plek).toBe(
      "Krugersdorp"
    );
    expect(groepeer([s({ vlak: "dorp", plek: "Krugersdorp" }), s({ vlak: "dorp", plek: "Rangeview" })])[0].plek).toBeNull();
  });
});

describe("haal", () => {
  beforeEach(() => {
    vi.stubEnv("SUPABASE_URL", "https://toets.voorbeeld");
    vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "toets-sleutel");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("calls the ward RPC with the plaaslik cache tag", async () => {
    const haal = vi.fn(async (url: string, init: RequestInit & { next?: unknown }) => {
      expect(url).toBe("https://toets.voorbeeld/rest/v1/rpc/plaaslike_nuus_vir_wyk");
      expect(JSON.parse(String(init.body))).toEqual({ p_wyk_id: "79900002", p_perk: 3 });
      expect(init.next).toEqual({ tags: ["plaaslik"], revalidate: 900 });
      return { ok: true, json: async () => [s({})] };
    });
    vi.stubGlobal("fetch", haal);
    expect(await haalWykNuus("79900002")).toHaveLength(1);
  });

  it("degrades to empty, never throws, when the database is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 503, json: async () => [] })));
    expect(await haalWykNuus("79900002")).toEqual([]);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("netwerk"); }));
    expect(await haalMuniNuus("TSH")).toEqual([]);
  });
});
