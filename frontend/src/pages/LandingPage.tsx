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
          className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-card/90 px-4 py-2 text-xs font-semibold text-foreground shadow-floating backdrop-blur-xl"
        >
          <motion.span
            animate={reduced ? {} : { rotate: [0, 15, -10, 0], scale: [1, 1.2, 1] }}
            transition={{ duration: 2.4, repeat: Infinity, repeatDelay: 2.5, ease: EASE_OUT }}
          >
            <Sparkles className="text-brass size-4" />
          </motion.span>
          Goal-based shopping, not keyword search
        </motion.span>

        <motion.h1
          variants={heroChild}
          className="font-display text-5xl leading-[1.05] tracking-tight text-foreground sm:text-7xl lg:text-8xl"
        >
          Tell it your goal.
          <br />
          <span className="landing-headline-accent">It builds the shopping list.</span>
        </motion.h1>

        <motion.p
          variants={heroChild}
          className="mx-auto mt-6 max-w-2xl text-balance text-base text-muted-foreground sm:text-xl"
        >
          Skip the search bar. Describe what you&apos;re actually doing and SmartBuy AI works out
          everything you need, excludes what you already own, compares real options and fits the
          whole basket to your budget -- with every choice explained.
        </motion.p>

        <motion.div variants={heroChild} className="mx-auto mt-10 max-w-2xl">
          <motion.button
            onClick={() => goal && startWith(goal.message)}
            disabled={!goal}
            whileHover={reduced || !goal ? undefined : { scale: 1.015, y: -3 }}
            whileTap={reduced || !goal ? undefined : { scale: 0.985 }}
            transition={SPRING}
            className="landing-lift glow-card-hero group relative flex min-h-[6rem] w-full items-center gap-3 overflow-hidden rounded-3xl border border-primary/40 bg-card/95 px-6 py-5 text-left shadow-floating-lg backdrop-blur-xl transition-all duration-300 hover:border-primary/70 disabled:cursor-default"
          >
            <span aria-hidden className="landing-edge absolute inset-y-0 left-0 w-[4px] opacity-90" />

            <span className="relative flex size-6 shrink-0 items-center justify-center">
              <motion.span
                aria-hidden
                className="h-5 w-[2.5px] rounded-full bg-primary"
                animate={reduced ? {} : { opacity: [1, 1, 0, 0] }}
                transition={{ duration: 1.1, repeat: Infinity, times: [0, 0.5, 0.5, 1] }}
              />
            </span>

            <span className="min-w-0 flex-1">
              {goal ? (
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={goal.message}
                    initial={reduced ? false : { opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduced ? undefined : { opacity: 0, y: -10 }}
                    transition={{ duration: 0.28, ease: EASE_OUT }}
                    className="block text-base font-medium text-foreground sm:text-lg"
                  >
                    &ldquo;{goal.message}&rdquo;
                  </motion.span>
                </AnimatePresence>
              ) : (
                <span className="block space-y-2" aria-label="Loading an example goal">
                  <span className="block h-4 w-4/5 rounded-full bg-secondary" />
                  <span className="block h-4 w-2/5 rounded-full bg-secondary" />
                </span>
              )}
            </span>

            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary transition-transform group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground">
              <ArrowRight className="size-5 shrink-0" />
            </div>
          </motion.button>

          <div
            className="mt-5 flex flex-wrap items-center justify-center gap-2.5"
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
                    delay: reduced ? 0 : 0.4 + i * 0.06,
                    duration: 0.35,
                    ease: EASE_OUT,
                  }}
                  whileHover={reduced ? undefined : { y: -3, scale: 1.03 }}
                  whileTap={reduced ? undefined : { scale: 0.96 }}
                  className={cn(
                    "relative inline-flex min-h-11 items-center gap-1.5 rounded-full border px-4 text-xs font-medium shadow-sm transition-all duration-200",
                    active
                      ? "border-primary bg-primary-soft/90 text-foreground shadow-floating"
                      : "border-border/80 bg-card/90 text-muted-foreground backdrop-blur-md hover:border-primary/50 hover:text-foreground",
                  )}
                >
                  {active && (
                    <motion.span
                      layoutId="landing-goal-active"
                      className="absolute inset-0 -z-10 rounded-full bg-primary-soft ring-1 ring-primary/40"
                      transition={SPRING}
                    />
                  )}
                  {suggestion.label}
                  {suggestion.detail && (
                    <span className="tabular text-[11px] font-semibold text-primary/80">
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
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
        >
          <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.95 }}>
            <Button size="lg" className="h-12 px-6 shadow-floating text-base gap-2" onClick={() => goal && startWith(goal.message)} disabled={!goal}>
              <ShoppingBasket className="size-5" /> Start shopping
            </Button>
          </motion.div>
          <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.95 }}>
            <Button size="lg" variant="outline" className="h-12 px-6 text-base" onClick={() => navigate("/chat")}>
              Or search a specific product
            </Button>
          </motion.div>
        </motion.div>

        {/* Live Interactive Plan Preview Card */}
        <motion.div
          variants={heroChild}
          className="mx-auto mt-14 max-w-3xl"
        >
          <div className="landing-ring landing-lift-lg rounded-3xl p-px">
            <div className="rounded-[calc(var(--radius)+14px)] bg-card/90 p-6 text-left shadow-floating-lg backdrop-blur-xl sm:p-7">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-9 items-center justify-center rounded-full bg-primary-soft text-primary">
                    <Sparkles className="size-4.5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-primary">Live Sample Plan</p>
                    <h3 className="text-base font-semibold text-foreground">4-Day Winter Trek in Manali</h3>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-savings-soft px-3 py-1 text-xs font-semibold text-savings border border-savings/30">
                    Budget Fit: ₹18,500
                  </span>
                  <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary border border-primary/30">
                    96% Fit Score
                  </span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="flex items-center gap-3 rounded-xl border border-border/70 bg-background/60 p-3 shadow-sm transition-all hover:border-primary/40">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary font-bold text-xs">
                    98%
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-1 text-xs font-semibold text-foreground">Waterproof Down Jacket</p>
                    <p className="text-[11px] text-muted-foreground">Quechua · ₹4,299</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-xl border border-border/70 bg-background/60 p-3 shadow-sm transition-all hover:border-primary/40">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-savings-soft text-savings font-bold text-xs">
                    95%
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-1 text-xs font-semibold text-foreground">Trekking Boots (Grip 4)</p>
                    <p className="text-[11px] text-muted-foreground">Forclaz · ₹6,999</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-xl border border-border/70 bg-background/60 p-3 shadow-sm transition-all hover:border-primary/40">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary font-bold text-xs">
                    94%
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-1 text-xs font-semibold text-foreground">0°C Sleeping Bag</p>
                    <p className="text-[11px] text-muted-foreground">TripPole · ₹3,499</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.section>

      {health.data && (
        <Reveal className="mx-auto mb-20 max-w-4xl px-6">
          <div className="landing-ring landing-lift-lg rounded-3xl p-px">
            <div className="grid grid-cols-1 gap-y-6 rounded-[calc(var(--radius)+14px)] bg-card/90 px-8 py-8 shadow-floating-lg backdrop-blur-xl sm:grid-cols-3 sm:gap-y-0 sm:divide-x sm:divide-border/60">
              <Stat
                value={health.data.catalog_size}
                format={(v) => v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                label="products in the catalog"
              />
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
        <Reveal className="mb-12 text-center">
          <h2 className="font-display text-3xl text-foreground sm:text-4xl">
            Four steps, none of them a search box
          </h2>
          <div aria-hidden className="landing-rule mx-auto mt-6 h-px w-full max-w-xl" />
        </Reveal>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
            <Reveal key={title} delay={i * 0.07}>
              <motion.div whileHover={reduced ? undefined : HOVER_LIFT} className="h-full">
                <Card className="group relative h-full overflow-hidden rounded-2xl border border-border/80 bg-card/90 p-6 shadow-sm backdrop-blur-md transition-all duration-300 hover:border-primary/50 hover:shadow-floating-lg">
                  <span
                    aria-hidden
                    className="text-brass pointer-events-none absolute -right-1 -top-5 font-display text-[5.5rem] leading-none opacity-[0.12] transition-opacity group-hover:opacity-[0.22]"
                  >
                    0{i + 1}
                  </span>

                  <motion.div
                    whileHover={reduced ? undefined : { rotate: -8, scale: 1.1 }}
                    transition={SPRING}
                    className="mb-4 flex size-11 items-center justify-center rounded-xl bg-primary-soft text-primary shadow-sm"
                  >
                    <Icon className="size-5" />
                  </motion.div>

                  <h3 className="mb-2 text-base font-semibold text-foreground">{title}</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
                  <motion.div
                    aria-hidden
                    className="landing-rail mt-5 h-1 origin-left rounded-full"
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
          <Card className="border-brass-soft glow-card-hero relative overflow-hidden rounded-3xl bg-accent/40 px-8 py-12 text-center backdrop-blur-xl">
            <p className="mx-auto max-w-2xl text-sm leading-relaxed text-foreground/90 font-medium">
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
