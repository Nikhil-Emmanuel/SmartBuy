import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  Compass,
  ListChecks,
  Scale,
  ShoppingBasket,
  Sparkles,
  Store,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { CountUp } from "@/components/shared/CountUp";
import { Reveal } from "@/components/shared/Reveal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useHealth, useMarketplaces } from "@/hooks/useProducts";
import { EASE_OUT, HOVER_LIFT, SPRING } from "@/lib/motion";

/**
 * The rotating prompts.
 *
 * These are the pitch: the point of the product is that any of these sentences
 * works, and a static example cannot make that argument. Whichever one is on
 * screen is the one the button submits -- an example you can't act on is a
 * screenshot, not a demo.
 */
const GOALS = [
  "I'm going for a 4-day winter trek in Manali, budget Rs 15,000, I'm a beginner, I already have trekking shoes and a backpack",
  "Setting up my first flat on a Rs 40,000 budget -- I have nothing except a mattress",
  "3-day beach holiday in Goa with friends, budget Rs 8,000",
  "Working from home 5 days a week and my back hurts, budget Rs 25,000",
];

const ROTATE_MS = 4200;

const STARTER_CHIPS = [
  "Waterproof trekking shoes under Rs 3,000",
  "Monsoon commute kit for a two-wheeler",
  "Gifts for a housewarming, Rs 5,000 total",
];

const HOW_IT_WORKS = [
  {
    icon: Compass,
    title: "Describe your goal",
    body: "Tell it what you're actually doing, not what to search for. “A 4-day winter trek in Manali” is enough to start.",
  },
  {
    icon: ListChecks,
    title: "It works out what you need",
    body: "A requirement checklist is derived from the goal, budget and what you already own -- nothing you're carrying gets duplicated.",
  },
  {
    icon: Scale,
    title: "Compares across marketplaces",
    body: "Every item is ranked on fit, quality, budget, reviews, delivery and deal value -- with the reasoning shown, not hidden.",
  },
  {
    icon: Wallet,
    title: "Fits the whole basket to budget",
    body: "A bundle optimizer picks the best combination under your budget, with a lower-cost and a premium alternative to switch to.",
  },
];

/** Hero children, staggered so the page assembles instead of appearing. */
const heroParent = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
const heroChild = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE_OUT } },
};

