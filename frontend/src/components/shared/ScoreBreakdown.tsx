import { percent, scoreLabel } from "@/lib/format";
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

/** The Page 7 scorecard: eight normalized components plus the final blend. */
export function ScoreBreakdown({
  breakdown,
  className,
  compact = false,
}: {
  breakdown: ScoreBreakdownType;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div className={cn("space-y-2.5", className)}>
      {COMPONENT_ORDER.map((key) => {
        const value = breakdown[key];
        return (
          <div key={key} className="flex items-center gap-3">
            <span
              className={cn(
                "shrink-0 text-muted-foreground",
                compact ? "w-28 text-[11px]" : "w-32 text-xs",
              )}
            >
              {scoreLabel(key)}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full transition-all duration-500", barColor(value))}
                style={{ width: `${Math.round(value * 100)}%` }}
              />
            </div>
            <span className={cn("tabular shrink-0 text-right font-medium", compact ? "w-9 text-[11px]" : "w-10 text-xs")}>
              {percent(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function FinalScoreRing({ value, size = 56 }: { value: number; size?: number }) {
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value);

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
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-xs font-semibold tabular">
        {percent(value)}
      </div>
    </div>
  );
}
