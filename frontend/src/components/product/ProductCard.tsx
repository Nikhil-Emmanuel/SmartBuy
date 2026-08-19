import { Check, ExternalLink, Scale, Star } from "lucide-react";
import type { ReactNode } from "react";

import { ProductImage } from "@/components/shared/ProductImage";
import { SimulatedBadge } from "@/components/shared/SimulatedBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { badgeLabel, deliveryLabel, percent, rating, rupees, sourceLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Product, ScoreBreakdown as ScoreBreakdownType } from "@/types/api";

const BADGE_VARIANT: Record<string, "savings" | "info" | "accent" | "caution"> = {
  best_overall: "accent",
  best_budget: "savings",
  best_rated: "info",
  best_premium: "caution",
  best_deal: "savings",
};

export function ProductCard({
  product,
  badge,
  score,
  reasons,
  comparable = false,
  compared = false,
  onToggleCompare,
  onExplain,
  footer,
  className,
}: {
  product: Product;
  badge?: string | null;
  score?: number | null;
  reasons?: string[];
  comparable?: boolean;
  compared?: boolean;
  onToggleCompare?: () => void;
  onExplain?: () => void;
  footer?: ReactNode;
  className?: string;
}) {
  const label = badgeLabel(badge);

  return (
    <div
      className={cn(
        "group flex flex-col overflow-hidden rounded-xl border border-border bg-card transition-all hover:border-primary/40 hover:shadow-md",
        compared && "ring-2 ring-primary ring-offset-2 ring-offset-background",
        className,
      )}
    >
      <div className="relative p-3 pb-0">
        <ProductImage category={product.category} seed={product.id} className="h-32 w-full" />
        {label && (
          <Badge
            variant={BADGE_VARIANT[badge ?? ""] ?? "accent"}
            className="absolute left-5 top-5 shadow-sm"
          >
            {label}
          </Badge>
        )}
        {typeof product.discount_pct === "number" && product.discount_pct > 0 && (
          <Badge variant="danger" className="absolute right-5 top-5 shadow-sm">
            {product.discount_pct}% off
          </Badge>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <span className="text-xs font-medium text-muted-foreground">{product.brand}</span>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {sourceLabel(product.source)}
          </span>
        </div>

        <h3 className="line-clamp-2 text-sm font-medium leading-snug text-foreground">
          {product.name}
        </h3>

        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {product.rating !== null && (
            <span className="inline-flex items-center gap-1">
              <Star className="size-3.5 fill-caution text-caution" />
              <span className="font-medium text-foreground">{rating(product.rating)}</span>
              {product.review_count ? `(${product.review_count})` : null}
            </span>
          )}
          <span>{deliveryLabel(product.delivery_days)}</span>
        </div>

        <div className="flex items-baseline gap-2 pt-1">
          <span className="text-lg font-semibold tabular text-foreground">
            {rupees(product.price)}
          </span>
          {product.original_price && product.original_price > product.price && (
            <span className="tabular text-xs text-muted-foreground line-through">
              {rupees(product.original_price)}
            </span>
          )}
        </div>

        {score !== undefined && score !== null && (
          <div className="text-xs text-muted-foreground">
            Match score <span className="font-medium text-foreground">{percent(score)}</span>
          </div>
        )}

        {reasons && reasons.length > 0 && (
          <ul className="mt-1 space-y-1 border-t border-border pt-2">
            {reasons.slice(0, 2).map((reason, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                <Check className="mt-0.5 size-3 shrink-0 text-savings" />
                <span className="leading-snug">{reason}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-auto flex items-center justify-between gap-2 pt-3">
          <SimulatedBadge />
          <div className="flex items-center gap-1">
            {onExplain && (
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onExplain}>
                Why this?
              </Button>
            )}
            {comparable && (
              <Button
                variant={compared ? "default" : "outline"}
                size="icon-sm"
                onClick={onToggleCompare}
                title={compared ? "Remove from comparison" : "Add to comparison"}
              >
                <Scale className="size-3.5" />
              </Button>
            )}
            {product.url && (
              <Button variant="outline" size="icon-sm" asChild>
                <a href={product.url} target="_blank" rel="noreferrer">
                  <ExternalLink className="size-3.5" />
                </a>
              </Button>
            )}
          </div>
        </div>
        {footer}
      </div>
    </div>
  );
}

export type { ScoreBreakdownType };
