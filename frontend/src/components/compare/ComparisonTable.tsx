import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Star, X } from "lucide-react";
import { useState } from "react";

import { ProductImage } from "@/components/shared/ProductImage";
import { ScoreBreakdown } from "@/components/shared/ScoreBreakdown";
import { Badge } from "@/components/ui/badge";
import {
  badgeLabel,
  deliveryLabel,
  percent,
  rating,
  rupees,
  titleCase,
} from "@/lib/format";
import { FADE, SPRING, useReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { Badge as BadgeType, CompareResponse } from "@/types/api";

const ROW_LABELS: Record<string, string> = {
  price: "Price",
  rating: "Rating",
  review_count: "Reviews",
  delivery_days: "Delivery",
  match_score: "Match score",
  deal_value: "Deal value",
  availability: "Availability",
};

export function ComparisonTable({
  data,
  onRemove,
}: {
  data: CompareResponse;
  onRemove?: (productId: string) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const reduced = useReducedMotion();
  const winnerEntries = Object.entries(data.winner) as [BadgeType, string][];

  return (
    <div className="space-y-4">
      {winnerEntries.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {winnerEntries.map(([badge, productId], i) => {
            const row = data.rows.find((r) => r.product.id === productId);
            if (!row) return null;
            return (
              <motion.div
                key={badge}
                layout={!reduced}
                initial={reduced ? false : { opacity: 0, scale: 0.88 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={reduced ? undefined : { y: -2, scale: 1.02 }}
                transition={{ ...SPRING, delay: reduced ? 0 : i * 0.05 }}
                className="flex items-center gap-1.5 rounded-full border border-border/80 bg-card/90 px-3 py-1.5 text-xs shadow-sm backdrop-blur-sm"
              >
                <Badge variant="accent">{badgeLabel(badge)}</Badge>
                <span className="max-w-[10rem] truncate text-muted-foreground">
                  {row.product.name}
                </span>
              </motion.div>
            );
          })}
        </div>
      )}

      <div className="overflow-x-auto rounded-2xl border border-border/70 bg-card/60 shadow-floating backdrop-blur-md">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="sticky left-0 z-10 w-56 bg-muted/50 p-3 text-left text-xs font-medium text-muted-foreground">
                Product
              </th>
              {data.columns.map((col) => (
                <th
                  key={col}
                  className="p-3 text-center text-xs font-medium text-muted-foreground"
                >
                  {ROW_LABELS[col] ?? titleCase(col)}
                </th>
              ))}
              <th className="w-10 p-3" />
            </tr>
          </thead>
          <tbody>
            {/*
              Rows are returned as a flat array rather than wrapped in a
              Fragment: AnimatePresence tracks its children by key and cannot
              see inside a Fragment, so a Fragment here would silently disable
              the removal animation.
            */}
            <AnimatePresence initial={false}>
              {data.rows.flatMap((row, i) => [
                <motion.tr
                  key={row.product.id}
                  layout={!reduced}
                  initial={reduced ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduced ? undefined : { opacity: 0, x: -24, transition: { duration: 0.18 } }}
                  transition={{ ...FADE, delay: reduced ? 0 : i * 0.05 }}
                  className="border-b border-border last:border-0"
                >
                  <td className="sticky left-0 z-10 bg-card p-3">
                    <div className="flex items-center gap-2.5">
                      <ProductImage
                        category={row.product.category}
                        subcategory={row.product.subcategory}
                        seed={row.product.id}
                        className="size-10 shrink-0"
                        iconClassName="size-4"
                      />
                      <div className="min-w-0">
                        <button
                          onClick={() =>
                            setExpanded(expanded === row.product.id ? null : row.product.id)
                          }
                          className="flex items-center gap-1 text-left text-xs font-medium leading-snug text-foreground hover:text-primary"
                        >
                          <span className="line-clamp-2">{row.product.name}</span>
                          <ChevronDown
                            className={cn(
                              "size-3 shrink-0 transition-transform",
                              expanded === row.product.id && "rotate-180",
                            )}
                          />
                        </button>
                        <p className="text-[11px] text-muted-foreground">{row.product.brand}</p>
                      </div>
                    </div>
                  </td>

                  {data.columns.map((col) => (
                    <td
                      key={col}
                      className={cn(
                        "tabular p-3 text-center text-sm",
                        row.is_best[col] && "bg-savings-soft font-semibold text-savings",
                      )}
                    >
                      <Cell column={col} row={row} />
                    </td>
                  ))}

                  <td className="p-3 text-center">
                    {onRemove && (
                      <motion.button
                        onClick={() => onRemove(row.product.id)}
                        whileHover={reduced ? undefined : { scale: 1.2, rotate: 90 }}
                        whileTap={reduced ? undefined : { scale: 0.9 }}
                        transition={SPRING}
                        className="text-muted-foreground hover:text-danger"
                        aria-label="Remove from comparison"
                      >
                        <X className="size-3.5" />
                      </motion.button>
                    )}
                  </td>
                </motion.tr>,

                expanded === row.product.id ? (
                  <motion.tr
                    key={`${row.product.id}-detail`}
                    initial={reduced ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={reduced ? undefined : { opacity: 0, transition: { duration: 0.12 } }}
                    transition={FADE}
                    className="border-b border-border bg-muted/30"
                  >
                    <td colSpan={data.columns.length + 2} className="p-4">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Score breakdown
                      </p>
                      <ScoreBreakdown breakdown={row.score_breakdown} compact />
                    </td>
                  </motion.tr>
                ) : null,
              ])}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Cell({ column, row }: { column: string; row: CompareResponse["rows"][number] }) {
  const p = row.product;
  switch (column) {
    case "price":
      return <>{rupees(p.price)}</>;
    case "rating":
      return (
        <span className="inline-flex items-center gap-1">
          <Star className="size-3.5 fill-caution text-caution" />
          {rating(p.rating)}
        </span>
      );
    case "review_count":
      return <>{p.review_count ?? "—"}</>;
    case "delivery_days":
      return <>{deliveryLabel(p.delivery_days)}</>;
    case "match_score":
      return <>{percent(row.match_score)}</>;
    case "deal_value":
      return <>{percent(row.deal_value)}</>;
    case "availability":
      return p.availability === "in_stock" ? (
        <Check className="mx-auto size-4 text-savings" />
      ) : (
        <span className="text-xs text-muted-foreground">{titleCase(p.availability)}</span>
      );
    default:
      return <>—</>;
  }
}
