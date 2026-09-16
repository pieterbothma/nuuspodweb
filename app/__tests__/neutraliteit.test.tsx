import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { Raad2021Tabel } from "@/app/_components/verkiesing/raad-2021";
import { Stembriewe } from "@/app/_components/verkiesing/stembriewe";
import type { Kandidaat, Stembriewe as StembriefData, Wyk } from "@/lib/verkiesing/wyksoeker";

/**
 * Neutrality, rendered: no candidate or party row on the ballot or the 2021 council table
 * carries a colour token, an arbitrary colour or an inline style. The brand's red and neon
 * belong to the chrome around these rows, never to a party. Both windows of the ballot are
 * rendered (alphabetical and drawn), because the drawn window adds numbers and could add
 * styling with them.
 */

const KLEUR = /rooi|siaan|neon|\[#|#[0-9a-fA-F]{3}/;

afterEach(cleanup);

const WYK: Wyk = {
  wyk_id: "10204009",
  wyk_nr: 9,
  muni_kode: "WC024",
  muni_naam: "Stellenbosch",
  muni_tipe: "plaaslik",
  distrik_kode: "DC2",
  distrik_naam: "Cape Winelands",
  provinsie: "Western Cape",
};

function k(van: string, party: string | null, lys_posisie: number | null = null): Kandidaat {
  return { volle_naam: `${van}, Voorbeeld`, van, party_naam: party, onafhanklik: party === null, lys_posisie };
}

function briewe(volgorde: StembriefData["volgorde"]): StembriefData {
  const drawn = volgorde === "stembrief";
  return {
    wyk: [k("AAA", "PARTY A", drawn ? 1 : null), k("BBB", null, drawn ? 2 : null)],
    pv_plaaslik: [
      { party_naam: "PARTY A", posisie: drawn ? 1 : null, kandidate: [k("CCC", "PARTY A", 1)] },
      { party_naam: "PARTY B", posisie: drawn ? 2 : null, kandidate: [k("DDD", "PARTY B", 1)] },
    ],
    pv_distrik: [{ party_naam: "PARTY A", posisie: drawn ? 1 : null, kandidate: [k("EEE", "PARTY A", 1)] }],
    volgorde,
  };
}

function kleurloos(rye: NodeListOf<Element>) {
  expect(rye.length).toBeGreaterThan(0);
  for (const ry of rye) {
    for (const el of [ry, ...ry.querySelectorAll("*")]) {
      expect(el.getAttribute("class") ?? "").not.toMatch(KLEUR);
      expect(el.getAttribute("style")).toBeNull();
    }
  }
}

describe("neutraliteit", () => {
  it.each(["alfabeties", "stembrief"] as const)(
    "geen kandidaat- of partyry op die stembriewe gebruik 'n kleurtoken nie (%s)",
    (volgorde) => {
      const { container } = render(<Stembriewe wyk={WYK} stembriewe={briewe(volgorde)} />);
      kleurloos(container.querySelectorAll("[data-ry]"));
    }
  );

  it("geen partyry in die 2021-raadstabel gebruik 'n kleurtoken nie", () => {
    const { container } = render(
      <Raad2021Tabel
        raad={{
          raadsgrootte: 11,
          onafhanklike_setels: 1,
          geenMeerderheid: true,
          rye: [
            { party_naam: "PARTY A", setels_wyk: 3, setels_pv: 2, setels_totaal: 5 },
            { party_naam: "PARTY B", setels_wyk: 2, setels_pv: 3, setels_totaal: 5 },
            { party_naam: "PARTY C", setels_wyk: 0, setels_pv: 0, setels_totaal: 0 },
          ],
        }}
      />
    );
    kleurloos(container.querySelectorAll("[data-raad-ry], [data-raad-ry-nul]"));
  });
});
