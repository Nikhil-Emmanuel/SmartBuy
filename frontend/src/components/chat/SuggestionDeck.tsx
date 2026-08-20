/**
 * The options tray that never goes away.
 *
 * A blank chat box invites questions the catalog cannot answer -- "mobile"
 * being the one that actually happened, since we stock no phones. The fix is
 * not a cleverer error message, it is to keep answerable options on screen at
 * all times so guessing is never the fastest path.
 *
 * Everything here comes from `/api/suggestions`, which reads the knowledge base
 * and counts the products table. Nothing is hard-coded in this file, which is
 * what guarantees an option on screen is an option we can serve.
 *
 * The text box stays. This tray is the fast path, not a cage: "waterproof
 * shoes under Rs 3,000" is a legitimate thing to type and half the product's
 * stated scope.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Compass, Layers, Sparkles } from "lucide-react";
import { useState } from "react";

import { useSuggestions } from "@/hooks/useChat";
import { EASE_OUT, listChild, listParent } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { Suggestion } from "@/types/api";

type Tab = "goals" | "categories";

export function SuggestionDeck({
  onSelect,
  disabled,
  agentChips,
}: {
  onSelect: (message: string) => void;
  disabled?: boolean;
  /** Chips the agent asked for this turn. They lead, because they answer its question. */
  agentChips?: string[];
}) {
  const reduced = useReducedMotion();
  const { data } = useSuggestions();
  const [tab, setTab] = useState<Tab>("goals");

  if (!data) return null;

  const items: Suggestion[] = tab === "goals" ? data.goals : data.categories;
  const hasAgentChips = !!agentChips?.length;

  return (
    <div className="space-y-2.5">
      <AnimatePresence initial={false}>
        {hasAgentChips && (
          <motion.div
            key="agent-chips"
            initial={reduced ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={reduced ? undefined : { opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-primary">
              <Sparkles className="size-3" /> Answer this
            </p>
            <div className="flex flex-wrap gap-1.5">
              {agentChips!.map((chip) => (
                <motion.button
                  key={chip}
                  type="button"
                  disabled={disabled}
                  onClick={() => onSelect(chip)}
                  whileHover={reduced || disabled ? undefined : { y: -2 }}
                  whileTap={reduced || disabled ? undefined : { scale: 0.97 }}
                  className="min-h-9 rounded-full border border-primary/40 bg-primary-soft px-3.5 text-xs font-medium text-primary transition-colors hover:bg-primary hover:text-primary-foreground disabled:opacity-50"
                >
                  {chip}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center gap-1">
        <TabButton active={tab === "goals"} onClick={() => setTab("goals")} icon={Compass}>
          Plan a goal
        </TabButton>
        <TabButton
          active={tab === "categories"}
          onClick={() => setTab("categories")}
          icon={Layers}
        >
          Browse what we stock
        </TabButton>
      </div>

      <motion.div
        key={tab}
        variants={listParent(items.length)}
        initial={reduced ? false : "hidden"}
        animate="visible"
        className="flex gap-2 overflow-x-auto pb-1"
      >
        {items.map((item) => (
          <motion.button
            key={item.label}
            type="button"
            variants={listChild}
            disabled={disabled}
            onClick={() => onSelect(item.message)}
            whileHover={reduced || disabled ? undefined : { y: -3 }}
            whileTap={reduced || disabled ? undefined : { scale: 0.98 }}
            className="min-h-[3.25rem] shrink-0 rounded-xl border border-border bg-card px-3.5 py-2 text-left transition-colors hover:border-primary/50 disabled:opacity-50"
          >
            <span className="block text-xs font-medium text-foreground">{item.label}</span>
            {item.detail && (
              <span className="block text-[11px] text-muted-foreground">{item.detail}</span>
            )}
          </motion.button>
        ))}
      </motion.div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Compass;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "relative flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium transition-colors",
        active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className="size-3.5" />
      {children}
      {active && (
        <motion.span
          layoutId="suggestion-tab"
          className="absolute inset-x-1 -bottom-0.5 h-0.5 rounded-full bg-primary"
          transition={{ type: "spring", stiffness: 400, damping: 32 }}
        />
      )}
    </button>
  );
}
