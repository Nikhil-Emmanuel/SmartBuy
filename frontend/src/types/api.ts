/**
 * Types transcribed from docs/API_CONTRACT.md (FROZEN v1.0).
 *
 * This file is the frontend's half of the contract. If a field is not here,
 * the frontend does not read it; if the backend renames one, the build breaks
 * here first rather than in a component at demo time.
 *
 * Money is always integer rupees. Scores are floats in [0, 1].
 */

// ---------------------------------------------------------------- primitives

export type Availability = "in_stock" | "limited_stock" | "out_of_stock";
export type Priority = "essential" | "recommended" | "optional";
export type FulfillmentStatus = "fulfilled" | "partial" | "unfulfilled" | "owned";
export type Badge =
  | "best_overall"
  | "best_budget"
  | "best_rated"
  | "best_premium"
  | "best_deal";
export type BundlePreset = "best_overall" | "best_budget" | "premium";
export type AgentState =
  | "INTAKE"
  | "SLOT_FILL"
  | "PLANNING"
  | "DISCOVERY"
  | "OPTIMIZING"
  | "PRESENTED"
  | "REFINING";
export type Intent =
  | "GOAL_BASED_SHOPPING"
  | "SPECIFIC_PRODUCT_SEARCH"
  | "PRODUCT_COMPARISON"
  | "BUDGET_OPTIMIZATION"
  | "FIND_ALTERNATIVE"
  | "FIND_BEST_DEAL"
  | "GENERAL_RECOMMENDATION"
  | "SMALL_TALK"
  | "OUT_OF_SCOPE";
export type NextAction = "answer_question" | "view_requirements" | "view_plan" | "none";
export type FeedbackType = "relevant" | "not_relevant" | "saved" | "not_interested";
export type UnfulfilledReason =
  | "no_candidates"
  | "all_over_budget"
  | "all_out_of_stock"
  | "budget_prioritized";
export type SortOption =
  | "relevance"
  | "price_asc"
  | "price_desc"
  | "rating"
  | "delivery"
  | "deal";
export type SubstituteReason =
  | "cheaper"
  | "better_rated"
  | "faster_delivery"
  | "unavailable";

export type ErrorCode =
  | "VALIDATION_ERROR"
  | "SESSION_NOT_FOUND"
  | "PLAN_NOT_FOUND"
  | "PRODUCT_NOT_FOUND"
  | "BUDGET_INFEASIBLE"
  | "NO_PRODUCTS_FOUND"
  | "LLM_UNAVAILABLE"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR";

export interface ApiErrorBody {
  error: { code: ErrorCode; message: string; details?: Record<string, unknown> };
}

// ------------------------------------------------------------------ products

export interface Offer {
  offer_type: string;
  discount_pct: number | null;
  coupon_code: string | null;
  description?: string | null;
  valid_until?: string | null;
}

export interface Product {
  id: string;
  source: string;
  name: string;
  brand: string;
  category: string;
  subcategory: string;
  price: number;
  original_price: number | null;
  discount_pct: number | null;
  rating: number | null;
  review_count: number | null;
  features: string[];
  availability: Availability;
  delivery_days: number | null;
  url: string | null;
  image_url: string | null;
  tags: string[];
  /** Always true in this build. The UI must say so — see SimulatedBadge. */
  is_simulated: boolean;
}

export interface ProductDetail extends Product {
  offers: Offer[];
  /** Same product_group_key on a different marketplace: the price-compare row. */
  other_sources: Product[];
}

export interface ProductSearchResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  facets: {
    brands: Record<string, number>;
    sources: Record<string, number>;
    price_buckets: { label: string; min: number; max: number | null; count: number }[];
  };
}

