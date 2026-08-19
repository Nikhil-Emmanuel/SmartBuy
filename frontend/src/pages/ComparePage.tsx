import { ArrowLeft, Scale } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { ComparisonTable } from "@/components/compare/ComparisonTable";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompare } from "@/hooks/useProducts";
import { useAppStore } from "@/store/useAppStore";

export function ComparePage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
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
          <h1 className="text-2xl font-semibold text-foreground">Compare products</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every column is a real computed value -- the highlighted cell in each row is the
            best option for that column.
          </p>
        </div>
        {compareSelection.length > 0 && (
          <Button variant="outline" size="sm" onClick={clearCompare}>
            Clear all
          </Button>
        )}
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
