import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  haalAlleMuniKodes,
  haalAlleWykIds,
  haalMuni,
  haalStembriewe,
  haalStemstasies,
  haalWyk,
  type Wyk,
} from "../wyksoeker";

/** Fake credentials — `lees` only needs both env vars set to attempt a fetch. */
beforeEach(() => {
  vi.stubEnv("SUPABASE_URL", "https://toets.voorbeeld");
  vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "toets-sleutel");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

type Antwoord = unknown[] | null;

/** Routes each PostgREST request to the first matching predicate and records every URL. */
function stubFetch(roetes: Array<[RegExp, Antwoord]>) {
  const oproepe: Array<{ url: string; init: RequestInit & { next?: unknown } }> = [];
  const haal = vi.fn(async (url: string, init: RequestInit & { next?: unknown }) => {
    oproepe.push({ url, init });
    const treffer = roetes.find(([patroon]) => patroon.test(url));
    const data = treffer ? treffer[1] : [];
    if (data === null) return { ok: false, status: 503, json: async () => [] };
    return { ok: true, status: 200, json: async () => data };
  });
  vi.stubGlobal("fetch", haal);
  return oproepe;
}

const STELLENBOSCH_WYK = {
  wyk_id: "19100055",
  wyk_nr: 7,
  muni_kode: "WC024",
  munisipaliteite: {
    naam: "Stellenbosch",
    tipe: "plaaslik",
    distrik_kode: "DC2",
    provinsie: "Western Cape",
  },
};

const WYK: Wyk = {
  wyk_id: "19100055",
  wyk_nr: 7,
  muni_kode: "WC024",
  muni_naam: "Stellenbosch",
  muni_tipe: "plaaslik",
  distrik_kode: "DC2",
  distrik_naam: "Cape Winelands",
  provinsie: "Western Cape",
};

describe("id-validering", () => {
  it("raak nooit die databasis vir 'n ongeldige wyk_id nie", async () => {
    const oproepe = stubFetch([]);
    expect(await haalWyk("abc")).toBeNull();
    expect(await haalWyk("1910005")).toBeNull();
    expect(await haalWyk("19100055; drop table wyke")).toBeNull();
    expect(await haalStemstasies("abc")).toEqual([]);
    expect(oproepe).toHaveLength(0);
  });

  it("raak nooit die databasis vir 'n ongeldige muni-kode nie", async () => {
    const oproepe = stubFetch([]);
    expect(await haalMuni("wc024")).toBeNull();
    expect(await haalMuni("WC0245")).toBeNull();
    expect(await haalMuni("")).toBeNull();
    expect(oproepe).toHaveLength(0);
  });

  it("aanvaar die egte kodes", async () => {
    const oproepe = stubFetch([
      [/munisipaliteite\?kode=eq\.TSH/, [{ kode: "TSH", naam: "City of Tshwane", tipe: "metro", distrik_kode: null, provinsie: "Gauteng" }]],
    ]);
    expect(await haalMuni("TSH")).not.toBeNull();
    expect(oproepe.length).toBeGreaterThan(0);
  });
});

describe("haalWyk", () => {
  it("bou 'n Wyk uit die ingebedde munisipaliteit en 'n tweede distrik-lesing", async () => {
    const oproepe = stubFetch([
      [/^.*wyke\?wyk_id=eq\.19100055/, [STELLENBOSCH_WYK]],
      [/munisipaliteite\?kode=eq\.DC2/, [{ naam: "Cape Winelands" }]],
    ]);
    expect(await haalWyk("19100055")).toEqual(WYK);
    expect(oproepe).toHaveLength(2);
    expect(oproepe[0].url).toContain("select=wyk_id,wyk_nr,muni_kode,munisipaliteite!inner(naam,tipe,distrik_kode,provinsie)");
  });

  it("gee null wanneer die wyk nie bestaan nie", async () => {
    stubFetch([[/wyke\?wyk_id=eq/, []]]);
    expect(await haalWyk("19100055")).toBeNull();
  });

  it("gee null — nie 'n uitsondering nie — wanneer die databasis af is", async () => {
    stubFetch([[/wyke\?wyk_id=eq/, null]]);
    expect(await haalWyk("19100055")).toBeNull();
  });

  it("los distrik_naam leeg vir 'n metro sonder distrik", async () => {
    const oproepe = stubFetch([
      [/wyke\?wyk_id=eq/, [{ wyk_id: "79800001", wyk_nr: 1, muni_kode: "TSH", munisipaliteite: { naam: "City of Tshwane", tipe: "metro", distrik_kode: null, provinsie: "Gauteng" } }]],
    ]);
    const wyk = await haalWyk("79800001");
    expect(wyk?.distrik_kode).toBeNull();
    expect(wyk?.distrik_naam).toBeNull();
    expect(oproepe).toHaveLength(1);
  });
});

describe("haalStemstasies", () => {
  it("lees op naam gesorteer en hou 'n leë adres as null", async () => {
    const oproepe = stubFetch([
      [/stemstasies\?/, [{ vd_nommer: "32870001", naam: "Kayamandi Sentrum", adres: "" }]],
    ]);
    expect(await haalStemstasies("19100055")).toEqual([
      { vd_nommer: "32870001", naam: "Kayamandi Sentrum", adres: null },
    ]);
    expect(oproepe[0].url).toContain("order=naam.asc");
  });

  it("gee 'n leë lys wanneer die databasis af is", async () => {
    stubFetch([[/stemstasies\?/, null]]);
    expect(await haalStemstasies("19100055")).toEqual([]);
  });
});

describe("haalStembriewe", () => {
  const wykRy = { volle_naam: "Bea Botha", van: "BOTHA", onafhanklik: false, lys_posisie: null, partye: { naam: "AAA" } };
  const pvRye = [
    { volle_naam: "Zani Zulu", van: "ZULU", onafhanklik: false, lys_posisie: 1, partye: { naam: "ZZZ" } },
    { volle_naam: "Anna Aberg", van: "ABERG", onafhanklik: false, lys_posisie: 2, partye: { naam: "ZZZ" } },
    { volle_naam: "Carl Cele", van: "CELE", onafhanklik: false, lys_posisie: 1, partye: { naam: "AAA" } },
  ];

  it("groepeer PR-rye per party: partye alfabeties voor die trekking, name volgens lysposisie", async () => {
    stubFetch([
      [/kandidate\?wyk_id=eq/, [wykRy]],
      [/stembrief=eq\.pv_plaaslik/, pvRye],
      [/stembrief=eq\.pv_distrik/, []],
      [/stembrief_volgorde\?/, []],
    ]);
    const uit = await haalStembriewe(WYK);
    expect(uit.volgorde).toBe("alfabeties");
    expect(uit.pv_plaaslik.map((p) => p.party_naam)).toEqual(["AAA", "ZZZ"]);
    expect(uit.pv_plaaslik.map((p) => p.posisie)).toEqual([null, null]);
    // Within the ZZZ list the party's own list position orders the names, even before the
    // draw: it ranks candidates inside one party, never parties against each other.
    expect(uit.pv_plaaslik[1].kandidate.map((k) => k.van)).toEqual(["ZULU", "ABERG"]);
    expect(uit.wyk).toHaveLength(1);
    expect(uit.wyk[0].party_naam).toBe("AAA");
  });

  it("gebruik stembriefvolgorde sodra die trekking gebeur het", async () => {
    stubFetch([
      [/kandidate\?wyk_id=eq/, [wykRy]],
      [/stembrief=eq\.pv_plaaslik/, pvRye],
      [/stembrief=eq\.pv_distrik/, []],
      [/stembrief_volgorde\?/, [
        { muni_kode: "WC024", stembrief: "pv_plaaslik", posisie: 1, partye: { naam: "ZZZ" } },
        { muni_kode: "WC024", stembrief: "pv_plaaslik", posisie: 2, partye: { naam: "AAA" } },
      ]],
    ]);
    const uit = await haalStembriewe(WYK);
    expect(uit.volgorde).toBe("stembrief");
    expect(uit.pv_plaaslik.map((p) => p.party_naam)).toEqual(["ZZZ", "AAA"]);
    // Within ZZZ the official list position now orders the names.
    expect(uit.pv_plaaslik[0].kandidate.map((k) => k.van)).toEqual(["ZULU", "ABERG"]);
  });

  it("lees die distrik-stembrief onder die distrik se kode", async () => {
    const oproepe = stubFetch([
      [/kandidate\?wyk_id=eq/, []],
      [/stembrief=eq\.pv_plaaslik/, []],
      [/stembrief=eq\.pv_distrik/, [{ volle_naam: "Dirk Dube", van: "DUBE", onafhanklik: false, lys_posisie: 1, partye: { naam: "DDD" } }]],
      [/stembrief_volgorde\?/, []],
    ]);
    const uit = await haalStembriewe(WYK);
    expect(uit.pv_distrik.map((p) => p.party_naam)).toEqual(["DDD"]);
    const distrikOproep = oproepe.find((o) => o.url.includes("pv_distrik"));
    expect(distrikOproep?.url).toContain("muni_kode=eq.DC2");
    expect(oproepe.find((o) => o.url.includes("stembrief_volgorde"))?.url).toContain("muni_kode=in.(WC024,DC2)");
  });

  it("vra geen distrik-stembrief vir 'n metro nie", async () => {
    const oproepe = stubFetch([
      [/kandidate\?/, []],
      [/stembrief_volgorde\?/, []],
    ]);
    const metro: Wyk = { ...WYK, muni_kode: "TSH", muni_naam: "City of Tshwane", muni_tipe: "metro", distrik_kode: null, distrik_naam: null };
    const uit = await haalStembriewe(metro);
    expect(uit.pv_distrik).toEqual([]);
    expect(oproepe.some((o) => o.url.includes("pv_distrik"))).toBe(false);
  });

  it("gee leë stembriewe wanneer kandidate nog nie gelaai is nie", async () => {
    stubFetch([[/./, []]]);
    const uit = await haalStembriewe(WYK);
    expect(uit).toEqual({ wyk: [], pv_plaaslik: [], pv_distrik: [], volgorde: "alfabeties" });
  });

  it("gee leë stembriewe — nie 'n uitsondering nie — wanneer die databasis af is", async () => {
    stubFetch([[/./, null]]);
    const uit = await haalStembriewe(WYK);
    expect(uit).toEqual({ wyk: [], pv_plaaslik: [], pv_distrik: [], volgorde: "alfabeties" });
  });

  it("hanteer 'n onafhanklike kandidaat sonder party", async () => {
    stubFetch([
      [/kandidate\?wyk_id=eq/, [{ volle_naam: "Ian Independent", van: "INDEPENDENT", onafhanklik: true, lys_posisie: null, partye: null }]],
      [/kandidate\?/, []],
      [/stembrief_volgorde\?/, []],
    ]);
    const uit = await haalStembriewe(WYK);
    expect(uit.wyk[0]).toEqual({ volle_naam: "Ian Independent", van: "INDEPENDENT", party_naam: null, onafhanklik: true, lys_posisie: null });
  });
});

describe("haalMuni", () => {
  it("stel die opsomming saam, insluitend raad2021 met geenMeerderheid", async () => {
    stubFetch([
      [/munisipaliteite\?kode=eq\.WC024/, [{ kode: "WC024", naam: "Stellenbosch", tipe: "plaaslik", distrik_kode: "DC2", provinsie: "Western Cape" }]],
      [/munisipaliteite\?kode=eq\.DC2/, [{ naam: "Cape Winelands" }]],
      [/wyke\?muni_kode=eq\.WC024/, [{ wyk_id: "19100055", wyk_nr: 7 }, { wyk_id: "19100056", wyk_nr: 8 }]],
      [/stembrief_volgorde\?muni_kode=eq\.WC024/, [{ partye: { naam: "DA" } }, { partye: { naam: "ANC" } }]],
      [/raad_uitslae_2021\?/, [
        { party_naam: "DA", setels_wyk: 19, setels_pv: 9, setels_totaal: 28 },
        { party_naam: "ANC", setels_wyk: 4, setels_pv: 4, setels_totaal: 8 },
      ]],
      [/raad_grootte_2021\?/, [{ raadsgrootte_totaal: 45, onafhanklike_setels: 0 }]],
    ]);
    const uit = await haalMuni("WC024");
    expect(uit).not.toBeNull();
    expect(uit!.naam).toBe("Stellenbosch");
    expect(uit!.distrik_naam).toBe("Cape Winelands");
    expect(uit!.wyke).toEqual([{ wyk_id: "19100055", wyk_nr: 7 }, { wyk_id: "19100056", wyk_nr: 8 }]);
    expect(uit!.partye).toEqual(["ANC", "DA"]);
    expect(uit!.raad2021).toEqual({
      raadsgrootte: 45,
      onafhanklike_setels: 0,
      rye: [
        { party_naam: "ANC", setels_wyk: 4, setels_pv: 4, setels_totaal: 8 },
        { party_naam: "DA", setels_wyk: 19, setels_pv: 9, setels_totaal: 28 },
      ],
      geenMeerderheid: false,
    });
  });

  it("gee 'n leë party-lys en geen raad2021 wanneer daar niks gelaai is nie", async () => {
    stubFetch([
      [/munisipaliteite\?kode=eq\.TSH/, [{ kode: "TSH", naam: "City of Tshwane", tipe: "metro", distrik_kode: null, provinsie: "Gauteng" }]],
      [/./, []],
    ]);
    const uit = await haalMuni("TSH");
    expect(uit!.partye).toEqual([]);
    expect(uit!.wyke).toEqual([]);
    expect(uit!.raad2021).toBeNull();
  });

  it("val terug op kandidate vir die party-lys voor die trekking", async () => {
    stubFetch([
      [/munisipaliteite\?kode=eq\.WC024/, [{ kode: "WC024", naam: "Stellenbosch", tipe: "plaaslik", distrik_kode: null, provinsie: "Western Cape" }]],
      [/stembrief_volgorde\?/, []],
      [/kandidate\?/, [{ partye: { naam: "VF Plus" } }, { partye: { naam: "DA" } }, { partye: { naam: "DA" } }, { partye: null }]],
      [/./, []],
    ]);
    const uit = await haalMuni("WC024");
    expect(uit!.partye).toEqual(["DA", "VF Plus"]);
    expect(uit!.volgorde).toBe("alfabeties");
  });

  it("gee die distrik se kode saam", async () => {
    stubFetch([
      [/munisipaliteite\?kode=eq\.WC024/, [{ kode: "WC024", naam: "Stellenbosch", tipe: "plaaslik", distrik_kode: "DC2", provinsie: "Western Cape" }]],
      [/munisipaliteite\?kode=eq\.DC2/, [{ naam: "Cape Winelands" }]],
      [/./, []],
    ]);
    const uit = await haalMuni("WC024");
    expect(uit!.distrik_kode).toBe("DC2");
  });

  it("volg die getrekte PV-stembrief ná die trekking; partye net op wykstembriewe kom daarna, alfabeties", async () => {
    stubFetch([
      [/munisipaliteite\?kode=eq\.WC024/, [{ kode: "WC024", naam: "Stellenbosch", tipe: "plaaslik", distrik_kode: null, provinsie: "Western Cape" }]],
      [/stembrief_volgorde\?muni_kode=eq\.WC024/, [
        { stembrief: "pv_plaaslik", posisie: 2, partye: { naam: "AAA" } },
        { stembrief: "pv_plaaslik", posisie: 1, partye: { naam: "ZZZ" } },
        { stembrief: "wyk", posisie: 1, partye: { naam: "MMM" } },
        { stembrief: "wyk", posisie: 2, partye: { naam: "BBB" } },
        { stembrief: "wyk", posisie: 3, partye: { naam: "AAA" } },
      ]],
      [/./, []],
    ]);
    const uit = await haalMuni("WC024");
    expect(uit!.volgorde).toBe("stembrief");
    expect(uit!.partye).toEqual(["ZZZ", "AAA", "BBB", "MMM"]);
  });

  it("lees 'n distriksraad se volgorde van die pv_distrik-stembrief", async () => {
    stubFetch([
      [/munisipaliteite\?kode=eq\.DC2/, [{ kode: "DC2", naam: "Cape Winelands", tipe: "distrik", distrik_kode: null, provinsie: "Western Cape" }]],
      [/stembrief_volgorde\?muni_kode=eq\.DC2/, [
        { stembrief: "pv_plaaslik", posisie: 1, partye: { naam: "AAA" } },
        { stembrief: "pv_distrik", posisie: 1, partye: { naam: "ZZZ" } },
        { stembrief: "pv_distrik", posisie: 2, partye: { naam: "AAA" } },
      ]],
      [/./, []],
    ]);
    const uit = await haalMuni("DC2");
    expect(uit!.volgorde).toBe("stembrief");
    expect(uit!.partye).toEqual(["ZZZ", "AAA"]);
  });
});

describe("sitemap-lesings", () => {
  it("blaai deur alle wyk-ids", async () => {
    const bladsy1 = Array.from({ length: 1000 }, (_, i) => ({ wyk_id: String(10000000 + i) }));
    const bladsy2 = [{ wyk_id: "19100055" }];
    const haal = vi.fn(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () => (url.includes("offset=0") ? bladsy1 : bladsy2),
    }));
    vi.stubGlobal("fetch", haal);
    const uit = await haalAlleWykIds();
    expect(uit).toHaveLength(1001);
    expect(haal).toHaveBeenCalledTimes(2);
  });

  it("gee 'n leë lys wanneer die databasis af is", async () => {
    stubFetch([[/./, null]]);
    expect(await haalAlleWykIds()).toEqual([]);
    expect(await haalAlleMuniKodes()).toEqual([]);
  });
});

describe("kas-etikette", () => {
  it("stuur die bedoelde tags en revalidate saam met elke lesing", async () => {
    const oproepe = stubFetch([
      [/wyke\?wyk_id=eq/, [STELLENBOSCH_WYK]],
      [/munisipaliteite\?kode=eq\.DC2/, [{ naam: "Cape Winelands" }]],
    ]);
    await haalWyk("19100055");
    for (const o of oproepe) {
      expect(o.init.next).toEqual({ tags: ["wyke"], revalidate: 3600 });
    }
  });

  it("merk kandidaat-lesings met die kandidate-etiket", async () => {
    const oproepe = stubFetch([[/./, []]]);
    await haalStembriewe(WYK);
    expect(oproepe.length).toBeGreaterThan(0);
    for (const o of oproepe) {
      expect(o.init.next).toEqual({ tags: ["kandidate"], revalidate: 3600 });
    }
  });
});
