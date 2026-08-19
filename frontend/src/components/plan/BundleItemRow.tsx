import { Heart, ThumbsDown, ThumbsUp } from "lucide-react";

import { ProductImage } from "@/components/shared/ProductImage";
import { Button } from "@/components/ui/button";
import { rupees } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BundleItem } from "@/types/api";

export function BundleItemRow({
  item,
  onExplain,
  onFeedback,
  feedbackGiven,
}: {
  item: BundleItem;
  onExplain?: () => void;
  onFeedback?: (type: "relevant" | "not_relevant" | "saved") => void;
  feedbackGiven?: "relevant" | "not_relevant" | "saved" | null;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
      <ProductImage
        category={item.product.category}
        seed={item.product.id}
        className="size-14 shrink-0"
        iconClassName="size-5"
      />

      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {item.requirement.item_name}
        </p>
        <p className="line-clamp-1 text-sm font-medium text-foreground">{item.product.name}</p>
        <p className="tabular text-xs text-muted-foreground">
          {rupees(item.product.price)} × {item.quantity} ={" "}
          <span className="font-medium text-foreground">{rupees(item.line_total)}</span>
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          className={cn(feedbackGiven === "relevant" && "text-savings")}
          onClick={() => onFeedback?.("relevant")}
          title="Relevant"
        >
          <ThumbsUp className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className={cn(feedbackGiven === "not_relevant" && "text-danger")}
          onClick={() => onFeedback?.("not_relevant")}
          title="Not relevant"
        >
          <ThumbsDown className="size-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className={cn(feedbackGiven === "saved" && "text-primary")}
          onClick={() => onFeedback?.("saved")}
          title="Save"
        >
          <Heart className="size-3.5" />
        </Button>
        {onExplain && (
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onExplain}>
            Why?
          </Button>
        )}
      </div>
    </div>
  );
}
