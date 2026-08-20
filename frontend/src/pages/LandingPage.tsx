import {
  AnimatePresence,
  motion,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion";
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

import { CategoryMarquee } from "@/components/landing/CategoryMarquee";
import { ShoppingParticles } from "@/components/landing/ShoppingParticles";
import { VelocityShowcase } from "@/components/landing/VelocityShowcase";
import { CountUp } from "@/components/shared/CountUp";
import { Reveal } from "@/components/shared/Reveal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useSuggestions } from "@/hooks/useChat";
import { useHealth, useMarketplaces } from "@/hooks/useProducts";
import { EASE_OUT, HOVER_LIFT, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

import "./landing.css";

/**
 * The rotating prompts come from `/api/suggestions`, which reads the YAML
 * knowledge base -- so the hero can only demo a goal the planner can actually
 * plan.
 *
 * This used to be four sentences written here. Two of them ("beach holiday in
 * Goa", "working from home and my back hurts") had no matching goal in the
 * knowledge base at all: the headline example on the landing page was a goal
 * the agent would have had to fall back on generic search for. Sourcing them
 * makes that mismatch impossible rather than merely fixed.
 */
const ROTATE_MS = 4200;

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
  const suggestions = useSuggestions();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  const goals = suggestions.data?.goals ?? [];
  const goal = goals.length > 0 ? goals[index % goals.length] : null;

  /*
    Scroll-linked motion. Three layers move at three speeds, which is the whole
    trick: the further back a layer is, the less it travels, and the eye reads
    that difference as depth. The content itself never moves -- parallaxing text
    while someone is trying to read it is the version of this effect that makes
    people motion-sick.
  */
  const { scrollY, scrollYProgress } = useScroll();
  const meshY = useTransform(scrollY, [0, 900], [0, 170]);
  const gridY = useTransform(scrollY, [0, 900], [0, 90]);
  const particleY = useTransform(scrollY, [0, 900], [0, 300]);
  // The spring is what keeps the progress bar from twitching on a trackpad.
  // Under reduced motion it is bound straight to the raw value instead: the
  // bar still has to be accurate, it just stops easing to get there.
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 140,
    damping: 26,
    restDelta: 0.001,
  });
  const progress = reduced ? scrollYProgress : smoothProgress;

  // Reduced motion stops the carousel outright rather than making it snap:
  // text that silently replaces itself is harder to read than text that moves.
  // It also stops while a chip is hovered, because the user is reading that one.
  useEffect(() => {
    if (reduced || paused || goals.length < 2) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % goals.length), ROTATE_MS);
    return () => clearInterval(timer);
  }, [reduced, paused, goals.length]);

  function startWith(message: string) {
    navigate("/chat", { state: { initialMessage: message } });
  }

  return (
    /*
      `landing-theme` is the palette override and it stops here: every token in
      `landing.css` is scoped to this element, so nothing outside this page
      changes colour. See the header of that file for the measured contrast.
    */
    <div className="landing-theme relative overflow-hidden bg-background text-foreground">
      {/* How far down the page you are. The one piece of scroll motion that is
          information rather than decoration, so it survives reduced motion. */}
      <motion.div
        aria-hidden
        style={{ scaleX: progress }}
        className="landing-progress pointer-events-none fixed inset-x-0 top-0 z-50 h-[3px] origin-left"
      />

      {/* Backdrop, back to front: colour wash, structural grid, drifting marks. */}
      <motion.div
        aria-hidden
        style={reduced ? undefined : { y: meshY }}
        className="landing-mesh landing-grain pointer-events-none absolute inset-x-0 -top-24 -z-20 h-[860px]"
      />
      <motion.div
        aria-hidden
        style={reduced ? undefined : { y: gridY }}
        className="landing-grid pointer-events-none absolute inset-x-0 top-0 -z-20 h-[700px]"
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[900px]">
        <ShoppingParticles parallax={reduced ? undefined : particleY} />
      </div>

      <motion.section
        variants={heroParent}
        initial={reduced ? false : "hidden"}
        animate="visible"
        className="mx-auto max-w-5xl px-6 pb-16 pt-20 text-center sm:pt-28"
      >
        <motion.span
          variants={heroChild}
          className="mx-auto mb-6 inline-flex items-center gap-1.5 rounded-full border border-border bg-card/80 px-3.5 py-1.5 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur"
        >
          <motion.span
            animate={reduced ? {} : { rotate: [0, 12, -8, 0], scale: [1, 1.15, 1] }}
            transition={{ duration: 2.4, repeat: Infinity, repeatDelay: 3, ease: EASE_OUT }}
          >
            <Sparkles className="text-brass size-3.5" />
          </motion.span>
          Goal-based shopping, not keyword search
        </motion.span>

        <motion.h1
          variants={heroChild}
          className="font-display text-4xl leading-[1.08] tracking-tight text-foreground sm:text-6xl"
        >
          Tell it your goal.
          <br />
          {/* Indigo into brass across the promise line: the palette's two
              voices in the one sentence that has to land. */}
          <span className="landing-headline-accent">It builds the shopping list.</span>
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
            onClick={() => goal && startWith(goal.message)}
            disabled={!goal}
            whileHover={reduced || !goal ? undefined : { scale: 1.01, y: -2 }}
            whileTap={reduced || !goal ? undefined : { scale: 0.99 }}
            transition={SPRING}
            className="landing-lift group relative flex min-h-[5.5rem] w-full items-center gap-3 overflow-hidden rounded-2xl border border-border bg-card/90 px-5 py-4 text-left backdrop-blur transition-colors hover:border-primary/50 disabled:cursor-default"
          >
            {/* A hairline of the gradient down the leading edge -- enough to tie
                the input to the headline without another block of colour. */}
            <span aria-hidden className="landing-edge absolute inset-y-0 left-0 w-[3px] opacity-75" />

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
              {goal ? (
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={goal.message}
                    initial={reduced ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduced ? undefined : { opacity: 0, y: -8 }}
                    transition={{ duration: 0.28, ease: EASE_OUT }}
                    className="block text-sm text-foreground sm:text-base"
                  >
                    &ldquo;{goal.message}&rdquo;
                  </motion.span>
                </AnimatePresence>
              ) : (
                // Before the knowledge base has answered there is no example to
                // show. A placeholder sentence here would be a fabricated one.
                <span className="block space-y-2" aria-label="Loading an example goal">
                  <span className="block h-3.5 w-4/5 rounded-full bg-secondary" />
                  <span className="block h-3.5 w-2/5 rounded-full bg-secondary" />
                </span>
              )}
            </span>

            <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
          </motion.button>

          {/*
            The goals the knowledge base can actually plan, with their real item
            counts -- these replaced three search phrases written by hand here,
            which meant the landing page could offer a starting point the
            planner had no plan for.

            Hovering one previews it in the box above and stops the rotation;
            clicking starts the chat with it. Hover-preview also means the row
            doubles as the carousel's position indicator, so there is no
            separate strip of dots to keep in sync.
          */}
          <div
            className="mt-4 flex flex-wrap items-center justify-center gap-2"
            onMouseLeave={() => setPaused(false)}
          >
            {goals.map((suggestion, i) => {
              const active = goal?.message === suggestion.message;
              return (
                <motion.button
                  key={suggestion.label}
                  onClick={() => startWith(suggestion.message)}
                  onMouseEnter={() => {
                    setIndex(i);
                    setPaused(true);
                  }}
                  onFocus={() => {
                    setIndex(i);
                    setPaused(true);
                  }}
                  onBlur={() => setPaused(false)}
                  aria-current={active}
                  initial={reduced ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    delay: reduced ? 0 : 0.5 + i * 0.07,
                    duration: 0.35,
                    ease: EASE_OUT,
                  }}
                  whileHover={reduced ? undefined : { y: -2 }}
                  className={cn(
                    // min-h-11 = 44px, the touch-target floor. These chips are
                    // the primary way into the product on a phone, so they are
                    // the last thing that should be a 30px sliver.
                    "relative inline-flex min-h-11 items-center gap-1.5 rounded-full border px-4 text-xs transition-colors",
                    active
                      ? "border-primary/50 text-foreground"
                      : "border-border bg-card/80 text-muted-foreground backdrop-blur hover:text-foreground",
                  )}
                >
                  {/* One shared element, so the highlight travels between chips
                      instead of blinking off one and on at the next. */}
                  {active && (
                    <motion.span
                      layoutId="landing-goal-active"
                      className="absolute inset-0 -z-10 rounded-full bg-primary-soft"
                      transition={SPRING}
                    />
                  )}
                  {suggestion.label}
                  {suggestion.detail && (
                    <span className="tabular text-[11px] text-muted-foreground/70">
                      {suggestion.detail}
                    </span>
                  )}
                </motion.button>
              );
            })}
          </div>
        </motion.div>

        <motion.div
          variants={heroChild}
          className="mt-8 flex flex-wrap items-center justify-center gap-3"
        >
          <Button size="lg" onClick={() => goal && startWith(goal.message)} disabled={!goal}>
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
        <Reveal className="mx-auto mb-20 max-w-3xl px-6">
          <div className="landing-ring landing-lift-lg rounded-2xl p-px">
            <div className="grid grid-cols-1 gap-y-6 rounded-[calc(var(--radius)+9px)] bg-card/85 px-6 py-6 backdrop-blur sm:grid-cols-3 sm:gap-y-0 sm:divide-x sm:divide-border">
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
          </div>
        </Reveal>
      )}

      <VelocityShowcase />

      <section className="mx-auto max-w-6xl px-6 pb-20">
        <Reveal className="mb-10 text-center">
          <h2 className="font-display text-2xl text-foreground sm:text-3xl">
            Four steps, none of them a search box
          </h2>
          <div aria-hidden className="landing-rule mx-auto mt-5 h-px w-full max-w-xl" />
        </Reveal>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
            <Reveal key={title} delay={i * 0.07}>
              <motion.div whileHover={reduced ? undefined : HOVER_LIFT} className="h-full">
                <Card className="group relative h-full overflow-hidden p-5">
                  {/* The step number as a watermark rather than a label: it
                      orders the cards without taking a line of copy. */}
                  <span
                    aria-hidden
                    className="text-brass pointer-events-none absolute -right-2 -top-4 font-display text-[5rem] leading-none opacity-[0.10] transition-opacity group-hover:opacity-[0.18]"
                  >
                    {i + 1}
                  </span>

                  <motion.div
                    whileHover={reduced ? undefined : { rotate: -8, scale: 1.08 }}
                    transition={SPRING}
                    className="mb-3 flex size-9 items-center justify-center rounded-lg bg-primary-soft text-primary"
                  >
                    <Icon className="size-4.5" />
                  </motion.div>

                  <h3 className="mb-1.5 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
                  {/* Progress rail: draws itself as the card arrives, so the four
                      cards read as a sequence rather than four unrelated boxes. */}
                  <motion.div
                    aria-hidden
                    className="landing-rail mt-4 h-0.5 origin-left rounded-full"
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

      <CategoryMarquee />

      <section className="mx-auto max-w-4xl px-6 pb-24 pt-16">
        <Reveal>
          <Card className="border-brass-soft relative overflow-hidden bg-accent/50 px-8 py-10 text-center">
            <p className="mx-auto max-w-2xl text-sm leading-relaxed text-foreground/80">
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
      <p className="flex items-center justify-center gap-1.5 font-display text-3xl text-foreground sm:text-4xl">
        {Icon && <Icon className="text-brass size-5" />}
        <CountUp value={value} format={format} duration={1.1} />
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
