/**
 * The ambient layer behind the landing hero: shopping marks drifting in the
 * background.
 *
 * Three rules this component is built around.
 *
 * 1. **Decorative means decorative.** It is `aria-hidden`, it never takes
 *    pointer events, and it sits behind everything. Nothing here is
 *    information, so nothing here is allowed to compete with information.
 * 2. **Reduced motion gets a still image, not a blank space.** The marks still
 *    render, they just stop moving. Removing them outright would change the
 *    composition for the people least able to opt back in.
 * 3. **The layout is deterministic.** Positions come from a seeded generator
 *    rather than `Math.random()`, so a re-render never reshuffles the field and
 *    the same build always looks the same in screenshots.
 */

import { motion, useReducedMotion, type MotionValue } from "framer-motion";
import {
  Gift,
  Package,
  Percent,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Tag,
  Truck,
} from "lucide-react";
import { useMemo } from "react";

const ICONS = [ShoppingBag, Tag, ShoppingCart, Package, Percent, Gift, Truck, Sparkles] as const;

const COUNT = 22;
const SEED = 20260820;

/** Linear congruential generator — small, deterministic, good enough for dust. */
function seeded(seed: number) {
  let state = seed;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}

interface Particle {
  Icon: (typeof ICONS)[number];
  left: number;
  top: number;
  size: number;
  opacity: number;
  duration: number;
  delay: number;
  rise: number;
  sway: number;
  spin: number;
  brass: boolean;
}

function buildField(): Particle[] {
  const random = seeded(SEED);
  return Array.from({ length: COUNT }, (_, i) => ({
    Icon: ICONS[i % ICONS.length],
    left: random() * 100,
    // Weighted toward the top: this sits behind the hero, and marks drifting
    // across the copy further down would be noise over the actual pitch.
    top: random() * 88,
    size: 15 + random() * 22,
    opacity: 0.05 + random() * 0.09,
    duration: 16 + random() * 15,
    delay: random() * 7,
    rise: 26 + random() * 46,
    sway: (random() - 0.5) * 34,
    spin: (random() - 0.5) * 26,
    // A third of the field picks up the brass accent so the layer carries the
    // palette's warm half rather than being a single flat hue.
    brass: random() < 0.34,
  }));
}

export function ShoppingParticles({ parallax }: { parallax?: MotionValue<number> }) {
  const reduced = useReducedMotion();
  const particles = useMemo(buildField, []);

  return (
    <motion.div
      aria-hidden
      style={reduced || !parallax ? undefined : { y: parallax }}
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden [mask-image:linear-gradient(to_bottom,#000_0%,#000_58%,transparent_92%)]"
    >
      {particles.map((particle, i) => {
        const { Icon } = particle;
        return (
          <motion.span
            key={i}
            className="absolute"
            style={{
              left: `${particle.left}%`,
              top: `${particle.top}%`,
              opacity: particle.opacity,
              color: particle.brass ? "var(--brass)" : "var(--primary)",
            }}
            animate={
              reduced
                ? undefined
                : {
                    y: [0, -particle.rise, 0],
                    x: [0, particle.sway, 0],
                    rotate: [0, particle.spin, 0],
                  }
            }
            transition={{
              duration: particle.duration,
              delay: particle.delay,
              repeat: Infinity,
              repeatType: "mirror",
              ease: "easeInOut",
            }}
          >
            <Icon style={{ width: particle.size, height: particle.size }} strokeWidth={1.4} />
          </motion.span>
        );
      })}
    </motion.div>
  );
}
