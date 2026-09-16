import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "../wyk-by-punt/route";

beforeEach(() => {
  vi.stubEnv("SUPABASE_URL", "https://toets.voorbeeld");
  vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "toets-sleutel");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** The point travels in the body, never in the URL — see the route's own comment. */
function versoek(liggaam: unknown, rou?: string) {
  return new Request("http://localhost/api/wyk-by-punt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: rou ?? JSON.stringify(liggaam),
  });
}

// A real point inside South Africa — Stellenbosch.
const LAT = -33.9346;
const LNG = 18.86;

describe("POST /api/wyk-by-punt", () => {
  it("gee 400 vir nie-numeriese of ontbrekende koördinate", async () => {
    const haal = vi.fn();
    vi.stubGlobal("fetch", haal);

    expect((await POST(versoek({}))).status).toBe(400);
    expect((await POST(versoek({ lat: LAT }))).status).toBe(400);
    expect((await POST(versoek({ lat: "nie-'n-getal", lng: LNG }))).status).toBe(400);
    expect((await POST(versoek({ lat: LAT, lng: "" }))).status).toBe(400);
    expect((await POST(versoek(null, "nie JSON nie"))).status).toBe(400);
    expect(haal).not.toHaveBeenCalled();
  });

  it("gee 400 vir koördinate buite Suid-Afrika", async () => {
    const haal = vi.fn();
    vi.stubGlobal("fetch", haal);

    // Well north of SA (lat too high) and well out in the Atlantic (lng too low).
    expect((await POST(versoek({ lat: 51.5, lng: -0.1 }))).status).toBe(400);
    // Just outside each bound.
    expect((await POST(versoek({ lat: -20, lng: 25 }))).status).toBe(400);
    expect((await POST(versoek({ lat: -25, lng: 35 }))).status).toBe(400);
    expect(haal).not.toHaveBeenCalled();
  });

  it("weier 'n GET, want dié sou die punt in 'n URL sit", async () => {
    const haal = vi.fn();
    vi.stubGlobal("fetch", haal);
    const res = GET();
    expect(res.status).toBe(405);
    expect(haal).not.toHaveBeenCalled();
  });

  it("sit die punt in die liggaam, nooit in die stroomop-URL nie", async () => {
    const haal = vi.fn(async (url: string, init: RequestInit) => {
      const u = String(url);
      expect(u).toContain("/rest/v1/rpc/vind_wyk");
      // No digit of either coordinate may appear in the URL.
      expect(u).not.toContain("33.9");
      expect(u).not.toContain("18.8");
      expect(u).not.toContain("lat");
      expect(u).not.toContain("lng");
      expect(init.method).toBe("POST");
      expect(JSON.parse(String(init.body))).toEqual({ lat: LAT, lng: LNG });
      return { ok: true, status: 200, json: async () => [] };
    });
    vi.stubGlobal("fetch", haal);

    await POST(versoek({ lat: LAT, lng: LNG }));
    expect(haal).toHaveBeenCalledTimes(1);
  });

  it("log nooit die koördinate nie", async () => {
    const spioen = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error(`fout by ${LAT},${LNG}`);
      })
    );

    const res = await POST(versoek({ lat: LAT, lng: LNG }));

    expect(res.status).toBe(200);
    const alleLogs = spioen.mock.calls.flat().join(" ");
    expect(alleLogs).not.toContain(String(LAT));
    expect(alleLogs).not.toContain(String(LNG));
    expect(alleLogs).not.toContain("-33.9");
    expect(alleLogs).toContain("[wyk-by-punt] opsoek misluk");
  });

  it("gee { wyk: null } wanneer die punt buite elke wyk val", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        expect(String(url)).toContain("/rest/v1/rpc/vind_wyk");
        expect(init.method).toBe("POST");
        return { ok: true, status: 200, json: async () => [] };
      })
    );

    const res = await POST(versoek({ lat: LAT, lng: LNG }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ wyk: null });
  });

  it("gee die wyk wanneer die RPC een ry terug gee", async () => {
    const RY = { wyk_id: "19100055", wyk_nr: 7, muni_kode: "WC024", muni_naam: "Stellenbosch" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, status: 200, json: async () => [RY] }))
    );

    const res = await POST(versoek({ lat: LAT, lng: LNG }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ wyk: RY });
  });
});
