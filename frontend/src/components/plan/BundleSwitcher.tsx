import { motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";

import { CountUp } from "@/components/shared/CountUp";
import { percent, presetLabel, rupees } from "@/lib/format";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { Bundle, BundlePreset } from "@/types/api";

const PRESET_HINT: Record<BundlePreset, string> = {
  best_overall: "Best balance of quality and price",
  best_budget: "Lowest total cost",
  premium: "Highest quality within reach",
};

export function BundleSwitcher({
  bundles,
  active,
  selected,
  onSelect,
}: {
  bundles: Bundle[];
  active: BundlePreset;
  selected: BundlePreset | null;
  onSelect: (preset: BundlePreset) => void;
}) {
  const reduced = useReducedMotion();

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {bundles.map((bundle) => {
        const isActive = bundle.preset === active;
        const isSelected = bundle.preset === selected;
        return (
          <motion.button
            key={bundle.preset}
            onClick={() => onSelect(bundle.preset)}
            aria-pressed={isActive}
            whileHover={reduced ? undefined : { y: -3 }}
            whileTap={reduced ? undefined : { scale: 0.985 }}
            transition={SPRING}
            className={cn(
              "relative cursor-pointer rounded-xl border p-4 text-left transition-colors",
              isActive
                ? "border-primary bg-primary-soft/60"
                : "border-border bg-card hover:border-primary/40",
            )}
          >
            {/* One element shared across all three cards, so switching basket
                slides the highlight from the old choice to the new one. A
                highlight that teleports makes the user hunt for what changed. */}
            {isActive && (
              <motion.span
                layoutId="bundle-active"
                transition={SPRING}
                className="pointer-events-none absolute inset-0 rounded-xl ring-2 ring-primary"
              />
            )}
            {isSelected && (
              <motion.span
                initial={reduced ? false : { scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={SPRING}
                className="absolute right-3 top-3 z-10 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
              >
                <Check className="size-3" />
              </motion.span>
            )}
            <p className="text-sm font-semibold text-foreground">{presetLabel(bundle.preset)}</p>
            <p className="mb-3 text-[11px] text-muted-foreground">{PRESET_HINT[bundle.preset]}</p>
            <p className="text-xl font-semibold text-foreground">
              <CountUp value={bundle.total_cost} format={rupees} />
            </p>
            <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Saved{" "}
                <span className="font-medium text-savings">
                  <CountUp value={bundle.total_savings} format={rupees} />
                </span>
              </span>
              <span>{percent(bundle.requirement_coverage)} covered</span>
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
