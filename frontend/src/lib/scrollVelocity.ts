/**
 * Scroll-velocity-linked motion.
 *
 * The effect: elements don't just move *with* the scroll, they react to how
 * fast you're scrolling. Flick the page and the row bows and tilts; let it
 * settle and everything springs back to rest. Motion's own example calls this
 * a "velocity-linked wave".
 *
 * Built from Motion's documented `useVelocity` recipe rather than copied --
 * the source of their example sits behind Motion+. The documented mapping is
 * `useTransform(velocity, [-3000, 0, 3000], [...], { clamp: false })`, and the
 * spring is what stops raw velocity (which is spiky and noisy frame to frame)
 * from making the whole thing judder.
 *
 * `clamp: false` matters: a violent scroll should exceed the range and bend
 * things further, not flatten against a ceiling. The visual cost of clamping
 * is that every fast scroll looks identical.
 */

import {
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
  type MotionValue,
} from "framer-motion";

import { useReducedMotion } from "@/lib/motion";

/** Raw scroll velocity is jittery; this is what makes it feel like weight. */
const VELOCITY_SPRING = { damping: 50, stiffness: 400, restDelta: 0.001 };

/** Beyond this, scrolling is "as fast as it gets" for mapping purposes. */
const VELOCITY_RANGE = 3000;

/**
 * A signed factor: roughly -1 (fast scroll up) → 0 (still) → 1 (fast down),
 * unclamped so a hard flick overshoots.
 *
 * Returns a motion value pinned at 0 when the user has asked for reduced
 * motion, so callers can use it unconditionally -- hooks cannot be called
 * conditionally, and gating at the source keeps every consumer honest.
 */
export function useScrollVelocityFactor(): MotionValue<number> {
  const reduced = useReducedMotion();
  const { scrollY } = useScroll();
  const velocity = useVelocity(scrollY);
  const smooth = useSpring(velocity, VELOCITY_SPRING);

  return useTransform(
    smooth,
    [-VELOCITY_RANGE, 0, VELOCITY_RANGE],
    reduced ? [0, 0, 0] : [-1, 0, 1],
    { clamp: false },
  );
}

/**
 * Turn the shared factor into one element's offset.
 *
 * `phase` staggers neighbours so a row bends as a wave instead of moving as a
 * slab -- that difference is the entire effect.
 */
export function useVelocityOffset(
  factor: MotionValue<number>,
  phase: number,
  amplitude = 70,
): MotionValue<number> {
  return useTransform(factor, (v) => Math.sin(phase) * v * amplitude);
}

/** A slight 3D tilt, capped so the row never turns edge-on and unreadable. */
export function useVelocityTilt(
  factor: MotionValue<number>,
  phase: number,
  degrees = 14,
): MotionValue<number> {
  return useTransform(factor, (v) => {
    const raw = Math.cos(phase) * v * degrees;
    return Math.max(-degrees * 1.6, Math.min(degrees * 1.6, raw));
  });
}
