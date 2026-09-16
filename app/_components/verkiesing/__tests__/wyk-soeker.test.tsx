import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { SoekRy } from "@/lib/verkiesing/wyksoeker";
import { vulIn, WykSoeker } from "../wyk-soeker";

const { stoot } = vi.hoisted(() => ({ stoot: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: stoot }) }));

/** The first line of a two-line copy slot — the statement, without the advice below it. */
const eersteLyn = (teks: string) => teks.split("\n")[0];

function ry(oorskryf: Partial<SoekRy> = {}): SoekRy {
  return {
    soort: "plek",
    etiket: "Brooklyn",
    muni_kode: "TSH",
    muni_naam: "Stad Tshwane",
    wyk_ids: ["19100056"],
    wyk_nrs: [56],
    teiken: "19100056",
    rang: 1,
    ...oorskryf,
  };
}

function stelSoek(rye: SoekRy[]) {
  const haal = vi.fn(async (_url: string, _init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () => ({ resultate: rye }),
  }));
  vi.stubGlobal("fetch", haal);
  return haal;
}

function stelLigging(geo: Partial<Geolocation>) {
  Object.defineProperty(window.navigator, "geolocation", {
    value: geo,
    configurable: true,
    writable: true,
  });
}

/**
 * Only `setTimeout`/`clearTimeout` are faked — the debounce and nothing else. The two
 * timing tests drive the box with `fireEvent` rather than `user-event`, because
 * user-event's own async wrapper never settles while Vitest's clock is frozen.
 */
const valsHorlosie = () => vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });

/** Types `teks` one character at a time, as fast as the event loop allows. */
function tik(boks: HTMLInputElement, teks: string) {
  for (let i = 1; i <= teks.length; i++) {
    fireEvent.change(boks, { target: { value: teks.slice(0, i) } });
  }
}

const soekboks = () => screen.getByRole("combobox") as HTMLInputElement;
const liggingKnoppie = () => screen.getByRole("button", { name: KOPIE.soek_ligging_knoppie });

