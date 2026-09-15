"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { aftelling } from "@/lib/verkiesing/datums";

/** Server passes its own clock so the first client render matches the HTML exactly. */
export function Aftelling({ teikenIso, nouMs }: { teikenIso: string; nouMs: number }) {
  const [nou, setNou] = useState(nouMs);
  const min = useReducedMotion();

  useEffect(() => {
    // Resync to the client's actual clock right after mount (the server value can be
    // seconds stale by the time hydration runs), then tick every 15s. The setTimeout(0)
    // keeps this out of the synchronous effect body so it doesn't trigger cascading renders.
    const tik = () => setNou(Date.now());
    const eerste = setTimeout(tik, 0);
    const t = setInterval(tik, 15_000);
    return () => {
      clearTimeout(eerste);
      clearInterval(t);
    };
  }, []);

  const a = aftelling(new Date(nou), new Date(teikenIso));
  if (a.verby) {
    return <p className="text-ink font-display text-4xl">Stemdag is Woensdag 4 November.</p>;
  }

  const dele = [
    { waarde: a.dae, etiket: a.dae === 1 ? "dag" : "dae" },
    { waarde: a.ure, etiket: "uur" },
    { waarde: a.minute, etiket: a.minute === 1 ? "minuut" : "minute" },
  ];

  return (
    <div role="timer" aria-label={`Nog ${a.dae} dae, ${a.ure} uur en ${a.minute} minute tot stemdag`} className="flex gap-6 sm:gap-10">
      {dele.map((d, i) => (
        <div key={i} className="flex flex-col" aria-hidden>
          <span className="text-ink relative block overflow-hidden font-display text-5xl leading-none tabular-nums sm:text-7xl">
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={d.waarde}
                className="block"
                initial={min ? false : { y: "55%", opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={min ? { opacity: 0 } : { y: "-55%", opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              >
                {d.waarde}
              </motion.span>
            </AnimatePresence>
          </span>
          <span className="text-grys mt-2 font-sans text-xs font-bold tracking-[0.2em] uppercase">{d.etiket}</span>
        </div>
      ))}
    </div>
  );
}
