import type { Metadata } from "next";
import Link from "next/link";
import { KOPIE } from "@/lib/verkiesing/kopie";

/**
 * The site's own 404. Without this file a mistyped ward id or municipality code lands a
 * voter on Next's English default page — the wrong language and a dead end on a site whose
 * whole job is to get someone to their ward.
 *
 * Deliberately masthead-less: the page shell, one heading, one line, and the two links a
 * reader in this position actually wants. The 3 px neon rule is the only brand element, so
 * the page cannot be mistaken for a working section of the site.
 */
export const metadata: Metadata = {
  title: KOPIE.nie_gevind_titel,
  robots: { index: false, follow: true },
};

const KNOP =
  "border-rand text-ink hover:border-ink inline-flex min-h-11 items-center justify-center rounded border px-4 py-2 font-sans text-xs font-bold tracking-widest uppercase focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi";

export default function NieGevind() {
  return (
    <>
      <div className="h-[3px] bg-linear-to-r from-neon-siaan to-neon-rooi" aria-hidden />
      <main className="mx-auto max-w-2xl px-5 pt-16 pb-20 sm:px-8 sm:pt-24">
        <h1 className="text-ink font-display text-[2.75rem] leading-[0.95] tracking-[-0.02em] text-balance sm:text-6xl">
          {KOPIE.nie_gevind_opskrif}
        </h1>
        <p className="text-grys mt-5 font-sans text-[1.0625rem] leading-relaxed sm:text-lg">
          {KOPIE.nie_gevind_teks}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/" className={KNOP}>
            {KOPIE.nie_gevind_tuis}
          </Link>
          <Link href="/#vind-jou-wyk" className={KNOP}>
            {KOPIE.nie_gevind_soek}
          </Link>
        </div>
      </main>
    </>
  );
}