export interface ProductSearchParams {
  q?: string;
  category?: string;
  subcategory?: string;
  brand?: string;
  min_price?: number;
  max_price?: number;
  min_rating?: number;
  source?: string;
  /** Comma-separated marketplace keys; omit for "all marketplaces". */
  sources?: string;
  features?: string;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

// ------------------------------------------------------------ recommendations

/** Every component normalized to [0,1]. Page 7 renders this verbatim. */
export interface ScoreBreakdown {
  goal_suitability: number;
  preference_match: number;
  quality: number;
  feature_match: number;
  budget_fit: number;
  review_strength: number;
  delivery: number;
  deal_value: number;
  final: number;
}

export interface Recommendation {
  product: Product;
  requirement_id: string;
  score: number;
  rank: number;
  badge: Badge | null;
  score_breakdown: ScoreBreakdown;
  reasons: string[];
  offer: Offer | null;
}

export interface Requirement {
  id: string;
  item_name: string;
  category: string;
  subcategory: string | null;
  priority: Priority;
  quantity: number;
  reason: string;
  est_price_min: number;
  est_price_max: number;
  is_owned: boolean;
  fulfillment_status: FulfillmentStatus;
}

export interface RequirementGroups {
  essential: Requirement[];
  recommended: Requirement[];
  optional: Requirement[];
}

export interface OwnedItem {
  item_name: string;
  matched_from: string;
}

// --------------------------------------------------------------------- slots

export interface Slots {
  goal_text: string | null;
  activity: string | null;
  location: string | null;
  region_type: string | null;
  season: string | null;
  duration_days: number | null;
  people_count: number | null;
  experience_level: string | null;
  budget_total: number | null;
  currency: string;
  camping: boolean | null;
  existing_items: string[];
  preferences: {
    brands: string[];
    price_bias: string;
    delivery_bias: string;
  };
}

export interface Assumption {
  slot: string;
  value: string;
  basis: string;
}

// ---------------------------------------------------------------------- chat

export interface ChatRequest {
  session_id: string | null;
  message: string;
}

export interface ChatResponse {
  session_id: string;
  state: AgentState;
  intent: Intent;
  assistant_message: string;
  chips: string[];
  slots: Slots;
  collected: string[];
  missing: string[];
  assumptions: Assumption[];
  progress: number;
  plan_id: string | null;
  next_action: NextAction;
  /** True when the LLM was unavailable and the deterministic path answered. */
  degraded: boolean;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  meta?: Record<string, unknown> | null;
}

export interface SessionResponse {
  session_id: string;
  state: AgentState;
  slots: Slots;
  intent: Intent | null;
  messages: ConversationMessage[];
  plan_id: string | null;
}

export type SlotPatch = Partial<{
  activity: string;
  location: string;
  season: string;
  duration_days: number;
  people_count: number;
  experience_level: string;
  budget_total: number;
  camping: boolean;
  existing_items: string[];
}>;

// -------------------------------------------------------------- requirements

export interface EstimatedRange {
  min: number;
  max: number;
}

export interface RequirementsResponse {
  plan_id: string;
  goal: string;
  goal_summary: string;
  context: Slots;
  requirements: RequirementGroups;
  already_owned: OwnedItem[];
  estimated_range: EstimatedRange;
}

export interface RequirementPatch {
  is_owned?: boolean;
  quantity?: number;
}

export interface RecommendationsRequest {
  plan_id: string;
  requirement_ids?: string[] | null;
  limit_per_requirement?: number;
  /** Marketplace keys the user has switched on; omit for "all marketplaces". */
  sources?: string[] | null;
}

export interface RequirementResults {
  requirement: Requirement;
  recommendations: Recommendation[];
  unfulfilled_reason: UnfulfilledReason | null;
}

export interface RecommendationsResponse {
  plan_id: string;
  results: RequirementResults[];
}

// ----------------------------------------------------------------- compare

export interface CompareRow {
  product: Product;
  match_score: number;
  deal_value: number;
  score_breakdown: ScoreBreakdown;
  is_best: Record<string, boolean>;
}

export interface CompareResponse {
  columns: string[];
  rows: CompareRow[];
  winner: Partial<Record<Badge, string>>;
}

export interface WeightedPoint {
  label: string;
  earned: number;
  max: number;
}

export interface ExplainResponse {
  match_score: number;
  score_breakdown: ScoreBreakdown;
  /** Sums to 100. Computed in Python — the summary is the only LLM prose. */
  weighted_points: WeightedPoint[];
  summary: string;
  reasons: string[];
  evidence: Record<string, number | string | boolean | null>;
  degraded?: boolean;
}

export interface Alternative {
  product: Product;
  price_delta: number;
  score_delta: number;
  why: string;
}

export interface SubstituteResponse {
  alternatives: Alternative[];
}

// ------------------------------------------------------------------ bundles

export interface BundleItem {
  requirement: Requirement;
  product: Product;
  quantity: number;
  line_total: number;
  score: number;
  reasons: string[];
}

export interface BundleExclusion {
  requirement_id: string;
  item_name?: string;
  reason: string;
}

export interface Marketplace {
  key: string;
  label: string;
  /** True only when products come from a real marketplace API, not the demo catalog. */
  live: boolean;
  /** False when the integration exists but has no credentials configured. */
  available: boolean;
  note?: string;
  product_count: number;
}

export interface MarketplacesResponse {
  marketplaces: Marketplace[];
}

export interface Bundle {
  preset: BundlePreset;
  total_cost: number;
  total_savings: number;
  remaining_budget: number;
  over_budget: number;
  utility_score: number;
  requirement_coverage: number;
  items: BundleItem[];
  excluded: BundleExclusion[];
}

export interface Substitution {
  requirement_id: string;
  from: Product;
  to: Product;
  price_delta: number;
  score_delta: number;
  reason: string;
}

export interface BundleOptimizeRequest {
  plan_id: string;
  presets?: BundlePreset[];
  include_priorities?: Priority[];
}

export interface BundleOptimizeResponse {
  plan_id: string;
  budget: number | null;
  bundles: Bundle[];
  substitutions: Substitution[];
  infeasible: boolean;
  shortfall: number | null;
}

export interface Unfulfilled {
  requirement_id: string;
  item_name: string;
  reason: UnfulfilledReason;
}

export interface PlanTotals {
  budget: number | null;
  estimated_total: number;
  savings: number;
  remaining: number | null;
}

export interface ShoppingPlanResponse {
  plan_id: string;
  goal: string;
  goal_summary: string;
  status: string;
  context: Slots;
  requirements: RequirementGroups;
  already_owned: OwnedItem[];
  bundles: Bundle[];
  selected_preset: BundlePreset | null;
  totals: PlanTotals;
  substitutions: Substitution[];
  unfulfilled: Unfulfilled[];
}

// ------------------------------------------------------- feedback & profile

export interface FeedbackRequest {
  product_id: string;
  plan_id?: string | null;
  feedback_type: FeedbackType;
  comment?: string | null;
}

export interface UserPreferences {
  preferred_categories: string[];
  preferred_brands: string[];
  min_price: number | null;
  max_price: number | null;
  price_bias: string;
  delivery_bias: string;
  brand_affinity: Record<string, number>;
  category_affinity: Record<string, number>;
  subcategory_affinity: Record<string, number>;
}

export interface FeedbackResponse {
  ok: boolean;
  preferences_updated: boolean;
  updated_preferences: UserPreferences;
}

export interface PlanSummary {
  plan_id: string;
  goal: string;
  estimated_total: number;
  created_at: string;
}

export interface FeedbackHistoryEntry {
  product: Product;
  feedback_type: FeedbackType;
  created_at: string;
}

export interface ProfileResponse {
  user_id: string;
  is_anonymous: boolean;
  preferences: UserPreferences;
  saved_products: Product[];
  recent_plans: PlanSummary[];
  feedback_history: FeedbackHistoryEntry[];
}

/**
 * Output of the trained shopper-segment classifier.
 *
 * `status` is not decoration: anything other than `"ok"` means no offer was
 * issued and the other fields are empty. The UI must show the reason rather
 * than silently render a blank card -- "we don't know you well enough yet" is
 * a true and useful thing to say; a phantom coupon is not.
 */
export interface PersonalizationResponse {
  segment: string | null;
  label: string | null;
  confidence: number;
  rationale: string | null;
  discount_pct: number;
  coupon_code: string | null;
  perk: string | null;
  events_considered: number;
  status: "ok" | "insufficient_history" | "low_confidence" | "model_unavailable";
  is_model_generated: boolean;
}

export interface ProfileUpdateRequest {
  preferred_categories?: string[];
  preferred_brands?: string[];
  min_price?: number | null;
  max_price?: number | null;
  price_bias?: string;
  delivery_bias?: string;
}

// --------------------------------------------------------------------- admin

export interface AdminMetrics {
  users: number;
  sessions: number;
  plans_generated: number;
  recommendations_generated: number;
  avg_bundle_value: number;
  budget_compliance_rate: number;
  requirement_coverage_avg: number;
  feedback: Record<string, number>;
  recommendation_acceptance_rate: number;
  llm: {
    calls: number;
    failures: number;
    fallback_rate: number;
    avg_latency_ms: number;
  };
  top_categories: { category: string; count: number }[];
}

export interface AuditLog {
  id: string;
  session_id: string | null;
  action: string;
  tool: string | null;
  input_summary: string | null;
  output_summary: string | null;
  model_version: string | null;
  latency_ms: number | null;
  status: string;
  created_at: string;
}

export interface AuditLogsResponse {
  logs: AuditLog[];
  total: number;
}

export interface HealthResponse {
  status: string;
  db: string;
  llm: "ok" | "degraded";
  catalog_size: number;
}
