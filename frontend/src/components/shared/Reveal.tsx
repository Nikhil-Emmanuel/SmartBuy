/**
 * Reveal content as it scrolls into view.
 *
 * `once: true` is not optional: a section that re-animates every time it
 * crosses the fold turns scrolling back up into a light show, and re-reading
 * something you already read should not cost you 300ms.
 *
 * The `-80px` margin fires the animation slightly before the element reaches
 * the viewport, so by the time it is genuinely visible it has already settled
 * -- the motion should be something you catch out of the corner of your eye,
 * not something you wait on.
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { EASE_OUT, useReducedMotion } from "@/lib/motion";

export function Reveal({
  children,
  delay = 0,
  y = 18,
  className,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, ease: EASE_OUT, delay }}
    >
      {children}
    </motion.div>
  );
}
