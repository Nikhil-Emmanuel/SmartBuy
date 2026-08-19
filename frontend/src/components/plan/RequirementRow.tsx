import { Minus, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { rupees, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Requirement } from "@/types/api";

const PRIORITY_VARIANT: Record<string, "accent" | "info" | "outline"> = {
  essential: "accent",
  recommended: "info",
  optional: "outline",
};

export function RequirementRow({
  requirement,
  onToggleOwned,
  onQuantityChange,
  busy,
}: {
  requirement: Requirement;
  onToggleOwned?: (owned: boolean) => void;
  onQuantityChange?: (quantity: number) => void;
  busy?: boolean;
}) {
  const r = requirement;

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border border-border bg-card p-4 transition-opacity",
        r.is_owned && "opacity-60",
      )}
    >
      <Checkbox
        checked={r.is_owned}
        onCheckedChange={(checked) => onToggleOwned?.(Boolean(checked))}
        disabled={busy}
        className="mt-0.5"
      />

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4
            className={cn(
              "text-sm font-medium text-foreground",
              r.is_owned && "line-through decoration-muted-foreground",
            )}
          >
            {r.item_name}
          </h4>
          <Badge variant={PRIORITY_VARIANT[r.priority] ?? "outline"} className="capitalize">
            {r.priority}
          </Badge>
          {r.is_owned && (
            <Badge variant="savings" className="capitalize">
              Already owned
            </Badge>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{r.reason}</p>
        <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
          <span>
            Est. <span className="tabular font-medium text-foreground">{rupees(r.est_price_min)}</span>
            {" – "}
            <span className="tabular font-medium text-foreground">{rupees(r.est_price_max)}</span>
          </span>
          <span>{titleCase(r.category)}</span>
        </div>
      </div>

      {onQuantityChange && !r.is_owned && (
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => onQuantityChange(Math.max(1, r.quantity - 1))}
            disabled={busy || r.quantity <= 1}
            className="flex size-6 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-accent disabled:opacity-40"
          >
            <Minus className="size-3" />
          </button>
          <span className="tabular w-5 text-center text-sm font-medium">{r.quantity}</span>
          <button
            onClick={() => onQuantityChange(r.quantity + 1)}
            disabled={busy}
            className="flex size-6 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-accent disabled:opacity-40"
          >
            <Plus className="size-3" />
          </button>
        </div>
      )}
    </div>
  );
}
