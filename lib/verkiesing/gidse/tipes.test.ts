import { describe, it, expect } from "vitest";
import { mdNaBlokke, vetDele } from "./tipes";

describe("vetDele", () => {
  it("splits bold runs from plain text", () => {
    expect(vetDele("**Stemdag:** Woensdag 4 November 2026.")).toEqual([
      { teks: "Stemdag:", vet: true },
      { teks: " Woensdag 4 November 2026.", vet: false },
    ]);
  });

  it("leaves text without markers alone, including a lone pair of asterisks", () => {
    expect(vetDele("Geen ** hier")).toEqual([{ teks: "Geen ** hier", vet: false }]);
  });

  it("returns nothing for an empty string", () => {
    expect(vetDele("")).toEqual([]);
  });
});

describe("mdNaBlokke", () => {
  it("reads paragraphs, headings and bullet lists", () => {
    const md = [
      "Eerste sin.",
      "",
      "## Wie kan aansoek doen?",
      "",
      "Jy moet geregistreer wees.",
      "* **Huisbesoek:** As jy nie kan reis nie.",
      "* **Stemlokaalbesoek:** As jy vooraf wil stem.",
      "",
      "Slot.",
    ].join("\n");
    expect(mdNaBlokke(md)).toEqual([
      { tipe: "p", teks: "Eerste sin." },
      { tipe: "h2", teks: "Wie kan aansoek doen?" },
      { tipe: "p", teks: "Jy moet geregistreer wees." },
      {
        tipe: "ul",
        items: ["**Huisbesoek:** As jy nie kan reis nie.", "**Stemlokaalbesoek:** As jy vooraf wil stem."],
      },
      { tipe: "p", teks: "Slot." },
    ]);
  });

  it("does not mistake a bold paragraph for a bullet", () => {
    expect(mdNaBlokke("**Let wel:** dit is vet.")).toEqual([{ tipe: "p", teks: "**Let wel:** dit is vet." }]);
  });
});
