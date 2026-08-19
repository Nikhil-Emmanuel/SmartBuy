/**
 * A number that counts to its value instead of snapping to it.
 *
 * Purely presentational, and deliberately so: the value it lands on is the
 * value it was handed. Nothing here rounds, estimates or derives money -- the
 * backend computes every total and this only paces how it is painted. If the
 * animation is skipped the rendered figure is identical.
 */

import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export function CountUp({
  value,
  format,
  duration = 0.7,
  className,
}: {
  value: number;
  format: (value: number) => string;
  duration?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(value);
  const previous = useRef(value);

  useEffect(() => {
    const from = previous.current;
    previous.current = value;

    if (reduced || from === value) {
      setShown(value);
      return;
    }

    const controls = animate(from, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setShown(latest),
      // Guarantee the exact figure at the end: easing arithmetic must never be
      // what decides the last rupee of a price.
      onComplete: () => setShown(value),
    });
    return () => controls.stop();
  }, [value, duration, reduced]);

  return (
    <span className={cn("tabular", className)}>{format(shown)}</span>
  );
}
