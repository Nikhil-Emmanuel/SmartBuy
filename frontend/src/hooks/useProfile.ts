import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { qk } from "@/lib/queryClient";
import * as api from "@/services/api";
import type { FeedbackRequest, ProfileUpdateRequest } from "@/types/api";

export function useProfile() {
  return useQuery({ queryKey: qk.profile, queryFn: api.getProfile });
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
