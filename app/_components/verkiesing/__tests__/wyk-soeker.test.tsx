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
    provinsie: "Gauteng",
    adres: null,
    wyk_ids: ["19100056"],
    wyk_nrs: [56],
    teiken: "/wyk/19100056",
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

/** Answers both endpoints: `/api/soek` with `rye`, `/api/wyk-by-punt` with `wyk`. */
function stelAlbei(rye: SoekRy[], wyk: unknown) {
  const haal = vi.fn(async (url: string, _init?: RequestInit) => {
    if (String(url).startsWith("/api/wyk-by-punt")) {
      return { ok: true, status: 200, json: async () => ({ wyk }) };
    }
    return { ok: true, status: 200, json: async () => ({ resultate: rye }) };
  });
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
    stelSoek([ry({ teiken: "/wyk/19100056" })]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklyn");
    await screen.findByRole("option", { name: /Brooklyn/ });

    await gebruiker.keyboard("{ArrowDown}{Enter}");
    expect(stoot).toHaveBeenCalledWith("/wyk/19100056");
  });

  it("volg 'n stemlokaal se teiken presies, anker ingesluit", async () => {
    stelSoek([
      ry({ soort: "stemlokaal", etiket: "KAYA MANDI HIGH SCHOOL", teiken: "/wyk/10204009#stemlokale" }),
    ]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Kaya Mandi");
    await screen.findByRole("option", { name: /KAYA MANDI/ });

    await gebruiker.keyboard("{ArrowDown}{Enter}");
    expect(stoot).toHaveBeenCalledWith("/wyk/10204009#stemlokale");
  });

  it("hanteer pyltjies en Escape volgens die combobox-patroon", async () => {
    stelSoek([
      ry({ etiket: "Brooklyn", wyk_ids: ["19100056"], wyk_nrs: [56], teiken: "/wyk/19100056" }),
      ry({
        etiket: "Brooklyn",
        muni_naam: "Stad Kaapstad",
        wyk_ids: ["19100055"],
        wyk_nrs: [55],
        teiken: "/wyk/19100055",
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
    const haal = vi.fn(async (url: string, _init?: RequestInit) => {
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

    // No URL the component builds may carry a digit of either coordinate — the ward
    // lookup POSTs the point in its body instead.
    for (const [url] of haal.mock.calls) {
      const u = String(url);
      expect(u).not.toContain("25.7");
      expect(u).not.toContain("28.2");
      expect(u).not.toMatch(/lat|lng/);
    }
    const puntRoep = haal.mock.calls.find((c) => String(c[0]).startsWith("/api/wyk-by-punt"));
    expect(puntRoep).toBeDefined();
    expect(puntRoep?.[1]?.method).toBe("POST");
    expect(JSON.parse(String(puntRoep?.[1]?.body))).toEqual({ lat: LAT, lng: LNG });

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

  it("wys die buite-'n-wyk-boodskap wanneer die punt in geen wyk val nie", async () => {
    stelAlbei([], null);
    stelLigging({
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { latitude: -34.4, longitude: 20.9 } } as GeolocationPosition),
    });
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.click(liggingKnoppie());

    expect(await screen.findByText(eersteLyn(KOPIE.soek_ligging_buite))).toBeTruthy();
    expect(stoot).not.toHaveBeenCalled();
  });

  it("hou 20 rye binne 'n rolbare houer", async () => {
    const baie = Array.from({ length: 20 }, (_, i) =>
      ry({
        etiket: `Brooklyn ${i + 1}`,
        wyk_ids: [`191000${String(i).padStart(2, "0")}`],
        wyk_nrs: [i + 1],
        teiken: `/wyk/191000${String(i).padStart(2, "0")}`,
        rang: i + 1,
      })
    );
    stelSoek(baie);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklyn");

    const lys = await screen.findByRole("listbox");
    // Every row renders — nothing is silently dropped.
    expect(within(lys).getAllByRole("option")).toHaveLength(20);
    // ...and the list is bounded and scrollable rather than 1 280 px tall.
    expect(lys.className).toContain("overflow-y-auto");
    expect(lys.className).toMatch(/max-h-\[min\(60vh,26rem\)\]/);
  });

  it("laat val 'n stadige antwoord vir 'n ou navraag", async () => {
    const sluis: { los: (() => void) | null } = { los: null };
    const stadigeRye = [ry({ etiket: "STADIGE OU ANTWOORD", teiken: "/wyk/19100001" })];
    const vinnigeRye = [ry({ etiket: "Brooklyn Vinnig", teiken: "/wyk/19100002" })];
    const haal = vi.fn(async (url: string, _init?: RequestInit) => {
      const q = new URL(url, "http://t").searchParams.get("q");
      if (q === "Broo") {
        await new Promise<void>((r) => {
          sluis.los = r;
        });
        return { ok: true, status: 200, json: async () => ({ resultate: stadigeRye }) };
      }
      return { ok: true, status: 200, json: async () => ({ resultate: vinnigeRye }) };
    });
    vi.stubGlobal("fetch", haal);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    const boks = soekboks();
    // First query goes out and hangs.
    await gebruiker.type(boks, "Broo");
    await waitFor(() => expect(haal).toHaveBeenCalledTimes(1));
    // The reader types on; the second query answers immediately.
    await gebruiker.type(boks, "klyn");
    await screen.findByRole("option", { name: /Brooklyn Vinnig/ });

    // Now let the stale response land.
    sluis.los?.();
    await new Promise((r) => setTimeout(r, 30));

    expect(screen.queryByText("STADIGE OU ANTWOORD")).toBeNull();
    expect(soekboks().getAttribute("aria-expanded")).toBe("true");
    const opsies = screen.getAllByRole("option");
    expect(opsies).toHaveLength(1);
    expect(opsies[0].textContent).toContain("Brooklyn Vinnig");
  });

  it("wys provinsie vir 'n plek en die adres vir 'n stemlokaal", async () => {
    stelSoek([
      ry({ etiket: "Brooklyn", provinsie: "Gauteng", adres: null }),
      ry({
        soort: "stemlokaal",
        etiket: "BROOKLYN PRIMARY SCHOOL",
        provinsie: "Gauteng",
        adres: "279 Murray Street",
        rang: 2,
      }),
      ry({
        soort: "stemlokaal",
        etiket: "BROOKLYN TENT",
        provinsie: "Gauteng",
        // The 2 stations with an empty source address arrive as null and show no third part.
        adres: null,
        rang: 3,
      }),
    ]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklyn");
    await screen.findByRole("listbox");

    expect(screen.getByText("Stad Tshwane · Gauteng")).toBeTruthy();
    expect(screen.getByText("Stad Tshwane · 279 Murray Street")).toBeTruthy();
    // A station with no address: municipality only, and no dangling separator.
    const sonderAdres = screen.getByRole("option", { name: /BROOKLYN TENT/ });
    expect(sonderAdres.textContent).toContain("Stad Tshwane");
    expect(sonderAdres.textContent).not.toContain("Stad Tshwane ·");
  });

  it("gebruik die enkelvoud wanneer daar een resultaat is", async () => {
    stelSoek([ry()]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    await gebruiker.type(soekboks(), "Brooklyn");
    await screen.findByRole("listbox");

    const telling = screen.getByRole("status");
    expect(telling.textContent).toBe(
      vulIn(KOPIE.soek_resultate_telling_een, { n: 1, q: "Brooklyn" })
    );
    expect(telling.textContent).not.toContain("1 resultate");
  });

  it("laat nie 'n bengelende aria-controls terwyl die lys toe is nie", async () => {
    stelSoek([ry()]);
    const gebruiker = userEvent.setup();
    render(<WykSoeker />);

    const boks = soekboks();
    expect(boks.hasAttribute("aria-controls")).toBe(false);

    await gebruiker.type(boks, "Brooklyn");
    await waitFor(() => expect(boks.getAttribute("aria-expanded")).toBe("true"));
    const beheer = boks.getAttribute("aria-controls");
    expect(beheer).toBeTruthy();
    expect(document.getElementById(String(beheer))).toBeTruthy();

    await gebruiker.keyboard("{Escape}");
    expect(boks.hasAttribute("aria-controls")).toBe(false);
  });
});
