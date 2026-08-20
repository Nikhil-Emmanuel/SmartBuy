/**
 * Fixture-backed API, enabled with `VITE_USE_MOCKS=true`.
 *
 * Every file in this directory is a *recorded* response from the real backend
 * (backend/scripts/capture_fixtures.py), not an invention. Mock mode exists so
 * an unreachable service cannot end the demo; the UI shows an explicit
 * "offline fixtures" banner whenever it is on, because pretending a stale
 * snapshot is a live system would be a lie about what the product did.
 *
 * Imports are dynamic so none of this reaches the production bundle.
 */

import type {
  AdminMetrics,
  AuditLogsResponse,
  ChatRequest,
  ChatResponse,
  CompareResponse,
  DemoShoppersResponse,
  ExplainResponse,
  PersonalizationResponse,
  Product,
  ProductDetail,
  ProductSearchParams,
  ProductSearchResponse,
  ProfileResponse,
  RecommendationsRequest,
  RecommendationsResponse,
  RequirementsResponse,
  SessionResponse,
  ShoppingPlanResponse,
  SuggestionsResponse,
} from "@/types/api";

/** Fixtures answer instantly; a little latency keeps loading states honest. */
const LATENCY_MS = 260;

async function fixture<T>(loader: () => Promise<{ default: unknown }>): Promise<T> {
  const [module] = await Promise.all([
    loader(),
    new Promise((resolve) => setTimeout(resolve, LATENCY_MS)),
  ]);
  return module.default as T;
}

export const isMockMode = true;

// ---------------------------------------------------------------- wave 1

export async function searchProducts(
  params: ProductSearchParams,
): Promise<ProductSearchResponse> {
  const data = await fixture<ProductSearchResponse>(() => import("./products_search.json"));
  let items = data.items;

  const q = params.q?.trim().toLowerCase();
  if (q) {
    const terms = q.split(/\s+/);
    items = items.filter((item) => {
      const haystack =
        `${item.name} ${item.brand} ${item.subcategory} ${item.features.join(" ")}`.toLowerCase();
      return terms.some((term) => haystack.includes(term));
    });
  }
  if (params.brand) items = items.filter((i) => i.brand === params.brand);
  if (params.source) items = items.filter((i) => i.source === params.source);
  if (params.min_price) items = items.filter((i) => i.price >= params.min_price!);
  if (params.max_price) items = items.filter((i) => i.price <= params.max_price!);
  if (params.min_rating) items = items.filter((i) => (i.rating ?? 0) >= params.min_rating!);

  const sorters: Record<string, (a: Product, b: Product) => number> = {
    price_asc: (a, b) => a.price - b.price,
    price_desc: (a, b) => b.price - a.price,
    rating: (a, b) => (b.rating ?? 0) - (a.rating ?? 0),
    delivery: (a, b) => (a.delivery_days ?? 99) - (b.delivery_days ?? 99),
    deal: (a, b) => (b.discount_pct ?? 0) - (a.discount_pct ?? 0),
  };
  const sorter = params.sort ? sorters[params.sort] : undefined;
  if (sorter) items = [...items].sort(sorter);

  const pageSize = params.page_size ?? 20;
  const page = params.page ?? 1;
  return {
    ...data,
    items: items.slice((page - 1) * pageSize, page * pageSize),
    total: items.length,
    page,
    page_size: pageSize,
  };
}

export async function getProduct(id: string): Promise<ProductDetail> {
  const detail = await fixture<ProductDetail>(() => import("./product_detail.json"));
  if (detail.id === id) return detail;

  const search = await fixture<ProductSearchResponse>(() => import("./products_search.json"));
  const match = search.items.find((item) => item.id === id);
  // Keep the offers/other_sources shape; only the product itself differs.
  return match ? { ...detail, ...match } : detail;
}

// ---------------------------------------------------------------- wave 2

let mockTurn = 0;

export function resetMockConversation() {
  mockTurn = 0;
}

export async function chat(body: ChatRequest): Promise<ChatResponse> {
  // The recorded demo is two turns: a clarifying question, then the plan.
  // Anything after that replays the completed state rather than inventing one.
  mockTurn = body.session_id === null ? 1 : mockTurn + 1;
  const name = mockTurn <= 1 ? "chat_turn1" : "chat_turn2";
  const data = await fixture<ChatResponse>(() =>
    name === "chat_turn1" ? import("./chat_turn1.json") : import("./chat_turn2.json"),
  );
  return data;
}

export function getSession(_id: string): Promise<SessionResponse> {
  return fixture<SessionResponse>(() => import("./session.json"));
}

// ---------------------------------------------------------------- wave 3

export function getRequirements(_planId: string): Promise<RequirementsResponse> {
  return fixture<RequirementsResponse>(() => import("./requirements.json"));
}

export async function getRecommendations(
  body: RecommendationsRequest,
): Promise<RecommendationsResponse> {
  const data = await fixture<RecommendationsResponse>(() => import("./recommendations.json"));
  if (!body.requirement_ids?.length) return data;
  const wanted = new Set(body.requirement_ids);
  return { ...data, results: data.results.filter((r) => wanted.has(r.requirement.id)) };
}

// ---------------------------------------------------------------- wave 4

export function getShoppingPlan(_planId: string): Promise<ShoppingPlanResponse> {
  return fixture<ShoppingPlanResponse>(() => import("./shopping_plan.json"));
}

// ---------------------------------------------------------------- wave 5

export function explain(
  _productId: string,
  _requirementId: string,
  _planId: string,
): Promise<ExplainResponse> {
  return fixture<ExplainResponse>(() => import("./explain.json"));
}

export async function compare(
  productIds: string[],
  _planId: string | null,
): Promise<CompareResponse> {
  const data = await fixture<CompareResponse>(() => import("./compare.json"));
  const wanted = new Set(productIds);
  const rows = data.rows.filter((row) => wanted.has(row.product.id));
  return rows.length ? { ...data, rows } : data;
}

// ---------------------------------------------------------------- wave 6

export function getProfile(): Promise<ProfileResponse> {
  return fixture<ProfileResponse>(() => import("./profile.json"));
}

export function getPersonalization(): Promise<PersonalizationResponse> {
  return fixture<PersonalizationResponse>(() => import("./personalization.json"));
}

export function getSuggestions(): Promise<SuggestionsResponse> {
  return fixture<SuggestionsResponse>(() => import("./suggestions.json"));
}

export function getDemoShoppers(): Promise<DemoShoppersResponse> {
  return fixture<DemoShoppersResponse>(() => import("./demo_shoppers.json"));
}

export function getAdminMetrics(): Promise<AdminMetrics> {
  return fixture<AdminMetrics>(() => import("./admin_metrics.json"));
}

export function getAuditLogs(): Promise<AuditLogsResponse> {
  return fixture<AuditLogsResponse>(() => import("./audit_logs.json"));
}
