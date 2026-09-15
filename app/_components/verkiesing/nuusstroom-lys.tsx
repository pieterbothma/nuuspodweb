"use client";

import { useId, useLayoutEffect, useRef, useState } from "react";
import { KOPIE } from "@/lib/verkiesing/kopie";

export interface StroomPos {
  id: number;
  titel: string;
  bron: string;
  bronTipe: string;
  afkorting: string;
  tyd: string;
  iso: string;
  url: string;
}

const SIGBAAR = 5;

/** Twitter/X-style timeline: the newest SIGBAAR posts show, the rest fold behind "Wys meer". */
export function NuusstroomLys({ items }: { items: StroomPos[] }) {
  const [oop, setOop] = useState(false);
  const listId = useId();
  const knopRef = useRef<HTMLButtonElement>(null);
  const eersteRender = useRef(true);

  useLayoutEffect(() => {
    if (eersteRender.current) {
      eersteRender.current = false;
      return;
    }
    if (oop) return; // only guard against being stranded when we just collapsed
    const knop = knopRef.current;
    if (!knop) return;
    const rect = knop.getBoundingClientRect();
    const inView = rect.bottom > 0 && rect.top < window.innerHeight;
    if (!inView) {
      document.getElementById("stroom-kop")?.scrollIntoView({ block: "nearest" });
    }
  }, [oop]);

  if (items.length === 0) {
    return <p className="text-grys mt-4 font-sans text-sm">{KOPIE.stroom_leeg}</p>;
  }

  const sigbare = items.slice(0, oop ? items.length : SIGBAAR);
  const oorblywend = items.length - SIGBAAR;

  return (
    <div className="mt-4">
      <ol id={listId} className="border-rand bg-grond divide-rand divide-y border">
        {sigbare.map((i) => (
          <li key={i.id}>
            <a
              href={i.url}
              target="_blank"
              rel="noopener"
              className="group grid grid-cols-[2.5rem_minmax(0,1fr)] gap-3 p-4 transition-colors hover:bg-paneel focus-visible:outline-2 focus-visible:outline-rooi"
            >
              <span
                aria-hidden
                className="text-ink border-rand bg-paneel grid size-10 place-items-center rounded-full border font-sans text-[0.7rem] font-bold tracking-wide"
              >
                {i.afkorting}
              </span>
              <span className="min-w-0">
                <span className="flex flex-wrap items-baseline gap-x-1.5 text-sm">
                  <span className="text-ink font-bold">{i.bron}</span>
                  <span className="text-grys">{i.bronTipe}</span>
                  <span aria-hidden className="text-grys">·</span>
                  <time dateTime={i.iso} className="text-grys tabular-nums">
                    {i.tyd}
                  </time>
                </span>
                <span className="text-ink group-hover:text-rooi mt-1 block font-sans text-[0.975rem] leading-snug break-words">
                  {i.titel}
                </span>
                <span className="text-grys group-hover:text-rooi mt-2 inline-flex items-center gap-1 font-sans text-xs font-bold tracking-wide">
                  {KOPIE.stroom_lees_by} {i.bron}
                  <span aria-hidden>↗</span>
                  <span className="sr-only"> (maak in &apos;n nuwe oortjie oop)</span>
                </span>
              </span>
            </a>
          </li>
        ))}
      </ol>
      {items.length > SIGBAAR && (
        <button
          ref={knopRef}
          type="button"
          onClick={() => setOop((v) => !v)}
          aria-expanded={oop}
          aria-controls={listId}
          className="border-rand text-ink mt-3 w-full border py-2.5 font-sans text-xs font-bold tracking-widest uppercase hover:border-ink focus-visible:outline-2 focus-visible:outline-rooi"
        >
          {oop ? KOPIE.stroom_minder : `${KOPIE.stroom_meer} (${oorblywend})`}
        </button>
      )}
    </div>
  );
}
