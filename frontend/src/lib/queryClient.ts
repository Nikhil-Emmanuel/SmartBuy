import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/services/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && !error.retryable) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});

export const qk = {
  health: ["health"] as const,
  session: (id: string) => ["session", id] as const,
  requirements: (planId: string) => ["requirements", planId] as const,
  recommendations: (planId: string, requirementIds?: string[] | null) =>
    ["recommendations", planId, requirementIds ?? "all"] as const,
  plan: (planId: string) => ["plan", planId] as const,
  explain: (productId: string, requirementId: string) =>
    ["explain", productId, requirementId] as const,
  compare: (productIds: string[]) => ["compare", [...productIds].sort()] as const,
  productSearch: (params: Record<string, unknown>) => ["products", params] as const,
  product: (id: string) => ["product", id] as const,
  profile: ["profile"] as const,
  adminMetrics: ["admin", "metrics"] as const,
  auditLogs: (params: Record<string, unknown>) => ["admin", "audit-logs", params] as const,
};
