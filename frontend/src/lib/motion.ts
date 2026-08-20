/**
 * Shared motion vocabulary.
 *
 * One file so that everything on screen accelerates the same way. The values
 * are not arbitrary: durations sit in the 150-300ms band where motion reads as
 * responsive rather than slow, and every entrance uses the same decelerating
 * curve so elements feel like they are settling into place instead of being
 * flung there.
 *
 * Motion here is only ever allowed to carry meaning -- where something came
 * from, that a number is being counted, that a choice moved. Decoration that
 * costs the user time is the anti-pattern this file exists to avoid.
 *
 * Every consumer must honour `prefers-reduced-motion`. Framer Motion's
 * `useReducedMotion()` is the hook for that; `index.css` already flattens CSS
 * animations, but JS-driven motion has to opt in for itself.
 */

import type { Transition, Variants } from "framer-motion";

/** Decelerating ease, matched to the `--animate-*` curves in index.css. */
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/** For things that settle: cards landing, selections moving. */
export const SPRING: Transition = {
  type: "spring",
  stiffness: 320,
  damping: 30,
  mass: 0.8,
};

/** High-energy spring physics for tactile micro-interactions and button feedback. */
export const SPRING_BOUNCE: Transition = {
  type: "spring",
  stiffness: 420,
  damping: 22,
  mass: 0.6,
};

/** Quick snappy spring for modals, popups, and instant feedback. */
export const SPRING_SNAPPY: Transition = {
  type: "spring",
  stiffness: 450,
  damping: 32,
};

/** For things that simply appear. */
export const FADE: Transition = { duration: 0.28, ease: EASE_OUT };

/**
 * Stagger a list in. Capped deliberately: with `each: 0.04` a 40-product grid
 * would take 1.6s to finish arriving, and a user who scrolled straight to the
 * bottom would be watching an empty screen. `staggerChildren` applies to the
 * whole list, so the cap belongs on the list length, not the step.
 */
export function listParent(count: number): Variants {
  return {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: count > 12 ? 0.02 : 0.04,
        delayChildren: 0.02,
      },
    },
  };
}

export const listChild: Variants = {
  hidden: { opacity: 0, y: 16, scale: 0.96 },
  visible: { opacity: 1, y: 0, scale: 1, transition: SPRING },
};

/** Product Grid Card reveal variant with soft layout scale. */
export const CARD_REVEAL: Variants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: { opacity: 1, y: 0, scale: 1, transition: SPRING },
};

/** Scale-in transition for popups and dialog overlays. */
export const SCALE_IN: Variants = {
  hidden: { opacity: 0, scale: 0.95, y: 8 },
  visible: { opacity: 1, scale: 1, y: 0, transition: SPRING_SNAPPY },
  exit: { opacity: 0, scale: 0.96, y: 4, transition: { duration: 0.15, ease: "easeIn" } },
};

/** Standard tactile press feedback scale factor. */
export const TAP_SCALE = { scale: 0.94 } as const;

/** Panels and sheets that arrive from below. */
export const rise: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: FADE },
};

/**
 * Route-level transition.
 *
 * Deliberately quicker and shallower than a list entrance: a whole page
 * sliding is the difference between "responsive" and "waiting for an
 * animation to finish before I can read". Exit is faster than enter, because
 * the user has already decided to leave.
 */
export const pageEnter: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.22, ease: EASE_OUT } },
  exit: { opacity: 0, y: -6, transition: { duration: 0.14, ease: "easeIn" } },
};

/**
 * Hover lift shared by every card that is also a link. One value so a card
 * does not rise further on one page than another.
 */
export const HOVER_LIFT = { y: -5, transition: SPRING_BOUNCE } as const;
