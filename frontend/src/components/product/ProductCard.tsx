import { motion } from "framer-motion";
import { Check, Scale, Star } from "lucide-react";
import type { ReactNode } from "react";

import { MarketplaceSearchMenu } from "@/components/shared/MarketplaceSearchMenu";
import { ProductImage } from "@/components/shared/ProductImage";
import { SimulatedBadge } from "@/components/shared/SimulatedBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { badgeLabel, deliveryLabel, percent, rating, rupees, sourceLabel } from "@/lib/format";
import { CARD_REVEAL, SPRING_BOUNCE, useReducedMotion } from "@/lib/motion";
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
  const reduced = useReducedMotion();
  const isTopFit = badge === "best_overall" || (score !== undefined && score !== null && score >= 0.85);

  return (
    <motion.div
      variants={CARD_REVEAL}
      initial={reduced ? false : "hidden"}
      animate="visible"
      whileHover={reduced ? undefined : { y: -6, scale: 1.01 }}
      transition={SPRING_BOUNCE}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-all duration-300 hover:border-primary/50 hover:shadow-floating-lg",
        isTopFit && "z-10 ring-1 ring-primary/30 shadow-glass",
        compared && "ring-2 ring-primary ring-offset-2 ring-offset-background",
        className,
      )}
    >
      <div className="relative overflow-hidden p-3 pb-0">
        <ProductImage
          category={product.category}
          subcategory={product.subcategory}
          seed={product.id}
          className="h-32 w-full rounded-xl transition-transform duration-500 ease-out group-hover:scale-[1.08]"
        />
        {label && (
          <Badge
            variant={BADGE_VARIANT[badge ?? ""] ?? "accent"}
            className="absolute left-5 top-5 shadow-sm backdrop-blur-sm"
          >
            {label}
          </Badge>
        )}
        {typeof product.discount_pct === "number" && product.discount_pct > 0 && (
          <Badge variant="danger" className="absolute right-5 top-5 shadow-sm backdrop-blur-sm">
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

        <h3 className="line-clamp-2 text-sm font-medium leading-snug text-foreground transition-colors group-hover:text-primary">
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
            Match score <span className="font-semibold text-primary">{percent(score)}</span>
          </div>
        )}

        {reasons && reasons.length > 0 && (
          <ul className="mt-1 space-y-1 border-t border-border/60 pt-2">
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
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.92 }}>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onExplain}>
                  Why this?
                </Button>
              </motion.div>
            )}
            {comparable && (
              <motion.div whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.90 }}>
                <Button
                  variant={compared ? "default" : "outline"}
                  size="icon-sm"
                  onClick={onToggleCompare}
                  title={compared ? "Remove from comparison" : "Add to comparison"}
                >
                  <Scale className="size-3.5" />
                </Button>
              </motion.div>
            )}
            <MarketplaceSearchMenu product={product} />
          </div>
        </div>
        {footer}
      </div>
    </motion.div>
  );
}

export type { ScoreBreakdownType };
