"use client";

import { motion, useReducedMotion } from "motion/react";
import {
  chyronTab,
  chyronWipe,
  drawRule,
  EASE,
  fadeInUp,
  kickerIn,
  staggerContainer,
  staggerItem,
} from "./variants";

const KYK_EEN_KEER = { once: true, amount: 0.25 } as const;

/**
 * The on-air lower third, animated the way the real graphic behaves: the tab
 * draws down, the kicker slides in behind it, then the heading is uncovered
 * left to right.
 */
export function Chyron({
  kicker,
  children,
  donker = true,
}: {
  kicker: string;
  children: React.ReactNode;
  /** False on the newsprint block, where the kicker takes the darker cyan. */
  donker?: boolean;
}) {
  const min = useReducedMotion();

  return (
    <motion.div
      className="mb-8 sm:mb-12"
      initial={min ? undefined : "hidden"}
      whileInView="visible"
      viewport={KYK_EEN_KEER}
    >
      <div className="flex items-center gap-3">
        <motion.span
          className="h-5 w-1 origin-top bg-rooi"
          variants={min ? undefined : chyronTab}
          aria-hidden
        />
        <motion.span
          className={`font-sans text-xs font-bold tracking-[0.22em] uppercase ${
            donker ? "text-siaan" : "text-[#0a6f88]"
          }`}
          variants={min ? undefined : kickerIn}
        >
          {kicker}
        </motion.span>
      </div>
      <motion.h2
        className={`mt-3 font-display text-3xl leading-tight sm:text-4xl md:text-5xl ${
          donker ? "text-papier" : "text-swart"
        }`}
        variants={min ? undefined : chyronWipe}
      >
        {children}
      </motion.h2>
    </motion.div>
  );
}

/** A plain scroll reveal, for blocks that should arrive without ceremony. */
export function Onthul({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const min = useReducedMotion();

  return (
    <motion.div
      className={className}
      variants={min ? undefined : fadeInUp}
      initial={min ? undefined : "hidden"}
      whileInView="visible"
      viewport={KYK_EEN_KEER}
      transition={min ? undefined : { delay }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerLys({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const min = useReducedMotion();

  return (
    <motion.div
      className={className}
      variants={min ? undefined : staggerContainer}
      initial={min ? undefined : "hidden"}
      whileInView="visible"
      viewport={KYK_EEN_KEER}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "li";
}) {
  const min = useReducedMotion();
  const Tag = as === "li" ? motion.li : motion.div;

  return (
    <Tag className={className} variants={min ? undefined : staggerItem}>
      {children}
    </Tag>
  );
}

/** A rule that draws itself from the left as it enters. */
export function TrekLyn({ className }: { className?: string }) {
  const min = useReducedMotion();

  return (
    <motion.div
      className={`origin-left ${className ?? ""}`}
      variants={min ? undefined : drawRule}
      initial={min ? undefined : "hidden"}
      whileInView="visible"
      viewport={KYK_EEN_KEER}
      aria-hidden
    />
  );
}

/**
 * One step of the hero's load sequence.
 *
 * The hero is the only thing that animates without being scrolled to, so it
 * runs as one orchestrated arrival rather than five separate effects.
 */
export function HeroStap({
  children,
  step,
  className,
}: {
  children: React.ReactNode;
  step: number;
  className?: string;
}) {
  const min = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={min ? undefined : { opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        min
          ? undefined
          : { duration: 0.7, delay: 0.08 + step * 0.11, ease: EASE.SAG }
      }
    >
      {children}
    </motion.div>
  );
}

/** The hero's pulse rule, which draws itself once the headline has landed. */
export function HeroPuls() {
  const min = useReducedMotion();

  return (
    <motion.div
      className="mt-6 h-1 w-40 origin-left bg-rooi"
      initial={min ? undefined : { scaleX: 0 }}
      animate={{ scaleX: 1 }}
      transition={min ? undefined : { duration: 0.55, delay: 0.4, ease: EASE.SAG }}
      aria-hidden
    >
      <div className="puls h-full w-full bg-siaan" />
    </motion.div>
  );
}
