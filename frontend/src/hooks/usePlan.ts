import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { qk } from "@/lib/queryClient";
import * as api from "@/services/api";
import type { BundlePreset, Priority, RequirementPatch, SubstituteReason } from "@/types/api";

export function useRequirements(planId: string | null) {
  return useQuery({
    queryKey: qk.requirements(planId ?? "none"),
    queryFn: () => api.getRequirements(planId as string),
    enabled: Boolean(planId),
  });
}

export function usePatchRequirement(planId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requirementId, patch }: { requirementId: string; patch: RequirementPatch }) =>
      api.patchRequirement(requirementId, patch),
    onSuccess: () => {
      if (!planId) return;
      queryClient.invalidateQueries({ queryKey: qk.requirements(planId) });
      queryClient.invalidateQueries({ queryKey: qk.plan(planId) });
    },
  });
}

export function useRecommendations(planId: string | null, requirementIds?: string[] | null) {
  return useQuery({
    queryKey: qk.recommendations(planId ?? "none", requirementIds),
    queryFn: () =>
      api.getRecommendations({
        plan_id: planId as string,
        requirement_ids: requirementIds ?? null,
        limit_per_requirement: 6,
      }),
    enabled: Boolean(planId),
  });
}

export function useShoppingPlan(planId: string | null) {
  return useQuery({
    queryKey: qk.plan(planId ?? "none"),
    queryFn: () => api.getShoppingPlan(planId as string),
    enabled: Boolean(planId),
  });
}

export function useOptimizeBundle(planId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (includePriorities?: Priority[]) => {
      if (!planId) throw new Error("No active plan");
      return api.optimizeBundle({
        plan_id: planId,
        presets: ["best_overall", "best_budget", "premium"],
        include_priorities: includePriorities ?? ["essential", "recommended", "optional"],
      });
    },
    onSuccess: () => {
      if (planId) queryClient.invalidateQueries({ queryKey: qk.plan(planId) });
    },
  });
}

export function useSelectBundle(planId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (preset: BundlePreset) => {
      if (!planId) throw new Error("No active plan");
      return api.selectBundle(planId, preset);
    },
    onSuccess: () => {
      if (planId) queryClient.invalidateQueries({ queryKey: qk.plan(planId) });
    },
  });
}

export function useSubstitute(planId: string | null) {
  return useMutation({
    mutationFn: ({
      requirementId,
      currentProductId,
      reason,
    }: {
      requirementId: string;
      currentProductId: string;
      reason: SubstituteReason;
    }) => {
      if (!planId) throw new Error("No active plan");
      return api.substitute(planId, requirementId, currentProductId, reason);
    },
  });
}
