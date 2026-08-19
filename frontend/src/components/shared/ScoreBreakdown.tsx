import { motion, useReducedMotion } from "framer-motion";

import { CountUp } from "@/components/shared/CountUp";
import { percent, scoreLabel } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { ScoreBreakdown as ScoreBreakdownType } from "@/types/api";

const COMPONENT_ORDER: (keyof ScoreBreakdownType)[] = [
  "goal_suitability",
  "preference_match",
  "quality",
  "feature_match",
  "budget_fit",
  "review_strength",
  "delivery",
  "deal_value",
];

function barColor(value: number): string {
  if (value >= 0.75) return "bg-savings";
  if (value >= 0.5) return "bg-info";
  if (value >= 0.3) return "bg-caution";
  return "bg-danger";
}

/**
 * The Page 7 scorecard: eight normalized components plus the final blend.
 *
 * The bars grow from zero in reading order rather than appearing at full
 * length. This is the one screen whose whole job is to show *why* a product
 * won, and drawing the components one after another is what makes it read as
 * eight separate reasons instead of one decorative block.
 */
export function ScoreBreakdown({
  breakdown,
  className,
  compact = false,
}: {
  breakdown: ScoreBreakdownType;
  className?: string;
  compact?: boolean;
}) {
  const reduced = useReducedMotion();

  return (
    <div className={cn("space-y-2.5", className)}>
      {COMPONENT_ORDER.map((key, i) => {
        const value = breakdown[key];
        const width = `${Math.round(value * 100)}%`;
        return (
          <div key={key} className="group/row flex items-center gap-3">
            <span
              className={cn(
                "shrink-0 text-muted-foreground transition-colors group-hover/row:text-foreground",
                compact ? "w-28 text-[11px]" : "w-32 text-xs",
              )}
            >
              {scoreLabel(key)}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <motion.div
                className={cn("h-full rounded-full", barColor(value))}
                initial={reduced ? false : { width: 0 }}
                animate={{ width }}
                transition={{ duration: 0.55, ease: EASE_OUT, delay: reduced ? 0 : i * 0.05 }}
              />
            </div>
            <span
              className={cn(
                "tabular shrink-0 text-right font-medium",
                compact ? "w-9 text-[11px]" : "w-10 text-xs",
              )}
            >
              {percent(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function FinalScoreRing({ value, size = 56 }: { value: number; size?: number }) {
  const reduced = useReducedMotion();
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--muted)"
          strokeWidth={5}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={reduced ? false : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - value) }}
          transition={{ duration: 0.8, ease: EASE_OUT }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-xs font-semibold">
        <CountUp value={value} format={(v) => percent(v)} duration={0.8} />
      </div>
    </div>
  );
}
