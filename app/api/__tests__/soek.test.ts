import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET } from "../soek/route";
import type { SoekRy } from "@/lib/verkiesing/wyksoeker";

beforeEach(() => {
  vi.stubEnv("SUPABASE_URL", "https://toets.voorbeeld");
  vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "toets-sleutel");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const RY: SoekRy = {
  soort: "plek",
  etiket: "Stellenbosch",
  muni_kode: "WC024",
  muni_naam: "Stellenbosch",
  provinsie: "Wes-Kaap",
  adres: null,
  wyk_ids: ["19100055"],
  wyk_nrs: [7],
  teiken: "19100055",
  rang: 1,
};

function versoek(q?: string) {
  const url = q === undefined ? "http://localhost/api/soek" : `http://localhost/api/soek?q=${encodeURIComponent(q)}`;
  return new Request(url);
}

describe("GET /api/soek", () => {
  it("gee 400 vir 'n navraag korter as 2 karakters", async () => {
    const haal = vi.fn();
    vi.stubGlobal("fetch", haal);
    const res = await GET(versoek("a"));
    expect(res.status).toBe(400);
    expect(haal).not.toHaveBeenCalled();
  });

  it("gee 'n leë lys sonder om die databasis te roep", async () => {
    const haal = vi.fn();
    vi.stubGlobal("fetch", haal);
    const res = await GET(versoek());
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ resultate: [] });
    expect(haal).not.toHaveBeenCalled();
  });

  it("stuur die navraag na die soek-RPC en gee die rye terug", async () => {
    const haal = vi.fn(async (url: string, init: RequestInit) => {
      // Any URL parameter on an RPC is a PostgREST filter (400 PGRST100), so none may be sent.
      expect(String(url)).toMatch(/\/rest\/v1\/rpc\/soek$/);
      expect(init.method).toBe("POST");
      expect(JSON.parse(String(init.body))).toEqual({ q: "stellenbosch" });
      return { ok: true, status: 200, json: async () => [RY] };
    });
    vi.stubGlobal("fetch", haal);
    const res = await GET(versoek("stellenbosch"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ resultate: [RY] });
    expect(haal).toHaveBeenCalledTimes(1);
  });

  it("gee 'n leë lys wanneer die databasis stukkend is", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("netwerkfout");
      })
    );
    const res = await GET(versoek("stellenbosch"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ resultate: [] });
  });

  it("gee ook 'n leë lys wanneer die RPC 'n fout-status gee", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 503, json: async () => [] }))
    );
    const res = await GET(versoek("stellenbosch"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ resultate: [] });
  });
});
