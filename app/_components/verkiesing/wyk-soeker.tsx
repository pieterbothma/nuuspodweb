"use client";

import { motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { KOPIE } from "@/lib/verkiesing/kopie";
import type { SoekRy } from "@/lib/verkiesing/wyksoeker";

/**
 * The hero's ward finder — the box a voter actually types into.
 *
 * Three rules shape this component:
 *  1. **No Afrikaans here.** Every visible string comes from `KOPIE`; `{n}` / `{q}`
 *     placeholders in those slots are filled by `vulIn`.
 *  2. **Coordinates are personal data.** The geolocation flow holds a point in a local
 *     variable for exactly one request. It is never put in state, in storage, in a log
 *     line, or in a URL the browser keeps — `router.push` only ever receives `/wyk/<id>`.
 *  3. **Keyboard first.** The ARIA combobox pattern: arrows move, Enter follows, Escape
 *     closes and then clears, and a polite live region reports the result count.
 */

/** Substitutes `{n}` / `{q}` placeholders in a copy slot. Unknown keys are left alone. */
export function vulIn(sjabloon: string, waardes: Record<string, string | number>): string {
  return sjabloon.replace(/\{(\w+)\}/g, (heel, sleutel: string) =>
    sleutel in waardes ? String(waardes[sleutel]) : heel
  );
}

type LiggingStatus = "rustig" | "besig" | "geweier" | "buite";

/**
 * One keyboard-reachable option. A place that spans several wards has no single target, so
 * activating it expands into one `wyk` option per ward — that way the arrow keys reach the
 * chooser strip the design shows, without putting buttons inside a listbox.
 */
type Opsie =
  | { soort: "ry"; indeks: number; ryIndeks: number; ry: SoekRy }
  | { soort: "wyk"; indeks: number; ryIndeks: number; wykId: string; wykNr: number };

const ONTDOP_MS = 250;
const MIN_KARAKTERS = 2;

/**
 * The mockup's outline `.knop`, plus `min-h-11` — the mockup draws it 32 px high, which is
 * below a thumb-sized target, so the code overrides the design here (the house idiom is
 * already in `ovk-aksies.tsx`).
 */
const KNOPPIE =
  "border-rand text-ink inline-flex min-h-11 items-center gap-2 rounded border px-4 py-2 font-sans text-xs font-bold tracking-widest uppercase hover:border-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi disabled:text-grys";

function SoekIkoon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      className="text-ink shrink-0"
      aria-hidden
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5" />
    </svg>
  );
}

function LiggingIkoon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" />
      <circle cx="12" cy="12" r="7" />
    </svg>
  );
}

function PylIkoon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-grys shrink-0"
      aria-hidden
    >
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

/** The busy button's ring. `motion-reduce` stops it spinning for a reader who asked it to. */
function Wieletjie() {
  return (
    <span
      aria-hidden
      className="border-rand border-t-ink inline-block size-3.5 animate-spin rounded-full border-2 motion-reduce:animate-none"
    />
  );
}

/**
 * A two-line notice: the statement in ink, the advice in grey. The copy slot carries both
 * lines separated by a newline; a single-line value renders as the statement only.
 */
function Boodskap({ teks }: { teks: string }) {
  const [eerste, ...res] = teks.split("\n");
  return (
    <div className="border-rand bg-paneel border px-3.5 py-3">
      <p className="text-ink font-sans text-[0.9375rem]">{eerste}</p>
      {res.length > 0 && <p className="text-grys mt-1 font-sans text-sm">{res.join(" ")}</p>}
    </div>
  );
}

