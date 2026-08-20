/**
 * The one place the trained model speaks to the user.
 *
 * `ml/personalization/train.py` fits a classifier over behavioural features;
 * `/api/personalization` scores the caller and attaches the offer policy for
 * whichever segment came back. This renders that answer -- including when the
 * answer is "we don't know yet".
 *
 * Two rules this component exists to keep:
 *
 * 1. A non-`ok` status is shown, not hidden. Rendering nothing would let a
 *    demo imply everyone gets a coupon; saying "you need a bit more history"
 *    is both true and more useful.
 * 2. The confidence figure is displayed as-is. A personalised discount that
 *    cannot say how sure it is has no business being on the page.
 */

import { motion, useReducedMotion } from "framer-motion";
import { Check, Copy, Sparkles, TrendingUp, Truck } from "lucide-react";
import { useState } from "react";

import { CountUp } from "@/components/shared/CountUp";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { usePersonalization } from "@/hooks/useProfile";
import { EASE_OUT, FADE, listChild, listParent } from "@/lib/motion";
import type { PersonalizationResponse } from "@/types/api";

const NOT_YET: Record<PersonalizationResponse["status"], string> = {
  ok: "",
  insufficient_history:
    "Browse and save a few more products and we'll be able to tailor an offer to how you actually shop.",
  low_confidence:
    "Your activity doesn't clearly match one shopping pattern yet, so we'd rather not guess at an offer.",
  model_unavailable: "Personalised offers are unavailable right now.",
};

export function PersonalizedOffer() {
  const { data, isLoading, isError } = usePersonalization();
  const reduced = useReducedMotion();
  const [copied, setCopied] = useState(false);

  // A failed request is not worth a red box on the profile page -- there is
  // simply no offer to show.
  if (isLoading || isError || !data) return null;

  if (data.status !== "ok") {
    return (
      <div className="space-y-4">
        <Card className="border-dashed">
          <CardContent className="flex items-start gap-3 p-4">
            <Sparkles className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">No personalised offer yet</p>
              <p className="text-xs text-muted-foreground">{NOT_YET[data.status]}</p>
            </div>
          </CardContent>
        </Card>
        {/* Low confidence still means we know how they shop -- only the label
            is missing, so the habits are worth showing on their own. */}
        <HabitGrid habits={data.habits} />
      </div>
    );
  }

  const copy = async () => {
    if (!data.coupon_code) return;
    await navigator.clipboard.writeText(data.coupon_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={FADE}
    >
      <Card className="relative overflow-hidden rounded-2xl border-primary/30 bg-primary-soft/50 shadow-floating-lg backdrop-blur-md">
        {/* Slow sheen. Decorative, so it is the first thing reduced-motion drops. */}
        {!reduced && (
          <motion.div
            aria-hidden
            className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r from-transparent via-white/30 to-transparent"
            animate={{ x: ["0%", "400%"] }}
            transition={{ duration: 2.6, ease: EASE_OUT, repeat: Infinity, repeatDelay: 4 }}
          />
        )}

        <CardContent className="relative space-y-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="accent" className="gap-1 shadow-sm">
              <Sparkles className="size-3 text-primary" />
              {data.label}
            </Badge>
            <span className="text-xs text-muted-foreground">
              matched from {data.events_considered} of your interactions ·{" "}
              <CountUp
                value={data.confidence * 100}
                format={(v) => `${v.toFixed(0)}% confidence`}
                duration={0.8}
              />
            </span>
          </div>

          <p className="text-sm font-medium text-foreground">{data.rationale}</p>

          {data.discount_pct > 0 && data.coupon_code ? (
            <div className="flex flex-wrap items-center gap-3">
              <motion.div
                initial={reduced ? false : { scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: reduced ? 0 : 0.14, ease: EASE_OUT, duration: 0.4 }}
                className="text-3xl font-bold text-primary"
              >
                <CountUp value={data.discount_pct} format={(v) => `${v.toFixed(0)}% off`} />
              </motion.div>
              <motion.button
                type="button"
                onClick={copy}
                whileHover={reduced ? undefined : { scale: 1.03, y: -1 }}
                whileTap={reduced ? undefined : { scale: 0.94 }}
                className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-primary/60 bg-card/90 px-3.5 text-sm font-semibold tracking-wider text-foreground shadow-sm transition-colors hover:border-primary hover:bg-primary-soft"
                aria-label={`Copy coupon code ${data.coupon_code}`}
              >
                {data.coupon_code}
                {copied ? (
                  <Check className="size-4 text-savings" />
                ) : (
                  <Copy className="size-4 text-muted-foreground" />
                )}
              </motion.button>
              <span aria-live="polite" className="sr-only">
                {copied ? "Coupon code copied" : ""}
              </span>
            </div>
          ) : null}

          {data.perk && (
            <p className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Truck className="size-4 text-primary" />
              {data.perk}
            </p>
          )}

          <p className="border-t border-primary/20 pt-2 text-[11px] text-muted-foreground">
            Predicted by a trained classifier from your browsing and purchase behaviour, not from
            a hand-written rule. The offer attached to each segment is a reviewable policy.
          </p>
        </CardContent>
      </Card>

      <div className="mt-4">
        <HabitGrid habits={data.habits} />
      </div>
    </motion.div>
  );
}

/**
 * How this shopper shops, in their own numbers.
 *
 * These are literally the model's input features rendered as words, so the
 * explanation and the prediction cannot drift apart. Nothing here is computed
 * in the browser.
 */
function HabitGrid({ habits }: { habits: PersonalizationResponse["habits"] }) {
  const reduced = useReducedMotion();
  if (!habits.length) return null;

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-foreground">
        <TrendingUp className="size-3.5 text-primary" /> Your shopping habits
      </p>
      <motion.div
        variants={listParent(habits.length)}
        initial={reduced ? false : "hidden"}
        animate="visible"
        className="grid grid-cols-2 gap-2 sm:grid-cols-3"
      >
        {habits.map((habit) => (
          <motion.div
            key={habit.label}
            variants={listChild}
            whileHover={reduced ? undefined : { y: -3 }}
            className="rounded-xl border border-border bg-card p-3"
            title={habit.hint}
          >
            <p className="tabular text-lg font-semibold text-foreground">{habit.value}</p>
            <p className="text-[11px] leading-tight text-muted-foreground">{habit.label}</p>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
