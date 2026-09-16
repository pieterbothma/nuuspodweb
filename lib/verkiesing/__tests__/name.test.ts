import { describe, expect, it } from "vitest";
import { distrikNaam, muniNaam, provinsieNaam } from "@/lib/verkiesing/name";

/**
 * Display-only translation of the two proper nouns the MDB/IEC publishes in English. The
 * database keeps the official name; these helpers only decide what a reader sees, so the
 * important properties are (a) every known key is covered and (b) an unknown key is passed
 * through untouched rather than blanking a heading.
 */

describe("provinsieNaam", () => {
  it("vertaal al nege provinsies", () => {
    expect(provinsieNaam("Eastern Cape")).toBe("Oos-Kaap");
    expect(provinsieNaam("Free State")).toBe("Vrystaat");
    expect(provinsieNaam("Gauteng")).toBe("Gauteng");
    expect(provinsieNaam("KwaZulu-Natal")).toBe("KwaZulu-Natal");
    expect(provinsieNaam("Limpopo")).toBe("Limpopo");
    expect(provinsieNaam("Mpumalanga")).toBe("Mpumalanga");
    expect(provinsieNaam("North West")).toBe("Noordwes");
    expect(provinsieNaam("Northern Cape")).toBe("Noord-Kaap");
    expect(provinsieNaam("Western Cape")).toBe("Wes-Kaap");
  });

  it("gee 'n onbekende of leë naam onveranderd terug", () => {
    expect(provinsieNaam("Wes-Kaap")).toBe("Wes-Kaap");
    expect(provinsieNaam("Atlantis")).toBe("Atlantis");
    expect(provinsieNaam("")).toBe("");
  });
});

describe("muniNaam", () => {
  it("vertaal al agt metro's op hul kode", () => {
    expect(muniNaam("CPT", "City of Cape Town")).toBe("Stad Kaapstad");
    expect(muniNaam("JHB", "City of Johannesburg")).toBe("Stad Johannesburg");
    expect(muniNaam("TSH", "City of Tshwane")).toBe("Stad Tshwane");
    expect(muniNaam("EKU", "Ekurhuleni")).toBe("Ekurhuleni");
    expect(muniNaam("ETH", "eThekwini")).toBe("eThekwini");
    expect(muniNaam("NMA", "Nelson Mandela Bay")).toBe("Nelson Mandela Baai");
    expect(muniNaam("MAN", "Mangaung")).toBe("Mangaung");
    expect(muniNaam("BUF", "Buffalo City")).toBe("Buffalo City");
  });

  it("laat elke ander munisipaliteit se amptelike naam staan", () => {
    expect(muniNaam("WC024", "Stellenbosch")).toBe("Stellenbosch");
    expect(muniNaam("DC2", "Cape Winelands")).toBe("Cape Winelands");
    expect(muniNaam("EC109", "Kou-Kamma")).toBe("Kou-Kamma");
    expect(muniNaam("NW383", "Mafikeng")).toBe("Mafikeng");
  });

  it("val terug op die naam, en dan op die kode — nooit op 'n leë string nie", () => {
    expect(muniNaam("XX999", "Iets")).toBe("Iets");
    expect(muniNaam("WC024", "")).toBe("WC024");
    expect(muniNaam("", "")).toBe("");
  });

  it("vertaal net op die kode, nooit op die Engelse naam nie", () => {
    // A local municipality that happened to share a metro's name must not be renamed.
    expect(muniNaam("WC999", "City of Cape Town")).toBe("City of Cape Town");
  });
});

describe("distrikNaam", () => {
  it("vertaal die vyf distrikte met 'n Engelse beskrywing as naam", () => {
    expect(distrikNaam("DC1", "West Coast")).toBe("Weskus");
    expect(distrikNaam("DC2", "Cape Winelands")).toBe("Kaapse Wynland");
    expect(distrikNaam("DC4", "Garden Route")).toBe("Tuinroete");
    expect(distrikNaam("DC5", "Central Karoo")).toBe("Sentraal-Karoo");
    expect(distrikNaam("DC48", "West Rand")).toBe("Wesrand");
  });

  it("laat elke ander distrik se eienaam staan", () => {
    expect(distrikNaam("DC3", "Overberg")).toBe("Overberg");
    expect(distrikNaam("DC25", "Amajuba")).toBe("Amajuba");
    expect(distrikNaam("DC32", "Ehlanzeni")).toBe("Ehlanzeni");
    expect(distrikNaam("DC42", "Sedibeng")).toBe("Sedibeng");
    expect(distrikNaam("DC6", "Namakwa")).toBe("Namakwa");
    expect(distrikNaam("DC10", "Sarah Baartman")).toBe("Sarah Baartman");
  });

  it("los dit op uit die naam alleen, vir 'n oproeper sonder die kode", () => {
    // MuniOpsomming carries distrik_naam but not distrik_kode.
    expect(distrikNaam(null, "Cape Winelands")).toBe("Kaapse Wynland");
    expect(distrikNaam(undefined, "West Rand")).toBe("Wesrand");
    expect(distrikNaam(null, "Overberg")).toBe("Overberg");
  });

  it("val terug op die naam, en dan op die kode — nooit op 'n leë string nie", () => {
    expect(distrikNaam("DC99", "Nuwe Distrik")).toBe("Nuwe Distrik");
    expect(distrikNaam(null, "Nuwe Distrik")).toBe("Nuwe Distrik");
    expect(distrikNaam("DC2", "")).toBe("Kaapse Wynland");
    expect(distrikNaam("DC99", "")).toBe("DC99");
    expect(distrikNaam(null, "")).toBe("");
  });

  it("gee die kode voorkeur bo die naam-indeks", () => {
    // A row whose name has changed must not be renamed by the old name's entry.
    expect(distrikNaam("DC3", "Cape Winelands")).toBe("Cape Winelands");
  });
});