export function LandingPage() {
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  const health = useHealth();
  const marketplaces = useMarketplaces();
  const [index, setIndex] = useState(0);

  // Reduced motion stops the carousel outright rather than making it snap:
  // text that silently replaces itself is harder to read than text that moves.
  useEffect(() => {
    if (reduced) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % GOALS.length), ROTATE_MS);
    return () => clearInterval(timer);
  }, [reduced]);

  function startWith(message: string) {
    navigate("/chat", { state: { initialMessage: message } });
  }

  const goal = GOALS[index];

  return (
    <div className="relative overflow-hidden">
      <div className="aurora grid-faint absolute inset-x-0 top-0 -z-10 h-[640px]" />

      <motion.section
        variants={heroParent}
        initial={reduced ? false : "hidden"}
        animate="visible"
        className="mx-auto max-w-5xl px-6 pb-16 pt-20 text-center sm:pt-28"
      >
        <motion.span
          variants={heroChild}
          className="mx-auto mb-6 inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-muted-foreground shadow-sm"
        >
          <motion.span
            animate={reduced ? {} : { rotate: [0, 12, -8, 0], scale: [1, 1.15, 1] }}
            transition={{ duration: 2.4, repeat: Infinity, repeatDelay: 3, ease: EASE_OUT }}
          >
            <Sparkles className="size-3.5 text-primary" />
          </motion.span>
          Goal-based shopping, not keyword search
        </motion.span>

        <motion.h1
          variants={heroChild}
          className="font-display text-4xl leading-[1.1] text-foreground sm:text-6xl"
        >
          Tell it your goal.
          <br />
          <span className="text-primary">It builds the shopping list.</span>
        </motion.h1>

        <motion.p
          variants={heroChild}
          className="mx-auto mt-5 max-w-2xl text-balance text-base text-muted-foreground sm:text-lg"
        >
          Skip the search bar. Describe what you&apos;re actually doing and SmartBuy AI works out
          everything you need, excludes what you already own, compares real options and fits the
          whole basket to your budget -- with every choice explained.
        </motion.p>

        <motion.div variants={heroChild} className="mx-auto mt-9 max-w-2xl">
          <motion.button
            onClick={() => startWith(goal)}
            whileHover={reduced ? undefined : { scale: 1.01, y: -2 }}
            whileTap={reduced ? undefined : { scale: 0.99 }}
            transition={SPRING}
            className="group flex min-h-[5.5rem] w-full items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 text-left shadow-sm transition-colors hover:border-primary/50"
          >
            <span className="relative flex size-5 shrink-0 items-center justify-center">
              {/* A cursor blink: the affordance is "this is a text box you can talk into". */}
              <motion.span
                aria-hidden
                className="h-4 w-[2px] rounded-full bg-primary"
                animate={reduced ? {} : { opacity: [1, 1, 0, 0] }}
                transition={{ duration: 1.1, repeat: Infinity, times: [0, 0.5, 0.5, 1] }}
              />
            </span>

            <span className="min-w-0 flex-1">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={goal}
                  initial={reduced ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduced ? undefined : { opacity: 0, y: -8 }}
                  transition={{ duration: 0.28, ease: EASE_OUT }}
                  className="block text-sm text-foreground sm:text-base"
                >
                  &ldquo;{goal}&rdquo;
                </motion.span>
              </AnimatePresence>
            </span>

            <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
          </motion.button>

          {/* Which prompt is showing, and a way to pick one directly rather than
              waiting for the rotation to come back round. */}
          <div className="mt-3 flex items-center justify-center gap-1.5">
            {GOALS.map((g, i) => (
              <button
                key={g}
                onClick={() => setIndex(i)}
                aria-label={`Show example goal ${i + 1}`}
                aria-current={i === index}
                className="group flex h-6 items-center px-1"
              >
                <span
                  className={
                    i === index
                      ? "block h-1.5 w-6 rounded-full bg-primary transition-all"
                      : "block size-1.5 rounded-full bg-border transition-all group-hover:bg-primary/50"
                  }
                />
              </button>
            ))}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            {STARTER_CHIPS.map((chip, i) => (
              <motion.button
                key={chip}
                onClick={() => startWith(chip)}
                initial={reduced ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: reduced ? 0 : 0.5 + i * 0.07, duration: 0.35, ease: EASE_OUT }}
                whileHover={reduced ? undefined : { y: -2 }}
                className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {chip}
              </motion.button>
            ))}
          </div>
        </motion.div>

        <motion.div
          variants={heroChild}
          className="mt-8 flex flex-wrap items-center justify-center gap-3"
        >
          <Button size="lg" onClick={() => startWith(goal)}>
            <ShoppingBasket /> Start shopping
          </Button>
          <Button size="lg" variant="outline" onClick={() => navigate("/chat")}>
            Or search a specific product
          </Button>
        </motion.div>
      </motion.section>

      {/*
        Live figures, not marketing copy. Both come from the API, and the strip
        does not render at all if the API did not answer -- an invented number
        on the landing page is the easiest lie in the building to tell.
      */}
      {health.data && (
        <Reveal className="mx-auto mb-16 max-w-3xl px-6">
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4 rounded-2xl border border-border bg-card/60 px-6 py-5 backdrop-blur">
            <Stat
              value={health.data.catalog_size}
              format={(v) => v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              label="products in the catalog"
            />
            {/*
              `available` only. The registry also lists eBay, Amazon, Flipkart
              and Myntra, which are wired up but have no credentials and return
              nothing -- counting them here would claim we compare seven
              marketplaces when we search three.
            */}
            {marketplaces.data && (
              <Stat
                value={marketplaces.data.marketplaces.filter((m) => m.available).length}
                format={(v) => String(Math.round(v))}
                label="marketplaces searched"
                icon={Store}
              />
            )}
            <Stat value={8} format={(v) => String(Math.round(v))} label="scoring components" />
          </div>
        </Reveal>
      )}

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
            <Reveal key={title} delay={i * 0.07}>
              <motion.div whileHover={reduced ? undefined : HOVER_LIFT} className="h-full">
                <Card className="group h-full p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <motion.div
                      whileHover={reduced ? undefined : { rotate: -8, scale: 1.08 }}
                      transition={SPRING}
                      className="flex size-9 items-center justify-center rounded-lg bg-primary-soft text-primary"
                    >
                      <Icon className="size-4.5" />
                    </motion.div>
                    <span className="tabular text-xs font-semibold text-muted-foreground">
                      0{i + 1}
                    </span>
                  </div>
                  <h3 className="mb-1.5 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
                  {/* Progress rail: draws itself as the card arrives, so the four
                      cards read as a sequence rather than four unrelated boxes. */}
                  <motion.div
                    aria-hidden
                    className="mt-4 h-0.5 origin-left rounded-full bg-primary/30"
                    initial={reduced ? false : { scaleX: 0 }}
                    whileInView={{ scaleX: 1 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.6, ease: EASE_OUT, delay: 0.15 + i * 0.07 }}
                  />
                </Card>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-24">
        <Reveal>
          <Card className="flex flex-col items-center gap-3 bg-primary-soft/40 px-8 py-10 text-center">
            <p className="text-sm text-muted-foreground">
              The catalog is a curated, generated dataset for this demo -- prices and stock are
              simulated, and every screen says so where it matters. Nothing here claims to be a
              live marketplace feed.
            </p>
          </Card>
        </Reveal>
      </section>
    </div>
  );
}

function Stat({
  value,
  format,
  label,
  icon: Icon,
}: {
  value: number;
  format: (v: number) => string;
  label: string;
  icon?: typeof Store;
}) {
  return (
    <div className="text-center">
      <p className="flex items-center justify-center gap-1.5 font-display text-2xl text-foreground sm:text-3xl">
        {Icon && <Icon className="size-5 text-primary" />}
        <CountUp value={value} format={format} duration={1.1} />
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