export function WykSoeker() {
  const router = useRouter();
  const minBeweging = useReducedMotion();
  const idBasis = useId();
  const titelId = `${idBasis}-titel`;
  const lysId = `${idBasis}-lys`;
  const houer = useRef<HTMLDivElement>(null);
  /** The query the box is on right now, readable from inside an in-flight request. */
  const jongsteQ = useRef("");

  const [navraag, setNavraag] = useState("");
  /** The last answer we got, tagged with the query it answers. */
  const [uitslag, setUitslag] = useState<{ q: string; rye: SoekRy[] } | null>(null);
  const [oop, setOop] = useState(false);
  const [aktief, setAktief] = useState(-1);
  const [uitgebrei, setUitgebrei] = useState<number | null>(null);
  const [ligging, setLigging] = useState<LiggingStatus>("rustig");

  const q = navraag.trim();
  // Results are keyed by their query, so a response that arrives after the box has moved
  // on is simply not the current answer and is never rendered.
  const rye = uitslag && uitslag.q === q ? uitslag.rye : null;
  const wysLys = oop && rye !== null && rye.length > 0;
  const geenResultate = rye !== null && rye.length === 0 && q.length >= MIN_KARAKTERS;

  const { opsies, indeksVanRy, indeksVanWyk } = useMemo(() => {
    const opsies: Opsie[] = [];
    const indeksVanRy = new Map<number, number>();
    const indeksVanWyk = new Map<string, number>();
    (rye ?? []).forEach((ry, ryIndeks) => {
      indeksVanRy.set(ryIndeks, opsies.length);
      opsies.push({ soort: "ry", indeks: opsies.length, ryIndeks, ry });
      if (ryIndeks !== uitgebrei) return;
      ry.wyk_ids.forEach((wykId, j) => {
        indeksVanWyk.set(`${ryIndeks}:${j}`, opsies.length);
        opsies.push({
          soort: "wyk",
          indeks: opsies.length,
          ryIndeks,
          wykId,
          wykNr: ry.wyk_nrs[j] ?? 0,
        });
      });
    });
    return { opsies, indeksVanRy, indeksVanWyk };
  }, [rye, uitgebrei]);

  // --- Search -------------------------------------------------------------
  useEffect(() => {
    jongsteQ.current = q;
    if (q.length < MIN_KARAKTERS) return;
    const afbreek = new AbortController();
    const tik = setTimeout(async () => {
      try {
        const res = await fetch(`/api/soek?q=${encodeURIComponent(q)}`, {
          signal: afbreek.signal,
        });
        const data = res.ok ? await res.json() : null;
        const gevind: SoekRy[] = Array.isArray(data?.resultate) ? data.resultate : [];
        // A slow answer for an older query must not even land in state: writing it would
        // make `uitslag.q` stale and close a popover that is showing the right rows.
        if (jongsteQ.current !== q) return;
        setUitslag({ q, rye: gevind });
      } catch {
        // Aborted (the reader typed on) or the network is gone. An empty result is the
        // honest answer for the second case; an abort must change nothing.
        if (!afbreek.signal.aborted && jongsteQ.current === q) setUitslag({ q, rye: [] });
      }
    }, ONTDOP_MS);
    return () => {
      clearTimeout(tik);
      afbreek.abort();
    };
  }, [q]);

  // Keep the active option visible once the list is tall enough to scroll.
  useEffect(() => {
    if (!wysLys || aktief < 0) return;
    const el = document.getElementById(`${idBasis}-o${aktief}`);
    // jsdom has no layout, so `scrollIntoView` may simply not exist there.
    el?.scrollIntoView?.({ block: "nearest" });
  }, [aktief, wysLys, idBasis]);

  // Clicking away closes the popover, the way a native combobox behaves.
  useEffect(() => {
    if (!wysLys) return;
    const opBuiteKlik = (e: MouseEvent) => {
      if (houer.current && !houer.current.contains(e.target as Node)) setOop(false);
    };
    document.addEventListener("mousedown", opBuiteKlik);
    return () => document.removeEventListener("mousedown", opBuiteKlik);
  }, [wysLys]);

  // --- Activation ---------------------------------------------------------
  function aktiveer(indeks: number) {
    const o = opsies[indeks];
    if (!o) return;
    if (o.soort === "wyk") {
      setOop(false);
      router.push(`/wyk/${o.wykId}`);
      return;
    }
    if (o.ry.teiken) {
      setOop(false);
      router.push(`/wyk/${o.ry.teiken}`);
      return;
    }
    // A place spanning several wards has nowhere of its own to go: open its chooser and
    // put the cursor on the first ward. Only one row is ever expanded, so the first ward
    // of row `n` sits at option index `n + 1`.
    if (o.ryIndeks === uitgebrei) {
      setUitgebrei(null);
      setAktief(o.ryIndeks);
    } else {
      setUitgebrei(o.ryIndeks);
      setAktief(o.ryIndeks + 1);
    }
  }

  function opSleutel(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (opsies.length === 0) return;
      setOop(true);
      setAktief((a) => (a + 1) % opsies.length);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (opsies.length === 0) return;
      setOop(true);
      setAktief((a) => (a <= 0 ? opsies.length - 1 : a - 1));
      return;
    }
    if (e.key === "Home" && wysLys) {
      e.preventDefault();
      setAktief(0);
      return;
    }
    if (e.key === "End" && wysLys) {
      e.preventDefault();
      setAktief(opsies.length - 1);
      return;
    }
    if (e.key === "Enter") {
      if (!wysLys) return;
      e.preventDefault();
      aktiveer(aktief >= 0 ? aktief : 0);
      return;
    }
    if (e.key === "Escape") {
      // A search input clears itself on Escape in some browsers; we own that behaviour.
      e.preventDefault();
      if (wysLys) {
        setOop(false);
        setAktief(-1);
        setUitgebrei(null);
        return;
      }
      setNavraag("");
      setUitslag(null);
      setLigging("rustig");
    }
  }

  // --- Location -----------------------------------------------------------
  async function wykByPunt(lat: number, lng: number) {
    try {
      // POST, so the point never rides in a URL the platform would log.
      const res = await fetch("/api/wyk-by-punt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lng }),
        cache: "no-store",
      });
      const data = res.ok ? await res.json() : null;
      const wykId: string | undefined = data?.wyk?.wyk_id;
      if (wykId) {
        setLigging("rustig");
        router.push(`/wyk/${wykId}`);
        return;
      }
      setLigging("buite");
    } catch {
      // Deliberately no error detail: a thrown fetch error carries the request URL, and
      // that URL carries the coordinates.
      setLigging("geweier");
    }
  }

  function gebruikMyLigging() {
    const geo = typeof navigator === "undefined" ? undefined : navigator.geolocation;
    if (!geo) {
      setLigging("geweier");
      return;
    }
    setOop(false);
    setLigging("besig");
    geo.getCurrentPosition(
      (pos) => {
        // The point lives only in these two locals, for exactly one request.
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        void wykByPunt(lat, lng);
      },
      () => setLigging("geweier"),
      { timeout: 8000, enableHighAccuracy: false }
    );
  }

  // --- Derived copy -------------------------------------------------------
  const boodskap =
    ligging === "geweier"
      ? KOPIE.soek_ligging_geweier
      : ligging === "buite"
        ? KOPIE.soek_ligging_buite
        : geenResultate
          ? vulIn(KOPIE.soek_geen, { q })
          : null;

  const aantal = rye?.length ?? 0;
  const telling =
    aantal === 1
      ? vulIn(KOPIE.soek_resultate_telling_een, { n: 1, q })
      : vulIn(KOPIE.soek_resultate_telling, { n: aantal, q });
  const aankondiging = wysLys ? telling : boodskap ? boodskap.split("\n").join(" ") : "";

  const genommer = (rye ?? []).map((ry, i) => ({ ry, i }));
  const groepe = [
    { etiket: KOPIE.soek_groep_plekke, items: genommer.filter((x) => x.ry.soort === "plek") },
    {
      etiket: KOPIE.soek_groep_stemlokale,
      items: genommer.filter((x) => x.ry.soort === "stemlokaal"),
    },
  ].filter((g) => g.items.length > 0);

  /** "Stad Tshwane · Gauteng" for a place, "Stad Tshwane · 279 Murray Street" for a
   * station — and just the municipality for a station whose address is empty. */
  const onderskrif = (ry: SoekRy) =>
    [ry.muni_naam, ry.soort === "stemlokaal" ? ry.adres : ry.provinsie]
      .filter(Boolean)
      .join(" · ");

  const kenteken = (ry: SoekRy) =>
    ry.wyk_nrs.length === 1
      ? vulIn(KOPIE.soek_wyk_nommer, { n: ry.wyk_nrs[0] })
      : vulIn(KOPIE.soek_wyk_aantal, { n: ry.wyk_nrs.length });

  const rytjie = (indeks: number) =>
    `flex w-full cursor-pointer items-center gap-3 px-3.5 py-2.5 text-left ${
      aktief === indeks ? "bg-[#f4f4f5]" : "bg-grond"
    }`;

  return (
    <div
      id="vind-jou-wyk"
      ref={houer}
      className="neon-raam-dun relative z-10 flex scroll-mt-24 flex-col gap-3.5 p-5 sm:p-6"
    >
      <div>
        <p className="text-ink font-sans text-xs font-bold tracking-[0.22em] uppercase">
          {KOPIE.soek_etiket}
        </p>
        <p id={titelId} className="text-ink mt-2 font-display text-2xl leading-tight text-balance">
          {KOPIE.soek_titel}
        </p>
      </div>

      <div className="relative">
        {/* The ring lives on the wrapper, so it frames the whole field including the
            icon rather than just the text area. */}
        <div className="border-ink flex h-12 items-center gap-2.5 border-2 px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-rooi">
          <SoekIkoon />
          <input
            type="search"
            role="combobox"
            aria-labelledby={titelId}
            aria-expanded={wysLys}
            aria-autocomplete="list"
            {...(wysLys ? { "aria-controls": lysId } : {})}
            {...(aktief >= 0 && wysLys
              ? { "aria-activedescendant": `${idBasis}-o${aktief}` }
              : {})}
            autoComplete="off"
            spellCheck={false}
            placeholder={KOPIE.soek_plekhouer}
            value={navraag}
            onChange={(e) => {
              setNavraag(e.target.value);
              setAktief(-1);
              setUitgebrei(null);
              setOop(true);
              setLigging("rustig");
            }}
            onKeyDown={opSleutel}
            className="text-ink placeholder:text-grys h-full w-full min-w-0 bg-transparent font-sans text-[1.0625rem] focus:outline-none [&::-webkit-search-cancel-button]:hidden"
          />
        </div>

        {wysLys && (
          <motion.div
            id={lysId}
            role="listbox"
            aria-labelledby={titelId}
            initial={minBeweging ? false : { opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={minBeweging ? { duration: 0 } : { duration: 0.16, ease: [0.4, 0, 0.2, 1] }}
            className="border-ink bg-grond static z-20 mt-3.5 max-h-[min(60vh,26rem)] w-full overflow-y-auto border pb-2 shadow-[0_12px_32px_rgba(11,13,16,0.10)] sm:absolute sm:top-full sm:left-0 sm:mt-2"
          >
            <p
              aria-hidden
              className="border-rand text-grys border-b px-3.5 py-2.5 font-sans text-[0.8125rem]"
            >
              {telling}
            </p>
            {groepe.map((g, gi) => (
              <div
                key={g.etiket}
                role="group"
                aria-label={g.etiket}
                className={gi > 0 ? "border-rand border-t" : undefined}
              >
                <p
                  aria-hidden
                  className="text-grys px-3.5 pt-3 pb-1.5 font-sans text-[0.6875rem] font-bold tracking-[0.2em] uppercase"
                >
                  {g.etiket}
                </p>
                {g.items.map(({ ry, i }) => {
                  const indeks = indeksVanRy.get(i) ?? 0;
                  return (
                    <div key={i} role="presentation">
                      <div
                        id={`${idBasis}-o${indeks}`}
                        role="option"
                        aria-selected={aktief === indeks}
                        onMouseEnter={() => setAktief(indeks)}
                        onClick={() => aktiveer(indeks)}
                        className={rytjie(indeks)}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="text-ink block font-sans text-base font-bold">
                            {ry.etiket}
                          </span>
                          <span className="text-grys block font-sans text-sm">
                            {onderskrif(ry)}
                          </span>
                        </span>
                        <span className="text-ink font-sans text-[0.8125rem] font-bold whitespace-nowrap">
                          {kenteken(ry)}
                        </span>
                        <PylIkoon />
                      </div>
                      {uitgebrei === i && (
                        <div className="flex flex-col gap-2 bg-[#f4f4f5] px-3.5 pt-0.5 pb-3">
                          <p className="text-grys font-sans text-[0.8125rem]">
                            {vulIn(KOPIE.soek_wyke_kies, { n: ry.wyk_ids.length, q: ry.etiket })}
                          </p>
                          <div role="presentation" className="flex flex-wrap gap-2">
                            {ry.wyk_ids.map((wykId, j) => {
                              const wIndeks = indeksVanWyk.get(`${i}:${j}`) ?? 0;
                              return (
                                <span
                                  key={wykId}
                                  id={`${idBasis}-o${wIndeks}`}
                                  role="option"
                                  aria-selected={aktief === wIndeks}
                                  onMouseEnter={() => setAktief(wIndeks)}
                                  onClick={() => aktiveer(wIndeks)}
                                  className={`${KNOPPIE} border-ink cursor-pointer ${
                                    aktief === wIndeks ? "bg-ink text-white" : "bg-grond"
                                  }`}
                                >
                                  {vulIn(KOPIE.soek_wyk_nommer, { n: ry.wyk_nrs[j] ?? 0 })}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </motion.div>
        )}
      </div>

      {/* One always-mounted polite region, so a count or a notice is announced even though
          the popover and the notice panel mount and unmount. */}
      <p role="status" aria-live="polite" className="sr-only">
        {aankondiging}
      </p>

      {/* No `aria-live` here: the sr-only region above already announces the notice, and
          two live regions would read it twice. */}
      <div>{boodskap && <Boodskap teks={boodskap} />}</div>

      <div className="flex flex-col items-start gap-3">
        <button
          type="button"
          onClick={gebruikMyLigging}
          disabled={ligging === "besig"}
          className={KNOPPIE}
        >
          {ligging === "besig" ? <Wieletjie /> : <LiggingIkoon />}
          <span>
            {ligging === "besig" ? KOPIE.soek_ligging_besig : KOPIE.soek_ligging_knoppie}
          </span>
        </button>
        {!boodskap && (
          <p className="text-grys inline-flex min-h-11 items-center font-sans text-sm">
            {KOPIE.soek_registrasie_skakel}{" "}
            <a
              href="#registrasie"
              className="text-ink decoration-rand ml-1 inline-flex min-h-11 items-center font-bold underline underline-offset-4 hover:text-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
            >
              {KOPIE.held_boks_skakel} ↓
            </a>
          </p>
        )}
      </div>
    </div>
  );
}
