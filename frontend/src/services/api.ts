/**
 * The typed API surface. One function per endpoint in docs/API_CONTRACT.md,
 * in contract order. Components import from here and never call `fetch`.
 *
 * When `VITE_USE_MOCKS=true` every call is served from captured fixtures
 * instead. Those fixtures are real recorded responses (see
 * backend/scripts/capture_fixtures.py), so mock mode and live mode render the
 * same screens — it exists so a dead backend cannot take the demo down.
 */

import { http, USE_MOCKS } from "./client";
import * as mocks from "./mocks";
import type {
  AdminMetrics,
  AuditLogsResponse,
  BundleOptimizeRequest,
  BundleOptimizeResponse,
  BundlePreset,
  ChatRequest,
  ChatResponse,
  CompareResponse,
  ExplainResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  MarketplacesResponse,
  DemoShoppersResponse,
  Offer,
  PersonalizationResponse,
  ProductDetail,
  ProductSearchParams,
  ProductSearchResponse,
  ProfileResponse,
  ProfileUpdateRequest,
  RecommendationsRequest,
  RecommendationsResponse,
  RequirementPatch,
  RequirementsResponse,
  SessionResponse,
  ShoppingPlanResponse,
  SlotPatch,
  SubstituteReason,
  SubstituteResponse,
  SuggestionsResponse,
} from "@/types/api";

// ----------------------------------------------------------------- wave 1

export function health() {
  return http.get<HealthResponse>("/api/health");
}

export function searchProducts(params: ProductSearchParams) {
  if (USE_MOCKS) return mocks.searchProducts(params);
  return http.get<ProductSearchResponse>("/api/products/search", { ...params });
}

export function getProduct(id: string) {
  if (USE_MOCKS) return mocks.getProduct(id);
  return http.get<ProductDetail>(`/api/products/${id}`);
}

export function getMarketplaces() {
  return http.get<MarketplacesResponse>("/api/marketplaces");
}

export function getOffers(productIds: string[]) {
  return http.get<{ offers: Record<string, Offer[]> }>("/api/offers", {
    product_ids: productIds.join(","),
  });
}

// ----------------------------------------------------------------- wave 2

export function chat(body: ChatRequest) {
  if (USE_MOCKS) return mocks.chat(body);
  return http.post<ChatResponse>("/api/chat", body);
}

export function getSession(id: string) {
  if (USE_MOCKS) return mocks.getSession(id);
  return http.get<SessionResponse>(`/api/session/${id}`);
}

/**
 * Manual slot correction from the sidebar.
 *
 * Returns a `SessionResponse`, NOT a `ChatResponse`: the backend route is
 * declared `response_model=SessionResponse` and ends in `return get_session(...)`.
 * It was typed as `ChatResponse` here, and since `http.post<T>` only casts,
 * nothing checked it -- the caller then read `assistant_message` off a payload
 * that has no such field and rendered `undefined` into a chat bubble.
 */
export function updateSlots(id: string, patch: SlotPatch) {
  return http.post<SessionResponse>(`/api/session/${id}/slots`, patch);
}

// ----------------------------------------------------------------- wave 3

export function generateRequirements(sessionId: string) {
  return http.post<RequirementsResponse>("/api/requirements/generate", {
    session_id: sessionId,
  });
}

export function getRequirements(planId: string) {
  if (USE_MOCKS) return mocks.getRequirements(planId);
  return http.get<RequirementsResponse>(`/api/requirements/${planId}`);
}

export function patchRequirement(requirementId: string, patch: RequirementPatch) {
  return http.patch<RequirementsResponse>(`/api/requirements/${requirementId}`, patch);
}

export function getRecommendations(body: RecommendationsRequest) {
  if (USE_MOCKS) return mocks.getRecommendations(body);
  return http.post<RecommendationsResponse>("/api/recommendations", body);
}

// ----------------------------------------------------------------- wave 4

export function optimizeBundle(body: BundleOptimizeRequest) {
  return http.post<BundleOptimizeResponse>("/api/bundle/optimize", body);
}

export function selectBundle(planId: string, preset: BundlePreset) {
  return http.post<{ ok: boolean; selected_preset: BundlePreset }>("/api/bundle/select", {
    plan_id: planId,
    preset,
  });
}

export function getShoppingPlan(planId: string) {
  if (USE_MOCKS) return mocks.getShoppingPlan(planId);
  return http.get<ShoppingPlanResponse>(`/api/shopping-plan/${planId}`);
}

// ----------------------------------------------------------------- wave 5

export function explain(productId: string, requirementId: string, planId: string) {
  if (USE_MOCKS) return mocks.explain(productId, requirementId, planId);
  return http.post<ExplainResponse>("/api/explain", {
    product_id: productId,
    requirement_id: requirementId,
    plan_id: planId,
  });
}

export function compare(productIds: string[], planId: string | null = null) {
  if (USE_MOCKS) return mocks.compare(productIds, planId);
  return http.post<CompareResponse>("/api/compare", {
    product_ids: productIds,
    plan_id: planId,
  });
}

export function substitute(
  planId: string,
  requirementId: string,
  currentProductId: string,
  reason: SubstituteReason,
) {
  return http.post<SubstituteResponse>("/api/substitute", {
    plan_id: planId,
    requirement_id: requirementId,
    current_product_id: currentProductId,
    reason,
  });
}

// ----------------------------------------------------------------- wave 6

export function sendFeedback(body: FeedbackRequest) {
  return http.post<FeedbackResponse>("/api/feedback", body);
}

export function recordInteraction(productId: string, interactionType: string) {
  return http.post<{ ok: boolean }>("/api/interactions", {
    product_id: productId,
    interaction_type: interactionType,
  });
}

export function getProfile() {
  if (USE_MOCKS) return mocks.getProfile();
  return http.get<ProfileResponse>("/api/profile");
}

export function updateProfile(body: ProfileUpdateRequest) {
  return http.put<ProfileResponse>("/api/profile", body);
}

export function getPersonalization() {
  if (USE_MOCKS) return mocks.getPersonalization();
  return http.get<PersonalizationResponse>("/api/personalization");
}

export function getSuggestions() {
  if (USE_MOCKS) return mocks.getSuggestions();
  return http.get<SuggestionsResponse>("/api/suggestions");
}

export function getDemoShoppers() {
  if (USE_MOCKS) return mocks.getDemoShoppers();
  return http.get<DemoShoppersResponse>("/api/demo/shoppers");
}

export function getAdminMetrics() {
  if (USE_MOCKS) return mocks.getAdminMetrics();
  return http.get<AdminMetrics>("/api/admin/metrics", undefined, true);
}

export function getAuditLogs(params: { limit?: number; session_id?: string; action?: string }) {
  if (USE_MOCKS) return mocks.getAuditLogs();
  return http.get<AuditLogsResponse>("/api/admin/audit-logs", params, true);
}
