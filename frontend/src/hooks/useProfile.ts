import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { qk } from "@/lib/queryClient";
import * as api from "@/services/api";
import type { FeedbackRequest, ProfileUpdateRequest } from "@/types/api";

export function useProfile() {
  return useQuery({ queryKey: qk.profile, queryFn: api.getProfile });
}

/**
 * The trained segment model's read of this user. Never retried hard: the
 * endpoint already degrades to a "no offer" answer instead of failing, so a
 * retry storm would only be noise.
 */
export function usePersonalization() {
  return useQuery({
    queryKey: qk.personalization,
    queryFn: api.getPersonalization,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** The demo shopper roster. Only fetched when the picker is actually open. */
export function useDemoShoppers(enabled = true) {
  return useQuery({
    queryKey: qk.demoShoppers,
    queryFn: api.getDemoShoppers,
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdateRequest) => api.updateProfile(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.profile }),
  });
}

export function useSendFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FeedbackRequest) => api.sendFeedback(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.profile }),
  });
}
