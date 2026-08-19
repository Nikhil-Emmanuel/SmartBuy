import { motion } from "framer-motion";
import { ArrowRight, PackageCheck, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { RequirementRow } from "@/components/plan/RequirementRow";
import { ErrorState } from "@/components/shared/States";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePatchRequirement, useRequirements } from "@/hooks/usePlan";
import { rupees } from "@/lib/format";
import { listParent } from "@/lib/motion";
import type { Requirement, RequirementGroups } from "@/types/api";

const GROUP_LABELS: Record<keyof RequirementGroups, string> = {
  essential: "Essential",
  recommended: "Recommended",
  optional: "Nice to have",
};

export function RequirementsPage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useRequirements(planId);
  const patch = usePatchRequirement(planId);
  const [pendingId, setPendingId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <ErrorState
          title="Could not load your requirements"
          description="The plan may not exist yet, or the service is unreachable."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  function toggleOwned(requirement: Requirement, owned: boolean) {
    setPendingId(requirement.id);
    patch.mutate(
      { requirementId: requirement.id, patch: { is_owned: owned } },
      { onSettled: () => setPendingId(null) },
    );
  }

  function changeQuantity(requirement: Requirement, quantity: number) {
    setPendingId(requirement.id);
    patch.mutate(
      { requirementId: requirement.id, patch: { quantity } },
      { onSettled: () => setPendingId(null) },
    );
  }

  const groups = Object.entries(data.requirements) as [keyof RequirementGroups, Requirement[]][];
  const totalItems = groups.reduce((sum, [, items]) => sum + items.length, 0);
  const toBuy = groups.reduce(
    (sum, [, items]) => sum + items.filter((r) => !r.is_owned).length,
    0,
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-wide text-primary">Your plan</p>
        <h1 className="mt-1 text-2xl font-semibold text-foreground">{data.goal}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{data.goal_summary}</p>
      </div>

      <Card className="mb-6">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div>
            <p className="text-xs text-muted-foreground">Estimated cost of everything you need</p>
            <p className="tabular text-lg font-semibold text-foreground">
              {rupees(data.estimated_range.min)} – {rupees(data.estimated_range.max)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">
              {toBuy} to buy · {totalItems - toBuy} already owned
            </p>
          </div>
        </CardContent>
      </Card>

      {data.already_owned.length > 0 && (
        <Card className="mb-6 border-savings/25 bg-savings-soft/40">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-savings">
              <PackageCheck className="size-4" /> Already in your kit
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 pt-0">
            {data.already_owned.map((item) => (
              <span
                key={item.item_name}
                className="rounded-full border border-savings/30 bg-card px-3 py-1 text-xs text-savings"
              >
                {item.item_name}
              </span>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="space-y-8">
        {groups.map(([group, items]) =>
          items.length ? (
            <section key={group}>
              <h2 className="mb-3 text-sm font-semibold text-foreground">
                {GROUP_LABELS[group]}{" "}
                <span className="font-normal text-muted-foreground">({items.length})</span>
              </h2>
              <motion.div
                variants={listParent(items.length)}
                initial="hidden"
                animate="visible"
                className="space-y-2.5"
              >
                {items.map((requirement) => (
                  <RequirementRow
                    key={requirement.id}
                    requirement={requirement}
                    busy={pendingId === requirement.id}
                    onToggleOwned={(owned) => toggleOwned(requirement, owned)}
                    onQuantityChange={(q) => changeQuantity(requirement, q)}
                  />
                ))}
              </motion.div>
            </section>
          ) : null,
        )}
      </div>

      <div className="sticky bottom-6 mt-8 flex justify-center">
        <Button size="lg" className="shadow-lg" onClick={() => navigate(`/plan/${planId}/discover`)}>
          <Search className="size-4" /> Find the best products
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

