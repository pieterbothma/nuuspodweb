"use client";

import { usePathname } from "next/navigation";
import { useState, useTransition } from "react";
import { stuurTerugvoer } from "@/app/aksies";

const KNOPPIE =
  "border-rand text-ink rounded border px-4 py-2 font-sans text-xs font-bold tracking-widest uppercase hover:border-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi disabled:opacity-50";

export function Terugvoer() {
  const pad = usePathname();
  const [gestuur, setGestuur] = useState(false);
  const [besig, begin] = useTransition();

  if (gestuur) {
    return (
      <p role="status" className="text-grys font-sans text-sm">
        Dankie, dit help ons om die bladsy beter te maak.
      </p>
    );
  }

  const stuur = (gevind: boolean) =>
    begin(async () => {
      try {
        await stuurTerugvoer(pad, gevind);
      } catch (err) {
        // A network hiccup shouldn't block the "Dankie" state from showing — the click still
        // registered from the reader's point of view, so fail soft rather than throw.
        console.error("[verkiesing] terugvoer misluk:", err);
      }
      setGestuur(true);
    });

  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-ink font-sans text-sm">Het jy gekry wat jy soek?</p>
      <button type="button" disabled={besig} onClick={() => stuur(true)} className={KNOPPIE}>
        Ja
      </button>
      <button type="button" disabled={besig} onClick={() => stuur(false)} className={KNOPPIE}>
        Nee
      </button>
    </div>
  );
}
