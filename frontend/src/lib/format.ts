/**
 * Formatting helpers.
 *
 * Every money value from the API is an integer number of rupees. Nothing here
 * does arithmetic on prices beyond what it is handed — totals, savings and
 * deltas are computed in Python and rendered verbatim.
 */

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const COMPACT = new Intl.NumberFormat("en-IN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function rupees(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return INR.format(value);
}

/** Signed, for price deltas: "−₹1,700" / "+₹450". */
export function rupeeDelta(value: number): string {
  if (value === 0) return "₹0";
  const sign = value > 0 ? "+" : "−";
  return `${sign}${INR.format(Math.abs(value))}`;
}

export function compactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return COMPACT.format(value);
}

/** 0.94 → "94%". Scores and rates arrive as [0,1] floats. */
export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function points(value: number): string {
  return value.toFixed(1).replace(/\.0$/, "");
}

export function rating(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(1);
}

export function deliveryLabel(days: number | null | undefined): string {
  if (days === null || days === undefined) return "Delivery unknown";
  if (days <= 0) return "Same day";
  if (days === 1) return "Next day";
  return `${days} days`;
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/** "MARKET_A" → "Market A". Sources are simulated marketplaces, not real ones. */
export function sourceLabel(source: string): string {
  return titleCase(source.toLowerCase());
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((Date.now() - then) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 7],
    ["week", 4.35],
    ["month", 12],
    ["year", Infinity],
  ];
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  let value = seconds;
  for (const [unit, divisor] of units) {
    if (Math.abs(value) < divisor) return rtf.format(-Math.round(value), unit);
    value /= divisor;
  }
  return rtf.format(-Math.round(value), "year");
}

export function dateLabel(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function timeLabel(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

const BADGE_LABELS: Record<string, string> = {
  best_overall: "Best overall",
  best_budget: "Best value",
  best_rated: "Highest rated",
  best_premium: "Premium pick",
  best_deal: "Biggest saving",
};

export function badgeLabel(badge: string | null | undefined): string | null {
  if (!badge) return null;
  return BADGE_LABELS[badge] ?? titleCase(badge);
}

const PRESET_LABELS: Record<string, string> = {
  best_overall: "Balanced",
  best_budget: "Lowest cost",
  premium: "Premium",
};

export function presetLabel(preset: string): string {
  return PRESET_LABELS[preset] ?? titleCase(preset);
}

const SCORE_LABELS: Record<string, string> = {
  goal_suitability: "Goal suitability",
  preference_match: "Preference match",
  quality: "Quality",
  feature_match: "Feature match",
  budget_fit: "Budget fit",
  review_strength: "Review strength",
  delivery: "Delivery",
  deal_value: "Deal value",
  final: "Final score",
};

export function scoreLabel(key: string): string {
  return SCORE_LABELS[key] ?? titleCase(key);
}

const SLOT_LABELS: Record<string, string> = {
  goal_text: "Goal",
  activity: "Activity",
  location: "Location",
  region_type: "Terrain",
  season: "Season",
  duration_days: "Duration",
  people_count: "People",
  experience_level: "Experience",
  budget_total: "Budget",
  camping: "Camping",
  existing_items: "Already owned",
};

export function slotLabel(key: string): string {
  return SLOT_LABELS[key] ?? titleCase(key);
}

export function slotValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (key === "budget_total" && typeof value === "number") return rupees(value);
  if (key === "duration_days") return `${value} ${Number(value) === 1 ? "day" : "days"}`;
  if (key === "people_count") return `${value} ${Number(value) === 1 ? "person" : "people"}`;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.map(titleCase).join(", ") : "—";
  return titleCase(String(value));
}

const UNFULFILLED_LABELS: Record<string, string> = {
  no_candidates: "Nothing in the catalog matched this",
  all_over_budget: "Everything found was over budget",
  all_out_of_stock: "Every match is out of stock",
  budget_prioritized: "Skipped to keep essentials within budget",
};

export function unfulfilledLabel(reason: string): string {
  return UNFULFILLED_LABELS[reason] ?? titleCase(reason);
}
