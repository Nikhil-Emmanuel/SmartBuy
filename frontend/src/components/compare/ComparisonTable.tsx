import { Check, ChevronDown, Star, X } from "lucide-react";
import { Fragment, useState } from "react";

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
  const winnerEntries = Object.entries(data.winner) as [BadgeType, string][];

  return (
    <div className="space-y-4">
      {winnerEntries.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {winnerEntries.map(([badge, productId]) => {
            const row = data.rows.find((r) => r.product.id === productId);
            if (!row) return null;
            return (
              <div
                key={badge}
                className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs"
              >
                <Badge variant="accent">{badgeLabel(badge)}</Badge>
                <span className="max-w-[10rem] truncate text-muted-foreground">
                  {row.product.name}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-border">
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
            {data.rows.map((row) => (
              <Fragment key={row.product.id}>
                <tr className="border-b border-border last:border-0">
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
                      <button
                        onClick={() => onRemove(row.product.id)}
                        className="text-muted-foreground hover:text-danger"
                        aria-label="Remove from comparison"
                      >
                        <X className="size-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
                {expanded === row.product.id && (
                  <tr className="border-b border-border bg-muted/30">
                    <td colSpan={data.columns.length + 2} className="p-4">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Score breakdown
                      </p>
                      <ScoreBreakdown breakdown={row.score_breakdown} compact />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
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
