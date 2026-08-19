import { useQuery } from "@tanstack/react-query";

import { qk } from "@/lib/queryClient";
import * as api from "@/services/api";

export function useAdminMetrics(enabled: boolean) {
  return useQuery({
    queryKey: qk.adminMetrics,
    queryFn: api.getAdminMetrics,
    enabled,
    retry: false,
  });
}

export function useAuditLogs(enabled: boolean, params: { limit?: number } = { limit: 60 }) {
  return useQuery({
    queryKey: qk.auditLogs(params),
    queryFn: () => api.getAuditLogs(params),
    enabled,
    retry: false,
  });
}
