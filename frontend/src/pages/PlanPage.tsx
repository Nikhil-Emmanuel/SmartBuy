import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, PackageCheck, Sparkles, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { BundleItemRow } from "@/components/plan/BundleItemRow";
import { BundleSwitcher } from "@/components/plan/BundleSwitcher";
import { ExplainDialog } from "@/components/product/ExplainDialog";
import { CountUp } from "@/components/shared/CountUp";
import { Reveal } from "@/components/shared/Reveal";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOptimizeBundle, useSelectBundle, useShoppingPlan } from "@/hooks/usePlan";
import { useSendFeedback } from "@/hooks/useProfile";
import { rupees, unfulfilledLabel } from "@/lib/format";
import { listChild, listParent, SPRING } from "@/lib/motion";
import type { BundlePreset, Product, Requirement } from "@/types/api";

type QuickFeedback = "relevant" | "not_relevant" | "saved";

export function PlanPage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  const { data, isLoading, isError, refetch } = useShoppingPlan(planId);
  const optimize = useOptimizeBundle(planId);
  const selectBundle = useSelectBundle(planId);
  const sendFeedback = useSendFeedback();

  const [activePreset, setActivePreset] = useState<BundlePreset | null>(null);
  const [explainTarget, setExplainTarget] = useState<{
    product: Product;
    requirement: Requirement;
  } | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, QuickFeedback>>({});

  useEffect(() => {
    if (data?.selected_preset) setActivePreset(data.selected_preset);
    else if (data?.bundles.length) setActivePreset(data.bundles[0].preset);
  }, [data?.selected_preset, data?.bundles]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8 sm:px-6">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <ErrorState title="Could not load the shopping plan" onRetry={() => refetch()} />
      </div>
    );
  }

  if (data.bundles.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <EmptyState
          icon={Sparkles}
          title="Ready to fit this to your budget"
          description={`${data.goal} -- run the optimizer to see the best combination of products within ${rupees(data.totals.budget)}.`}
          action={
            <Button onClick={() => optimize.mutate(undefined)} disabled={optimize.isPending}>
              {optimize.isPending ? "Optimizing…" : "Build my shopping plan"}
            </Button>
          }
        />
      </div>
    );
  }

  const bundle = data.bundles.find((b) => b.preset === activePreset) ?? data.bundles[0];
  const overBudget = data.totals.budget !== null && bundle.total_cost > data.totals.budget;

  function handleSelect(preset: BundlePreset) {
    setActivePreset(preset);
    selectBundle.mutate(preset, {
      onSuccess: () => toast.success(`Switched to the ${preset.replace("_", " ")} bundle`),
    });
  }

  function handleFeedback(product: Product, type: QuickFeedback) {
    setFeedbackGiven((prev) => ({ ...prev, [product.id]: type }));
    sendFeedback.mutate({ product_id: product.id, plan_id: planId, feedback_type: type });
    if (type === "saved") toast.success("Saved to your profile");
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 pb-16 pt-8 sm:px-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-primary">Shopping plan</p>
        <h1 className="mt-1 text-2xl font-semibold text-foreground">{data.goal}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{data.goal_summary}</p>
      </div>

      {data.status === "budget_infeasible" && (
        <Alert variant="destructive">
          <AlertTriangle />
          <div>
            <AlertTitle>This budget doesn&apos;t cover everything essential</AlertTitle>
            <AlertDescription>
              We&apos;ve built the closest bundle we can. Increase the budget from the chat, or
              review what&apos;s missing below.
            </AlertDescription>
          </div>
        </Alert>
      )}

      <BundleSwitcher
        bundles={data.bundles}
        active={bundle.preset}
        selected={data.selected_preset}
        onSelect={handleSelect}
      />

      <Card>
        <CardContent className="grid grid-cols-2 gap-4 p-5 sm:grid-cols-4">
          <Stat label="Budget" value={data.totals.budget} />
          <Stat label="This bundle" value={bundle.total_cost} danger={overBudget} />
          <Stat label="You save" value={bundle.total_savings} accent="savings" />
          <Stat
            label={overBudget ? "Over by" : "Remaining"}
            value={overBudget ? bundle.over_budget : bundle.remaining_budget}
            danger={overBudget}
          />
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">
          {bundle.items.length} items in this bundle
        </h2>
        {bundle.preset === data.selected_preset ? (
          <Badge variant="savings">Selected</Badge>
        ) : (
          <Button size="sm" variant="outline" onClick={() => handleSelect(bundle.preset)}>
            Select this bundle
          </Button>
        )}
      </div>

      {/*
        Keyed on the preset as well as the requirement: switching bundles
        genuinely swaps the products, so the rows should re-enter rather than
        silently mutate their contents in place. `layout` then animates the
        height change when the two bundles cover a different number of items.
      */}
      <motion.div
        className="space-y-2.5"
        variants={listParent(bundle.items.length)}
        initial={reduced ? false : "hidden"}
        animate="visible"
        key={bundle.preset}
      >
        {bundle.items.map((item) => (
          <motion.div key={item.requirement.id} variants={listChild} layout={!reduced}>
            <BundleItemRow
              item={item}
              feedbackGiven={feedbackGiven[item.product.id] ?? null}
              onFeedback={(type) => handleFeedback(item.product, type)}
              onExplain={() =>
                setExplainTarget({ product: item.product, requirement: item.requirement })
              }
            />
          </motion.div>
        ))}
      </motion.div>

      {bundle.excluded.length > 0 && (
        <Reveal>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Left out of this bundle
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 pt-0">
              {bundle.excluded.map((ex) => (
                <p key={ex.requirement_id} className="text-xs text-muted-foreground">
                  {ex.item_name ?? "Item"} -- {ex.reason}
                </p>
              ))}
            </CardContent>
          </Card>
        </Reveal>
      )}

      {data.substitutions.length > 0 && (
        <Reveal>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Cheaper swaps worth knowing about</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pt-0">
              {data.substitutions.map((sub) => (
                <div
                  key={sub.requirement_id}
                  className="rounded-lg border border-border bg-muted/40 p-3 text-xs"
                >
                  <p className="text-foreground">{sub.reason}</p>
                  <p className="mt-1 text-muted-foreground">
                    {sub.from.name} <span className="mx-1">→</span> {sub.to.name}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </Reveal>
      )}

      {data.unfulfilled.length > 0 && (
        <Reveal>
          <Card className="border-caution/25 bg-caution-soft/40">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-caution">Not found</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 pt-0">
              {data.unfulfilled.map((u) => (
                <p key={u.requirement_id} className="text-xs text-caution">
                  {u.item_name} -- {unfulfilledLabel(u.reason)}
                </p>
              ))}
            </CardContent>
          </Card>
        </Reveal>
      )}

      {data.already_owned.length > 0 && (
        <Reveal>
          <Card className="border-savings/25 bg-savings-soft/40">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm text-savings">
                <PackageCheck className="size-4" /> Already in your kit
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2 pt-0">
              {data.already_owned.map((item, i) => (
                <motion.span
                  key={item.item_name}
                  initial={reduced ? false : { opacity: 0, scale: 0.85 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ ...SPRING, delay: reduced ? 0 : i * 0.04 }}
                  className="rounded-full border border-savings/30 bg-card px-3 py-1 text-xs text-savings"
                >
                  {item.item_name}
                </motion.span>
              ))}
            </CardContent>
          </Card>
        </Reveal>
      )}

      <div className="flex justify-center pt-4">
        <Button variant="outline" onClick={() => navigate(`/plan/${planId}/discover`)}>
          <Wallet className="size-4" /> Adjust individual products
        </Button>
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

/**
 * One figure in the totals strip.
 *
 * The number counts rather than snapping because this strip is the direct
 * consequence of switching bundles -- watching "You save" climb is what makes
 * the switch legible. `CountUp` lands on exactly the value it was given; the
 * arithmetic is all backend-side, and a null budget is still an em dash.
 */
function Stat({
  label,
  value,
  danger,
  accent,
}: {
  label: string;
  value: number | null;
  danger?: boolean;
  accent?: "savings";
}) {
  const tone = danger ? "text-danger" : accent === "savings" ? "text-savings" : "text-foreground";
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`tabular text-lg font-semibold ${tone}`}>
        {value === null ? "—" : <CountUp value={value} format={rupees} duration={0.6} />}
      </p>
    </div>
  );
}
