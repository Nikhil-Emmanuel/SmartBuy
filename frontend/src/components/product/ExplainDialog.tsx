import { AlertTriangle } from "lucide-react";

import { FinalScoreRing, ScoreBreakdown } from "@/components/shared/ScoreBreakdown";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useExplain } from "@/hooks/useProducts";
import { points, rating, rupees, titleCase } from "@/lib/format";
import type { Product } from "@/types/api";

export function ExplainDialog({
  open,
  onOpenChange,
  product,
  requirementId,
  planId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: Product | null;
  requirementId: string | null;
  planId: string | null;
}) {
  const { data, isLoading, isError } = useExplain(
    open ? (product?.id ?? null) : null,
    requirementId,
    planId,
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto rounded-2xl glass-panel border-border/60 shadow-floating-lg">
        <DialogHeader>
          <DialogTitle>Why this recommendation?</DialogTitle>
          <DialogDescription className="line-clamp-1">{product?.name}</DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="mx-auto h-14 w-14 rounded-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {isError && (
          <div className="flex items-center gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            <AlertTriangle className="size-4 shrink-0" />
            Could not load the score breakdown for this product.
          </div>
        )}

        {data && (
          <div className="space-y-5">
            <div className="flex items-center gap-4">
              <FinalScoreRing value={data.match_score} size={64} />
              <p className="text-sm leading-relaxed text-foreground">{data.summary}</p>
            </div>

            <div>
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Score breakdown
              </p>
              <ScoreBreakdown breakdown={data.score_breakdown} />
            </div>

            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Scorecard (100 pts)
              </p>
              <div className="divide-y divide-border rounded-lg border border-border">
                {data.weighted_points.map((wp) => (
                  <div
                    key={wp.label}
                    className="flex items-center justify-between px-3 py-2 text-sm"
                  >
                    <span className="text-muted-foreground">{wp.label}</span>
                    <span className="tabular font-medium">
                      {points(wp.earned)} / {points(wp.max)}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between bg-muted/50 px-3 py-2 text-sm font-semibold">
                  <span>Total</span>
                  <span className="tabular">
                    {points(data.weighted_points.reduce((s, w) => s + w.earned, 0))} / 100
                  </span>
                </div>
              </div>
            </div>

            {data.reasons.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Reasons
                </p>
                <ul className="space-y-1.5">
                  {data.reasons.map((reason, i) => (
                    <li key={i} className="flex gap-2 text-sm text-foreground">
                      <span className="text-primary">•</span>
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Evidence
              </p>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(data.evidence).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between rounded-md bg-muted px-2.5 py-1.5"
                  >
                    <span className="text-xs text-muted-foreground">{titleCase(key)}</span>
                    <span className="tabular font-medium">
                      {key.toLowerCase().includes("price")
                        ? rupees(Number(value))
                        : key.toLowerCase() === "rating"
                          ? rating(Number(value))
                          : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {data.degraded && (
              <p className="text-xs text-muted-foreground">
                This summary was generated by deterministic rules -- the language model was
                unavailable for this request. Every number above is still computed the same way.
              </p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
