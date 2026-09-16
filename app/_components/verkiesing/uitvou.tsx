import type { ReactNode } from "react";
import { KOPIE } from "@/lib/verkiesing/kopie";

/**
 * Lists longer than this sit behind one button (Piet, 2026-09-16: on a phone the ward page
 * was an endless scroll). Shorter lists stay open — a button in front of three rows costs a
 * tap and saves nothing.
 */
export const UITVOU_DREMPEL = 5;

/**
 * A long list folded behind a full-width button. The WHOLE list folds, never its tail: a
 * "first five, then more" preview would put the alphabetically-early parties in front of
 * everyone else. `<details>` keeps it server-rendered with no client JavaScript, and the
 * content stays in the HTML for search engines and find-in-page.
 *
 * The group is named (`group/uitvou`) so the party lists' own `<details>` inside a ballot
 * keep their unnamed `group-open:` arrows to themselves. The focus ring is ink, not red:
 * this also sits inside the ballot blocks, where no red is allowed.
 *
 * `binne` draws the button as a row inside a bordered block (top hairline only) instead of
 * as a free-standing bordered button.
 */
export function Uitvou({
  naam,
  wys,
  aantal,
  binne = false,
  children,
}: {
  naam: string;
  wys: string;
  aantal: number;
  binne?: boolean;
  children: ReactNode;
}) {
  if (aantal <= UITVOU_DREMPEL) return <>{children}</>;
  const raam = binne ? "border-rand border-t px-5 sm:px-6" : "border-rand border px-4";
  return (
    <details data-uitvou={naam} className="group/uitvou">
      <summary
        className={`${raam} text-ink hover:bg-paneel flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 font-sans text-xs font-bold tracking-widest uppercase [&::-webkit-details-marker]:hidden focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink`}
      >
        <span className="group-open/uitvou:hidden">{wys}</span>
        <span className="hidden group-open/uitvou:inline">{KOPIE.uitvou_versteek}</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
          className="shrink-0 group-open/uitvou:-rotate-180"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </summary>
      {children}
    </details>
  );
}
