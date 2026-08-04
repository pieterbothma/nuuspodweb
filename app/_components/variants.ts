import type { Variants } from "motion/react";

/** Smooth decelerate — used where something arrives and settles. */
const SAG = [0.16, 1, 0.3, 1] as const;
/** Standard ease — used for the shorter, more mechanical moves. */
const STANDAARD = [0.4, 0, 0.2, 1] as const;

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: SAG },
  },
};

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: STANDAARD },
  },
};

/**
 * The chyron's red tab, growing downward the way an on-air lower third does.
 * Anchored at the top so it reads as being drawn, not scaled.
 */
export const chyronTab: Variants = {
  hidden: { scaleY: 0 },
  visible: {
    scaleY: 1,
    transition: { duration: 0.32, ease: STANDAARD },
  },
};

/**
 * The heading wipe: text uncovered left to right behind a moving edge, which
 * is how a broadcast graphic reveals a name. A fade would say nothing about
 * the subject; this is the one place the page spends its motion budget.
 */
export const chyronWipe: Variants = {
  hidden: { clipPath: "inset(0 100% 0 0)" },
  visible: {
    clipPath: "inset(0 0% 0 0)",
    transition: { duration: 0.62, ease: SAG, delay: 0.16 },
  },
};

/** The kicker rides in just behind its tab. */
export const kickerIn: Variants = {
  hidden: { opacity: 0, x: -10 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.4, ease: STANDAARD, delay: 0.12 },
  },
};

/** Hairline rules that draw themselves, echoing the chyron tab. */
export const drawRule: Variants = {
  hidden: { scaleX: 0 },
  visible: {
    scaleX: 1,
    transition: { duration: 0.5, ease: SAG },
  },
};

export const EASE = { SAG, STANDAARD };
