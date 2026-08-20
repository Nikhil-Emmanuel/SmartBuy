/**
 * A marquee of the catalog's real categories whose direction and speed are
 * linked to scroll velocity.
 *
 * Same source as the chat's suggestion tray (`/api/suggestions`), so the
 * landing page can only advertise a category the catalog actually stocks --
 * and the count next to each name is the live row count, not copy.
 *
 * The motion is the documented velocity-linked recipe: a constant base drift,
 * plus the smoothed scroll velocity added on top, with the sign of the
 * velocity flipping which way the row travels. Scrolling up runs it backwards.
 */

import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
  useTransform,
  wrap,
} from "framer-motion";
import { useRef } from "react";
import { useNavigate } from "react-router-dom";

import { useSuggestions } from "@/hooks/useChat";
import { useScrollVelocityFactor } from "@/lib/scrollVelocity";
import type { Suggestion } from "@/types/api";

/** Four copies of the row, so wrapping one quarter of the track is seamless. */
const COPIES = 4;

export function CategoryMarquee() {
  const { data } = useSuggestions();
  const navigate = useNavigate();
  const categories = data?.categories ?? [];

  // Nothing to advertise until the catalog answers. A marquee of placeholders
  // would be inventing inventory.
  if (categories.length === 0) return null;

  const pick = (suggestion: Suggestion) =>
    navigate("/chat", { state: { initialMessage: suggestion.message } });

  return (
    <section className="border-y border-border bg-card/40 py-10">
      <div className="mx-auto mb-6 max-w-2xl px-6 text-center">
        <h2 className="font-display text-2xl text-foreground sm:text-3xl">
          Everything the catalog actually stocks
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Live counts, straight from the database. Pick one to start browsing — the row moves
          with you as you scroll.
        </p>
      </div>

      <div className="space-y-3">
        <MarqueeRow items={categories} baseVelocity={26} onPick={pick} />
        <MarqueeRow items={[...categories].reverse()} baseVelocity={-26} onPick={pick} />
      </div>
    </section>
  );
}

function MarqueeRow({
  items,
  baseVelocity,
  onPick,
}: {
  items: Suggestion[];
  baseVelocity: number;
  onPick: (suggestion: Suggestion) => void;
}) {
  const reduced = useReducedMotion();
  const factor = useScrollVelocityFactor();
  const baseX = useMotionValue(0);

  // The track holds four identical copies, so travelling 25% of it lands on an
  // identical frame -- that is what makes the wrap invisible.
  const x = useTransform(baseX, (value) => `${wrap(-100 / COPIES, 0, value)}%`);

  const direction = useRef(1);

  useAnimationFrame((_, delta) => {
    if (reduced) return;
    let moveBy = direction.current * baseVelocity * (delta / 1000);

    // Scroll direction wins over the base drift: reversing the row is the
    // clearest possible signal that the motion is answering the user.
    const velocity = factor.get();
    if (velocity < 0) direction.current = -1;
    else if (velocity > 0) direction.current = 1;

    moveBy += moveBy * velocity;
    baseX.set(baseX.get() + moveBy);
  });

  return (
    <div className="flex overflow-hidden">
      <motion.div className="flex shrink-0 gap-3 pr-3" style={reduced ? undefined : { x }}>
        {Array.from({ length: COPIES }, (_, copy) =>
          items.map((item) => (
            <button
              key={`${copy}-${item.label}`}
              type="button"
              onClick={() => onPick(item)}
              // Only the first copy is real to assistive tech and to the tab
              // order; the other three exist purely to fill the track.
              aria-hidden={copy > 0}
              tabIndex={copy > 0 ? -1 : 0}
              className="inline-flex min-h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-border bg-card px-4 text-sm text-foreground shadow-sm transition-colors hover:border-primary/50 hover:bg-primary-soft"
            >
              {item.label}
              {item.detail && (
                <span className="tabular text-xs text-muted-foreground">{item.detail}</span>
              )}
            </button>
          )),
        )}
      </motion.div>
    </div>
  );
}
