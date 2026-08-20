import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { qk } from "@/lib/queryClient";
import { ApiError } from "@/services/client";
import * as api from "@/services/api";
import { useAppStore } from "@/store/useAppStore";
import type { ChatResponse } from "@/types/api";

/**
 * Keeps the app store's conversation/plan pointers -- and the last turn
 * itself -- in lockstep with a chat call. This runs from `useMutation`'s
 * hook-level `onSuccess`, which React Query guarantees fires even if the
 * component that called `mutate()` has since unmounted (see the note on
 * `lastChatTurn` in useAppStore). Do not move this logic into a per-call
 * `mutate(vars, { onSuccess })` callback -- that one is not guaranteed to run.
 */
function syncFromResponse(response: ChatResponse) {
  const { setChatSession, setPlan, reportChatTurn } = useAppStore.getState();
  setChatSession(response.session_id);
  if (response.plan_id) setPlan(response.plan_id);
  reportChatTurn(response);
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => {
      const chatSessionId = useAppStore.getState().chatSessionId;
      return api.chat({ session_id: chatSessionId, message });
    },
    onSuccess: (response) => {
      syncFromResponse(response);
      if (response.plan_id) {
        queryClient.invalidateQueries({ queryKey: qk.requirements(response.plan_id) });
        queryClient.invalidateQueries({ queryKey: qk.plan(response.plan_id) });
      }
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : "Something went wrong reaching SmartBuy. Please try again in a moment.";
      useAppStore.getState().reportChatError(message);
    },
  });
}

export function useSession(chatSessionId: string | null) {
  return useQuery({
    queryKey: qk.session(chatSessionId ?? "none"),
    queryFn: () => api.getSession(chatSessionId as string),
    enabled: Boolean(chatSessionId),
  });
}

/**
 * Editing a slot by hand is not a conversational turn, and must not be
 * reported as one.
 *
 * This used to call `syncFromResponse`, which pushes the payload through
 * `reportChatTurn` -- the channel ChatPage listens on to append the
 * assistant's reply. A slot update returns a `SessionResponse`, which has no
 * `assistant_message`, so ChatPage appended a bubble whose content was
 * `undefined` and `ChatBubble` threw on `content.length`. With no error
 * boundary above it, React unmounted the whole tree: the page went blank.
 *
 * The result is written to the session cache instead, which is where a
 * session response belongs.
 */
export function useUpdateSlots() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Parameters<typeof api.updateSlots>[1]) => {
      const chatSessionId = useAppStore.getState().chatSessionId;
      if (!chatSessionId) throw new Error("No active conversation");
      return api.updateSlots(chatSessionId, patch);
    },
    onSuccess: (response) => {
      const { setChatSession, setPlan } = useAppStore.getState();
      setChatSession(response.session_id);
      if (response.plan_id) setPlan(response.plan_id);

      queryClient.setQueryData(qk.session(response.session_id), response);
      if (response.plan_id) {
        queryClient.invalidateQueries({ queryKey: qk.requirements(response.plan_id) });
        queryClient.invalidateQueries({ queryKey: qk.plan(response.plan_id) });
      }
    },
  });
}

/**
 * The always-on option tray for the chat.
 *
 * Cached hard: goals come from YAML files and category counts from a catalog
 * that only changes when someone reseeds. Refetching this on every mount would
 * be pure noise.
 */
export function useSuggestions() {
  return useQuery({
    queryKey: qk.suggestions,
    queryFn: api.getSuggestions,
    staleTime: 30 * 60_000,
  });
}
