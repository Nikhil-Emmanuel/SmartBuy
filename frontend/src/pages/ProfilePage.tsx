import { motion } from "framer-motion";
import { Heart, History, Sparkles, ThumbsDown, ThumbsUp, User } from "lucide-react";
import { Link } from "react-router-dom";

import { ProductCard } from "@/components/product/ProductCard";
import { PersonalizedOffer } from "@/components/profile/PersonalizedOffer";
import { ProductImage } from "@/components/shared/ProductImage";
import { Reveal } from "@/components/shared/Reveal";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProfile } from "@/hooks/useProfile";
import { dateLabel, rupees, titleCase } from "@/lib/format";
import { HOVER_LIFT, listChild, listParent, useReducedMotion } from "@/lib/motion";

const FEEDBACK_ICON = {
  relevant: ThumbsUp,
  not_relevant: ThumbsDown,
  saved: Heart,
  not_interested: ThumbsDown,
} as const;

export function ProfilePage() {
  const { data, isLoading, isError, refetch } = useProfile();
  const reduced = useReducedMotion();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8 sm:px-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <ErrorState title="Could not load your profile" onRetry={() => refetch()} />
      </div>
    );
  }

  const { preferences } = data;
  const hasPreferences = preferences.preferred_categories.length || preferences.preferred_brands.length;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 sm:px-6">
      <div className="flex items-center gap-3">
        <motion.div
          initial={reduced ? false : { scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 320, damping: 24 }}
          className="flex size-11 items-center justify-center rounded-full bg-primary-soft text-primary"
        >
          <User className="size-5" />
        </motion.div>
        <div>
          <h1 className="text-xl font-semibold text-foreground">Your profile</h1>
          <p className="text-sm text-muted-foreground">
            {data.is_anonymous ? "Anonymous session" : "Signed in"} · learned from what you save
            and skip
          </p>
        </div>
      </div>

      <PersonalizedOffer />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Sparkles className="size-4 text-primary" /> Preferences we&apos;ve picked up
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          {!hasPreferences ? (
            <p className="text-sm text-muted-foreground">
              Nothing yet -- like, save or skip products and this fills in over time.
            </p>
          ) : (
            <>
              {preferences.preferred_categories.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs text-muted-foreground">Categories</p>
                  <div className="flex flex-wrap gap-1.5">
                    {preferences.preferred_categories.map((c) => (
                      <Badge key={c} variant="accent">
                        {titleCase(c)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {preferences.preferred_brands.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs text-muted-foreground">Brands</p>
                  <div className="flex flex-wrap gap-1.5">
                    {preferences.preferred_brands.map((b) => (
                      <Badge key={b} variant="outline">
                        {b}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          <div className="flex gap-6 border-t border-border pt-3 text-xs text-muted-foreground">
            <span>
              Price bias: <span className="font-medium text-foreground">{titleCase(preferences.price_bias)}</span>
            </span>
            <span>
              Delivery bias: <span className="font-medium text-foreground">{titleCase(preferences.delivery_bias)}</span>
            </span>
            {preferences.min_price !== null && preferences.max_price !== null && (
              <span>
                Typical range:{" "}
                <span className="font-medium text-foreground">
                  {rupees(preferences.min_price)} – {rupees(preferences.max_price)}
                </span>
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <Reveal>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Saved products</h2>
        {data.saved_products.length === 0 ? (
          <EmptyState icon={Heart} title="Nothing saved yet" className="py-8" />
        ) : (
          <motion.div
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
            variants={listParent(data.saved_products.length)}
            initial={reduced ? false : "hidden"}
            animate="visible"
          >
            {data.saved_products.map((product) => (
              <motion.div key={product.id} variants={listChild}>
                <ProductCard product={product} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </Reveal>

      <Reveal>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Recent plans</h2>
        {data.recent_plans.length === 0 ? (
          <EmptyState icon={History} title="No plans yet" className="py-8" />
        ) : (
          <div className="space-y-2">
            {data.recent_plans.map((plan) => (
              <motion.div key={plan.plan_id} whileHover={reduced ? undefined : HOVER_LIFT}>
                <Link
                  to={`/plan/${plan.plan_id}`}
                  className="flex items-center justify-between rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{plan.goal}</p>
                    <p className="text-xs text-muted-foreground">{dateLabel(plan.created_at)}</p>
                  </div>
                  <span className="tabular text-sm font-semibold text-foreground">
                    {rupees(plan.estimated_total)}
                  </span>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </Reveal>

      <Reveal>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Feedback history</h2>
        {data.feedback_history.length === 0 ? (
          <EmptyState icon={ThumbsUp} title="No feedback given yet" className="py-8" />
        ) : (
          <div className="space-y-2">
            {data.feedback_history.map((entry, i) => {
              const Icon = FEEDBACK_ICON[entry.feedback_type];
              return (
                <motion.div
                  key={`${entry.product.id}-${i}`}
                  initial={reduced ? false : { opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.3, delay: reduced ? 0 : Math.min(i, 10) * 0.04 }}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"
                >
                  <ProductImage
                    category={entry.product.category}
                    seed={entry.product.id}
                    className="size-10 shrink-0"
                    iconClassName="size-4"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-1 text-sm text-foreground">{entry.product.name}</p>
                    <p className="text-xs text-muted-foreground">{dateLabel(entry.created_at)}</p>
                  </div>
                  <Badge variant="outline" className="gap-1 capitalize">
                    <Icon className="size-3" />
                    {entry.feedback_type.replace("_", " ")}
                  </Badge>
                </motion.div>
              );
            })}
          </div>
        )}
      </Reveal>
    </div>
  );
}
