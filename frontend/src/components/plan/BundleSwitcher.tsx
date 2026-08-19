import { Check } from "lucide-react";

import { percent, presetLabel, rupees } from "@/lib/format";
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
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {bundles.map((bundle) => {
        const isActive = bundle.preset === active;
        const isSelected = bundle.preset === selected;
        return (
          <button
            key={bundle.preset}
            onClick={() => onSelect(bundle.preset)}
            className={cn(
              "relative rounded-xl border p-4 text-left transition-all",
              isActive
                ? "border-primary bg-primary-soft/60 shadow-sm"
                : "border-border bg-card hover:border-primary/40",
            )}
          >
            {isSelected && (
              <span className="absolute right-3 top-3 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Check className="size-3" />
              </span>
            )}
            <p className="text-sm font-semibold text-foreground">{presetLabel(bundle.preset)}</p>
            <p className="mb-3 text-[11px] text-muted-foreground">{PRESET_HINT[bundle.preset]}</p>
            <p className="tabular text-xl font-semibold text-foreground">
              {rupees(bundle.total_cost)}
            </p>
            <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Saved <span className="tabular font-medium text-savings">{rupees(bundle.total_savings)}</span>
              </span>
              <span>{percent(bundle.requirement_coverage)} covered</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
