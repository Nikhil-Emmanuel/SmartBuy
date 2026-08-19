import {
  ArrowRight,
  Backpack,
  Compass,
  ListChecks,
  Scale,
  ShoppingBasket,
  Sparkles,
  Wallet,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const DEMO_SENTENCE =
  "I'm going for a 4-day winter trek in Manali, budget Rs 15,000, I'm a beginner, I already have trekking shoes and a backpack";

const STARTER_CHIPS = [
  "Setting up my first flat, budget Rs 40,000",
  "Waterproof trekking shoes under Rs 3,000",
  "3-day beach holiday in Goa, budget Rs 8,000",
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

export function LandingPage() {
  const navigate = useNavigate();

  function startWith(message: string) {
    navigate("/chat", { state: { initialMessage: message } });
  }

  return (
    <div className="relative overflow-hidden">
      <div className="aurora grid-faint absolute inset-x-0 top-0 -z-10 h-[640px]" />

      <section className="mx-auto max-w-5xl px-6 pb-20 pt-20 text-center sm:pt-28">
        <span className="animate-rise mx-auto mb-6 inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
          <Sparkles className="size-3.5 text-primary" />
          Goal-based shopping, not keyword search
        </span>

        <h1
          className="animate-rise font-display text-4xl leading-[1.1] text-foreground sm:text-6xl"
          style={{ animationDelay: "60ms" }}
        >
          Tell it your goal.
          <br />
          <span className="text-primary">It builds the shopping list.</span>
        </h1>

        <p
          className="animate-rise mx-auto mt-5 max-w-2xl text-balance text-base text-muted-foreground sm:text-lg"
          style={{ animationDelay: "120ms" }}
        >
          Skip the search bar. Describe what you&apos;re actually doing and SmartBuy AI works out
          everything you need, excludes what you already own, compares real options and fits the
          whole basket to your budget -- with every choice explained.
        </p>

        <div
          className="animate-rise mx-auto mt-9 max-w-2xl"
          style={{ animationDelay: "180ms" }}
        >
          <button
            onClick={() => startWith(DEMO_SENTENCE)}
            className="group flex w-full items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 text-left shadow-sm transition-all hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10"
          >
            <Backpack className="size-5 shrink-0 text-primary" />
            <span className="flex-1 text-sm text-foreground sm:text-base">
              &ldquo;{DEMO_SENTENCE}&rdquo;
            </span>
            <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
          </button>

          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            {STARTER_CHIPS.map((chip) => (
              <button
                key={chip}
                onClick={() => startWith(chip)}
                className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        <div
          className="animate-rise mt-8 flex flex-wrap items-center justify-center gap-3"
          style={{ animationDelay: "240ms" }}
        >
          <Button size="lg" onClick={() => navigate("/chat")}>
            <ShoppingBasket /> Start shopping
          </Button>
          <Button size="lg" variant="outline" onClick={() => navigate("/chat")}>
            Or search a specific product
          </Button>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
            <Card
              key={title}
              className="animate-rise p-5"
              style={{ animationDelay: `${280 + i * 60}ms` }}
            >
              <div className="mb-3 flex size-9 items-center justify-center rounded-lg bg-primary-soft text-primary">
                <Icon className="size-4.5" />
              </div>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-24">
        <Card className="flex flex-col items-center gap-3 bg-primary-soft/40 px-8 py-10 text-center">
          <p className="text-sm text-muted-foreground">
            The catalog is a curated, generated dataset for this demo -- prices and stock are
            simulated, and every screen says so where it matters. Nothing here claims to be a
            live marketplace feed.
          </p>
        </Card>
      </section>
    </div>
  );
}
