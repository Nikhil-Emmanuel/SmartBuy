import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Scale } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { ComparisonTable } from "@/components/compare/ComparisonTable";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompare } from "@/hooks/useProducts";
import { FADE, useReducedMotion } from "@/lib/motion";
import { useAppStore } from "@/store/useAppStore";

export function ComparePage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  const compareSelection = useAppStore((s) => s.compareSelection);
  const toggleCompare = useAppStore((s) => s.toggleCompare);
  const clearCompare = useAppStore((s) => s.clearCompare);

  const { data, isLoading, isError, refetch } = useCompare(compareSelection, planId);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <div className="flex items-center justify-between">
        <div>
          <Button
            variant="ghost"
            size="sm"
            className="mb-2 -ml-2 text-muted-foreground"
            onClick={() => navigate(`/plan/${planId}/discover`)}
          >
            <ArrowLeft className="size-4" /> Back to discovery
          </Button>
          <motion.h1
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={FADE}
            className="text-2xl font-semibold text-foreground"
          >
            Compare products
          </motion.h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every column is a real computed value -- the highlighted cell in each row is the
            best option for that column.
          </p>
        </div>
        <AnimatePresence>
          {compareSelection.length > 0 && (
            <motion.div
              initial={reduced ? false : { opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={reduced ? undefined : { opacity: 0, scale: 0.9 }}
              transition={FADE}
            >
              <Button variant="outline" size="sm" onClick={clearCompare}>
                Clear all
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {compareSelection.length < 2 && (
        <EmptyState
          icon={Scale}
          title="Select at least two products to compare"
          description="Go back to discovery and choose up to four products using the compare icon on each card."
          action={
            <Button onClick={() => navigate(`/plan/${planId}/discover`)}>Back to discovery</Button>
          }
        />
      )}

      {compareSelection.length >= 2 && isLoading && (
        <Skeleton className="h-96 w-full rounded-xl" />
      )}

      {compareSelection.length >= 2 && isError && (
        <ErrorState title="Could not load the comparison" onRetry={() => refetch()} />
      )}

      {compareSelection.length >= 2 && data && (
        <ComparisonTable data={data} onRemove={toggleCompare} />
      )}
    </div>
  );
}
