import { describe, it, expect } from "vitest";
import { balanseer, tydEtiket, type StroomItem } from "./stroom";

const item = (id: number, bron: string): StroomItem => ({
  id,
  titel: `Opskrif ${id}`,
  bron,
  bron_tipe: "nasionaal",
  url: `https://voorbeeld.co.za/${id}`,
  gepubliseer_om: "2026-09-15T08:00:00Z",
});

describe("balanseer", () => {
  it("allows at most three items per source, in the given order", () => {
    const items = [1, 2, 3, 4].map((id) => item(id, "A")).concat(item(5, "B"));
    expect(balanseer(items).map((i) => i.id)).toEqual([1, 2, 3, 5]);
  });

  it("stops at the top limit", () => {
    const items = Array.from({ length: 40 }, (_, i) => item(i, `bron-${i}`));
    expect(balanseer(items)).toHaveLength(15);
  });
});

describe("tydEtiket", () => {
  const nou = new Date("2026-09-14T18:00:00Z"); // 20:00 SAST

  it("shows SAST clock time for today's items", () => {
    expect(tydEtiket("2026-09-14T12:20:00Z", nou)).toBe("14:20");
  });

  it("shows day and Afrikaans month for older items", () => {
    expect(tydEtiket("2026-09-12T09:00:00Z", nou)).toBe("12 Sep");
    expect(tydEtiket("2026-10-03T09:00:00Z", new Date("2026-10-20T09:00:00Z"))).toBe("3 Okt");
  });

  it("uses the SAST date, not the UTC date, to decide what is today", () => {
    // 23:30 UTC on the 13th is 01:30 SAST on the 14th.
    expect(tydEtiket("2026-09-13T23:30:00Z", nou)).toBe("01:30");
  });
});
