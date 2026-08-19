import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check, Circle, Info, Pencil } from "lucide-react";
import { useState } from "react";

import { CountUp } from "@/components/shared/CountUp";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { percent, slotLabel, slotValue } from "@/lib/format";
import { FADE, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { Assumption, Slots } from "@/types/api";

const DISPLAY_ORDER: (keyof Slots)[] = [
  "activity",
  "location",
  "duration_days",
  "people_count",
  "experience_level",
  "budget_total",
  "camping",
  "existing_items",
];

export function SlotSidebar({
  slots,
  collected,
  missing,
  assumptions,
  progress,
  onUpdateBudget,
  updatingBudget,
}: {
  slots: Slots;
  collected: string[];
  missing: string[];
  assumptions: Assumption[];
  progress: number;
  onUpdateBudget?: (value: number) => void;
  updatingBudget?: boolean;
}) {
  const [editingBudget, setEditingBudget] = useState(false);
  const [budgetInput, setBudgetInput] = useState(String(slots.budget_total ?? ""));
  const reduced = useReducedMotion();

  const known = new Set(collected);
  const relevant = DISPLAY_ORDER.filter(
    (key) => known.has(key) || missing.includes(key) || slotHasValue(slots[key]),
  );

  function submitBudget() {
    const value = Number(budgetInput.replace(/[^\d]/g, ""));
    if (value > 0 && onUpdateBudget) onUpdateBudget(value);
    setEditingBudget(false);
  }

  return (
    <Card className="sticky top-24">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Your goal so far</CardTitle>
        <div className="flex items-center gap-2 pt-1">
          <Progress value={Math.round(progress * 100)} className="h-1.5 flex-1" />
          <CountUp
            value={progress}
            format={(v) => percent(v)}
            duration={0.5}
            className="text-xs font-medium text-muted-foreground"
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {slots.goal_text && (
          <motion.p
            key={slots.goal_text}
            initial={reduced ? false : { opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={FADE}
            className="rounded-lg bg-muted px-3 py-2 text-xs italic leading-relaxed text-muted-foreground"
          >
            &ldquo;{slots.goal_text}&rdquo;
          </motion.p>
        )}

        <ul className="space-y-2">
          {relevant.map((key) => {
            const isKnown = known.has(key) || slotHasValue(slots[key]);
            const isBudget = key === "budget_total";
            return (
              <motion.li
                key={key}
                layout={!reduced}
                initial={reduced ? false : { opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={FADE}
                className="flex items-start gap-2 text-sm"
              >
                {/*
                  The tick pops when a slot flips from unknown to known. This is
                  the one piece of motion on this panel that is doing real work:
                  the sidebar sits beside the conversation, and without it the
                  moment a sentence filled something in is easy to miss.
                */}
                <AnimatePresence mode="wait" initial={false}>
                  {isKnown ? (
                    <motion.span
                      key="known"
                      initial={reduced ? false : { scale: 0.4, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={SPRING}
                      className="mt-0.5 shrink-0"
                    >
                      <Check className="size-3.5 text-savings" />
                    </motion.span>
                  ) : (
                    <motion.span key="unknown" className="mt-0.5 shrink-0">
                      <Circle className="size-3.5 text-muted-foreground/50" />
                    </motion.span>
                  )}
                </AnimatePresence>
                <span className="w-24 shrink-0 text-xs text-muted-foreground">
                  {slotLabel(key)}
                </span>
                {isBudget && editingBudget ? (
                  <div className="flex flex-1 items-center gap-1">
                    <Input
                      value={budgetInput}
                      onChange={(e) => setBudgetInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && submitBudget()}
                      className="h-7 px-2 text-xs"
                      autoFocus
                    />
                    <Button size="sm" className="h-7 px-2 text-xs" onClick={submitBudget}>
                      Save
                    </Button>
                  </div>
                ) : (
                  <span
                    className={cn(
                      "flex-1 truncate text-xs font-medium",
                      isKnown ? "text-foreground" : "text-muted-foreground/60",
                    )}
                  >
                    {slotValue(key, slots[key])}
                  </span>
                )}
                {isBudget && !editingBudget && onUpdateBudget && (
                  <button
                    onClick={() => {
                      setBudgetInput(String(slots.budget_total ?? ""));
                      setEditingBudget(true);
                    }}
                    disabled={updatingBudget}
                    className="text-muted-foreground/60 hover:text-primary"
                    aria-label="Edit budget"
                  >
                    <Pencil className="size-3" />
                  </button>
                )}
              </motion.li>
            );
          })}
        </ul>

        {assumptions.length > 0 && (
          <>
            <Separator />
            <div>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Info className="size-3.5" />
                Assumed for you
              </p>
              <ul className="space-y-1.5">
                {assumptions.map((a, i) => (
                  <motion.li
                    key={a.slot}
                    initial={reduced ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ ...FADE, delay: reduced ? 0 : i * 0.05 }}
                    className="rounded-lg bg-info-soft/60 px-2.5 py-1.5 text-xs"
                  >
                    <span className="font-medium text-info">
                      {slotLabel(a.slot)}: {a.value}
                    </span>
                    <p className="text-muted-foreground">{a.basis}</p>
                  </motion.li>
                ))}
              </ul>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function slotHasValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}
