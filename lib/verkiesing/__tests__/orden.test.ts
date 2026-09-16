import { describe, expect, it } from "vitest";
import { geenMeerderheid, sorteerKandidate, sorteerLysKandidate, sorteerPartyLyste } from "../orden";

describe("sorteerKandidate", () => {
  it("sorteer alfabeties op van, dan volle naam, met Afrikaanse kollasie", () => {
    const uit = sorteerKandidate([
      { volle_naam: "Zani", van: "ZULU", party_naam: "P", onafhanklik: false, lys_posisie: null },
      { volle_naam: "Anna", van: "ÅBERG", party_naam: "P", onafhanklik: false, lys_posisie: null },
      { volle_naam: "Bea", van: "BOTHA", party_naam: null, onafhanklik: true, lys_posisie: null },
    ]);
    expect(uit.map((k) => k.van)).toEqual(["ÅBERG", "BOTHA", "ZULU"]);
  });
  it("gebruik lys_posisie wanneer dit die stembriefvolgorde is", () => {
    const uit = sorteerKandidate(
      [
        { volle_naam: "B", van: "B", party_naam: "P", onafhanklik: false, lys_posisie: 2 },
        { volle_naam: "A", van: "A", party_naam: "P", onafhanklik: false, lys_posisie: 1 },
      ],
      "stembrief"
    );
    expect(uit.map((k) => k.van)).toEqual(["A", "B"]);
  });
});

describe("sorteerLysKandidate", () => {
  it("volg altyd die party se eie lys_posisie; rye sonder posisie kom laaste, alfabeties", () => {
    const uit = sorteerLysKandidate([
      { volle_naam: "Zed", van: "ZULU", party_naam: "P", onafhanklik: false, lys_posisie: null },
      { volle_naam: "Bea", van: "BOTHA", party_naam: "P", onafhanklik: false, lys_posisie: 2 },
      { volle_naam: "Ari", van: "ABERG", party_naam: "P", onafhanklik: false, lys_posisie: null },
      { volle_naam: "Cas", van: "CRONJE", party_naam: "P", onafhanklik: false, lys_posisie: 1 },
    ]);
    expect(uit.map((k) => k.van)).toEqual(["CRONJE", "BOTHA", "ABERG", "ZULU"]);
  });
});

describe("sorteerPartyLyste", () => {
  it("sorteer alfabeties sonder volgorde-data", () => {
    expect(sorteerPartyLyste([{ party_naam: "ZZZ", posisie: null, kandidate: [] }, { party_naam: "AAA", posisie: null, kandidate: [] }]).map((p) => p.party_naam)).toEqual(["AAA", "ZZZ"]);
  });
  it("sorteer op posisie sodra die trekking gebeur het", () => {
    expect(sorteerPartyLyste([{ party_naam: "AAA", posisie: 2, kandidate: [] }, { party_naam: "ZZZ", posisie: 1, kandidate: [] }]).map((p) => p.party_naam)).toEqual(["ZZZ", "AAA"]);
  });
  it("sorteer nooit op setels of lysgrootte nie", () => {
    const groot = { party_naam: "ZZZ", posisie: null, kandidate: [1, 2, 3].map(() => ({ volle_naam: "x", van: "x", party_naam: "ZZZ", onafhanklik: false, lys_posisie: null })) };
    const klein = { party_naam: "AAA", posisie: null, kandidate: [] };
    expect(sorteerPartyLyste([groot, klein]).map((p) => p.party_naam)).toEqual(["AAA", "ZZZ"]);
  });
});

describe("geenMeerderheid", () => {
  it("meet teen die volle raadsgrootte, insluitend onafhanklikes", () => {
    // 11-seat council: biggest party 5 → no majority
    expect(geenMeerderheid({ raadsgrootte: 11, onafhanklike_setels: 1, rye: [{ party_naam: "A", setels_wyk: 3, setels_pv: 2, setels_totaal: 5 }, { party_naam: "B", setels_wyk: 2, setels_pv: 3, setels_totaal: 5 }] })).toBe(true);
  });
  it("is vals wanneer een party meer as die helfte het", () => {
    expect(geenMeerderheid({ raadsgrootte: 45, onafhanklike_setels: 0, rye: [{ party_naam: "DA", setels_wyk: 19, setels_pv: 9, setels_totaal: 28 }, { party_naam: "ANC", setels_wyk: 4, setels_pv: 4, setels_totaal: 8 }] })).toBe(false);
  });
  it("is vals wanneer die raadsgrootte ontbreek of nul is", () => {
    expect(geenMeerderheid({ raadsgrootte: 0, onafhanklike_setels: 0, rye: [{ party_naam: "A", setels_wyk: 1, setels_pv: 0, setels_totaal: 1 }] })).toBe(false);
  });
  it("is vals sonder party-rye, want dan is daar niks om te meet nie", () => {
    expect(geenMeerderheid({ raadsgrootte: 45, onafhanklike_setels: 0, rye: [] })).toBe(false);
  });
});
