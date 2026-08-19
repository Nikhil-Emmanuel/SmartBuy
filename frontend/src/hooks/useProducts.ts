import { useQuery } from "@tanstack/react-query";

import { qk } from "@/lib/queryClient";
import * as api from "@/services/api";
import type { ProductSearchParams } from "@/types/api";

export function useProductSearch(params: ProductSearchParams, enabled = true) {
  return useQuery({
    queryKey: qk.productSearch(params as Record<string, unknown>),
    queryFn: () => api.searchProducts(params),
    enabled,
    placeholderData: (previous) => previous,
  });
}

/**
 * The marketplace catalogue. Cached hard because it only changes when the
 * backend gains or loses a provider integration, which cannot happen mid-session.
 */
export function useMarketplaces() {
  return useQuery({
    queryKey: qk.marketplaces(),
    queryFn: api.getMarketplaces,
    staleTime: Infinity,
  });
}

export function useProduct(id: string | null) {
  return useQuery({
    queryKey: qk.product(id ?? "none"),
    queryFn: () => api.getProduct(id as string),
    enabled: Boolean(id),
  });
}

export function useExplain(
  productId: string | null,
  requirementId: string | null,
  planId: string | null,
) {
  return useQuery({
    queryKey: qk.explain(productId ?? "none", requirementId ?? "none"),
    queryFn: () => api.explain(productId as string, requirementId as string, planId as string),
    enabled: Boolean(productId && requirementId && planId),
    staleTime: Infinity,
  });
}

export function useCompare(productIds: string[], planId: string | null) {
  return useQuery({
    queryKey: qk.compare(productIds),
    queryFn: () => api.compare(productIds, planId),
    enabled: productIds.length >= 2,
  });
}
