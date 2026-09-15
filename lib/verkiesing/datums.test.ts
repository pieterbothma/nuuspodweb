import { describe, it, expect } from "vitest";
import { aftelling, komendeMylpale, spesialeStemStatus, STEMDAG } from "./datums";

describe("aftelling", () => {
  it("counts whole days, hours and minutes to 07:00 on election day", () => {
    expect(aftelling(new Date("2026-09-14T20:00:00+02:00"))).toEqual({
      dae: 50,
      ure: 11,
      minute: 0,
      verby: false,
    });
  });

  it("reports verby once voting has opened", () => {
    expect(aftelling(STEMDAG).verby).toBe(true);
  });
});

describe("komendeMylpale", () => {
  it("drops milestones whose end has passed and keeps list order", () => {
    const ids = komendeMylpale(new Date("2026-09-17T12:00:00+02:00")).map((m) => m.id);
    expect(ids).toEqual(["spesiale-aansoeke", "trekking", "spesiale-stemme"]);
  });

  it("keeps the special-vote window visible until 17:00 on 12 October", () => {
    const voor = komendeMylpale(new Date("2026-10-12T16:59:00+02:00"), 1);
    const na = komendeMylpale(new Date("2026-10-12T17:01:00+02:00"), 1);
    expect(voor[0].id).toBe("spesiale-aansoeke");
    expect(na[0].id).toBe("spesiale-stemme");
  });

  it("is empty after voting closes", () => {
    expect(komendeMylpale(new Date("2026-11-04T21:01:00+02:00"))).toEqual([]);
  });
});

describe("spesialeStemStatus", () => {
  it("is 'toe' before applications open on 21 September", () => {
    expect(spesialeStemStatus(new Date("2026-09-20T23:59:00+02:00"))).toBe("toe");
  });

  it("is 'oop' the moment applications open at 00:00 on 21 September", () => {
    expect(spesialeStemStatus(new Date("2026-09-21T00:00:00+02:00"))).toBe("oop");
  });

  it("is still 'oop' at 16:59 on 12 October", () => {
    expect(spesialeStemStatus(new Date("2026-10-12T16:59:00+02:00"))).toBe("oop");
  });

  it("is 'verby' at 17:00 on 12 October", () => {
    expect(spesialeStemStatus(new Date("2026-10-12T17:00:00+02:00"))).toBe("verby");
  });
});
