import { motion } from "framer-motion";
import { PackageSearch, Scale, Wallet } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ExplainDialog } from "@/components/product/ExplainDialog";
import { ProductCard } from "@/components/product/ProductCard";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRecommendations } from "@/hooks/usePlan";
import { unfulfilledLabel } from "@/lib/format";
import { listParent } from "@/lib/motion";
import { MAX_COMPARE_ITEMS, useAppStore } from "@/store/useAppStore";
import type { Product, Requirement } from "@/types/api";

export function DiscoverPage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useRecommendations(planId, null);

  const compareSelection = useAppStore((s) => s.compareSelection);
  const toggleCompare = useAppStore((s) => s.toggleCompare);

  const [explainTarget, setExplainTarget] = useState<{
    product: Product;
    requirement: Requirement;
  } | null>(null);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-3">
            <Skeleton className="h-5 w-48" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((__, j) => (
                <Skeleton key={j} className="h-72 w-full rounded-xl" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <ErrorState
          title="Could not load product recommendations"
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-10 px-4 pb-28 pt-8 sm:px-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-primary">Discover</p>
        <h1 className="mt-1 text-2xl font-semibold text-foreground">
          The best options for each item
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ranked on fit, quality, budget, reviews, delivery and deal value. Select up to{" "}
          {MAX_COMPARE_ITEMS} to compare side by side.
        </p>
      </div>

      {data.results.map(({ requirement, recommendations, unfulfilled_reason }) => (
        <section key={requirement.id}>
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold text-foreground">{requirement.item_name}</h2>
            <Badge variant="outline" className="capitalize">
              {requirement.priority}
            </Badge>
          </div>

          {recommendations.length === 0 ? (
            <EmptyState
              icon={PackageSearch}
              title="No matches found"
              description={
                unfulfilled_reason
                  ? unfulfilledLabel(unfulfilled_reason)
                  : "Nothing in the catalog matched this requirement."
              }
              className="py-8"
            />
          ) : (
            <motion.div
              variants={listParent(recommendations.length)}
              initial="hidden"
              animate="visible"
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
            >
              {recommendations.map((rec) => (
                <ProductCard
                  key={rec.product.id}
                  product={rec.product}
                  badge={rec.badge}
                  score={rec.score}
                  reasons={rec.reasons}
                  comparable
                  compared={compareSelection.includes(rec.product.id)}
                  onToggleCompare={() => toggleCompare(rec.product.id)}
                  onExplain={() => setExplainTarget({ product: rec.product, requirement })}
                />
              ))}
            </motion.div>
          )}
        </section>
      ))}

      <div className="fixed inset-x-0 bottom-6 z-30 flex justify-center px-4">
        <div className="flex items-center gap-3 rounded-full border border-border bg-card/95 px-4 py-2.5 shadow-xl backdrop-blur">
          {compareSelection.length > 0 && (
            <span className="text-xs text-muted-foreground">
              {compareSelection.length} selected
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={compareSelection.length < 2}
            onClick={() => navigate(`/plan/${planId}/compare`)}
          >
            <Scale className="size-4" /> Compare
          </Button>
          <Button size="sm" onClick={() => navigate(`/plan/${planId}`)}>
            <Wallet className="size-4" /> View shopping plan
          </Button>
        </div>
      </div>

      <ExplainDialog
        open={Boolean(explainTarget)}
        onOpenChange={(open) => !open && setExplainTarget(null)}
        product={explainTarget?.product ?? null}
        requirementId={explainTarget?.requirement.id ?? null}
        planId={planId}
      />
    </div>
  );
}