beforeEach(() => {
  stoot.mockClear();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(window.navigator as unknown as Record<string, unknown>, "geolocation");
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("WykSoeker", () => {
  it("soek nie voor 2 karakters nie", async () => {
    valsHorlosie();
    const haal = stelSoek([ry()]);
    render(<WykSoeker />);

    tik(soekboks(), "B");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(haal).not.toHaveBeenCalled();
    expect(soekboks().getAttribute("aria-expanded")).toBe("false");
  });

  it("ontdop 250 ms en doen een versoek vir vinnige tikwerk", async () => {
    valsHorlosie();
    const haal = stelSoek([ry()]);
    render(<WykSoeker />);

    tik(soekboks(), "Brooklyn");
    // Eight keystrokes, no request yet: the clock has not moved.
    expect(haal).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(249);
    });
    expect(haal).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(haal).toHaveBeenCalledTimes(1);
    expect(String(haal.mock.calls[0][0])).toContain("q=Brooklyn");
  });

  it("wys plekke en stemlokale in aparte groepe", async () => {
    stelSoek([
      ry({ etiket: "Brooklyn" }),
      ry({
        soort: "stemlokaal",
        etiket: "BROOKLYN PRIMARY SCHOOL",
        rang: 2,
      }),
    ]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklyn");

    const plekke = await screen.findByRole("group", { name: KOPIE.soek_groep_plekke });
    const opsiesPlekke = within(plekke).getAllByRole("option");
    expect(opsiesPlekke).toHaveLength(1);
    expect(opsiesPlekke[0].textContent).toContain("Brooklyn");

    const lokale = screen.getByRole("group", { name: KOPIE.soek_groep_stemlokale });
    const opsiesLokale = within(lokale).getAllByRole("option");
    expect(opsiesLokale).toHaveLength(1);
    expect(opsiesLokale[0].textContent).toContain("BROOKLYN PRIMARY SCHOOL");

    // The polite count line reports both rows.
    const telling = screen.getByRole("status");
    expect(telling.textContent).toBe(vulIn(KOPIE.soek_resultate_telling, { n: 2, q: "Brooklyn" }));
  });

  it("wys 'n kiesstrook wanneer 'n plek oor meer as een wyk val", async () => {
    stelSoek([
      ry({
        etiket: "Moreleta Park",
        wyk_ids: ["19100045", "19100047"],
        wyk_nrs: [45, 47],
        teiken: null,
      }),
    ]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Moreleta");

    const reeks = await screen.findByRole("option", { name: /Moreleta Park/ });
    await gebruiker.click(reeks);

    // A place spanning several wards can't navigate anywhere on its own.
    expect(stoot).not.toHaveBeenCalled();
    expect(
      screen.getByText(
        vulIn(KOPIE.soek_wyke_kies, { n: 2, q: "Moreleta Park" })
      )
    ).toBeTruthy();

    const wyk47 = screen.getByRole("option", { name: vulIn(KOPIE.soek_wyk_nommer, { n: 47 }) });
    await gebruiker.click(wyk47);
    expect(stoot).toHaveBeenCalledWith("/wyk/19100047");
  });

  it("navigeer na die teiken met Enter", async () => {
    stelSoek([ry({ teiken: "19100056" })]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklyn");
    await screen.findByRole("option", { name: /Brooklyn/ });

    await gebruiker.keyboard("{ArrowDown}{Enter}");
    expect(stoot).toHaveBeenCalledWith("/wyk/19100056");
  });

  it("hanteer pyltjies en Escape volgens die combobox-patroon", async () => {
    stelSoek([
      ry({ etiket: "Brooklyn", wyk_ids: ["19100056"], wyk_nrs: [56], teiken: "19100056" }),
      ry({
        etiket: "Brooklyn",
        muni_naam: "Stad Kaapstad",
        wyk_ids: ["19100055"],
        wyk_nrs: [55],
        teiken: "19100055",
        rang: 2,
      }),
    ]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    const boks = soekboks();
    await gebruiker.type(boks, "Brooklyn");
    await waitFor(() => expect(boks.getAttribute("aria-expanded")).toBe("true"));

    const opsies = screen.getAllByRole("option");
    expect(boks.hasAttribute("aria-activedescendant")).toBe(false);

    await gebruiker.keyboard("{ArrowDown}");
    expect(boks.getAttribute("aria-activedescendant")).toBe(opsies[0].id);
    expect(opsies[0].getAttribute("aria-selected")).toBe("true");

    await gebruiker.keyboard("{ArrowDown}");
    expect(boks.getAttribute("aria-activedescendant")).toBe(opsies[1].id);

    await gebruiker.keyboard("{ArrowUp}");
    expect(boks.getAttribute("aria-activedescendant")).toBe(opsies[0].id);

    // First Escape closes the popover but keeps what was typed.
    await gebruiker.keyboard("{Escape}");
    expect(boks.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(boks.value).toBe("Brooklyn");

    // Second Escape clears the box.
    await gebruiker.keyboard("{Escape}");
    expect(boks.value).toBe("");
  });

  it("wys die geweier-boodskap wanneer ligging geweier word", async () => {
    stelSoek([]);
    const getCurrentPosition = vi.fn(
      (
        _ok: PositionCallback,
        fout?: PositionErrorCallback | null,
        _opsies?: PositionOptions
      ) => {
        fout?.({ code: 1, message: "denied", PERMISSION_DENIED: 1 } as GeolocationPositionError);
      }
    );
    stelLigging({ getCurrentPosition });
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.click(liggingKnoppie());

    expect(await screen.findByText(eersteLyn(KOPIE.soek_ligging_geweier))).toBeTruthy();
    // The browser call is made with the brief's options and nothing else.
    expect(getCurrentPosition.mock.calls[0][2]).toEqual({
      timeout: 8000,
      enableHighAccuracy: false,
    });
    expect(stoot).not.toHaveBeenCalled();
  });

  it("stuur nooit koördinate na /api/soek nie", async () => {
    const LAT = -25.7479;
    const LNG = 28.2293;
    const haal = vi.fn(async (url: string) => {
      const s = String(url);
      if (s.startsWith("/api/wyk-by-punt")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            wyk: { wyk_id: "19100056", wyk_nr: 56, muni_kode: "TSH", muni_naam: "Stad Tshwane" },
          }),
        };
      }
      return { ok: true, status: 200, json: async () => ({ resultate: [ry()] }) };
    });
    vi.stubGlobal("fetch", haal);
    const logboek = [
      vi.spyOn(console, "log").mockImplementation(() => {}),
      vi.spyOn(console, "warn").mockImplementation(() => {}),
      vi.spyOn(console, "error").mockImplementation(() => {}),
      vi.spyOn(console, "info").mockImplementation(() => {}),
    ];
    stelLigging({
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { latitude: LAT, longitude: LNG } } as GeolocationPosition),
    });
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.click(liggingKnoppie());
    await waitFor(() => expect(stoot).toHaveBeenCalledWith("/wyk/19100056"));

    await gebruiker.type(soekboks(), "Brooklyn");
    await waitFor(() =>
      expect(haal.mock.calls.some((c) => String(c[0]).startsWith("/api/soek"))).toBe(true)
    );

    const soekUrls = haal.mock.calls.map((c) => String(c[0])).filter((u) => u.startsWith("/api/soek"));
    expect(soekUrls.length).toBeGreaterThan(0);
    for (const u of soekUrls) {
      expect(u).not.toContain("lat");
      expect(u).not.toContain("lng");
      expect(u).not.toContain(String(LAT));
      expect(u).not.toContain(String(LNG));
    }

    // Never stored, never logged, never in a URL the browser keeps.
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    const gelog = logboek
      .flatMap((s) => s.mock.calls)
      .flat()
      .map((v) => String(v))
      .join(" ");
    expect(gelog).not.toContain(String(LAT));
    expect(gelog).not.toContain(String(LNG));
    const genavigeer = stoot.mock.calls.flat().map(String).join(" ");
    expect(genavigeer).not.toContain(String(LAT));
    expect(genavigeer).not.toContain(String(LNG));
  });

  it("wys die geen-resultate-boodskap", async () => {
    stelSoek([]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklin");

    expect(
      await screen.findByText(vulIn(eersteLyn(KOPIE.soek_geen), { q: "Brooklin" }))
    ).toBeTruthy();
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});
