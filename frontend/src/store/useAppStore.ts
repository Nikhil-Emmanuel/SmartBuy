import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ChatResponse } from "@/types/api";

/**
 * Ephemeral, cross-page UI state only. Anything the backend owns (slots,
 * messages, plans, recommendations) lives in TanStack Query, keyed off the
 * ids stored here -- this store is the pointer, not the data.
 *
 * `chatSessionId` is the *conversation* id (`ChatResponse.session_id`), not
 * the anonymous-user id. Those are two different identifiers that happen to
 * share the word "session": the user id lives in the `X-Session-Id` header
 * and is managed privately inside services/client.ts, because every request
 * needs it and no component should have to think about it. The conversation
 * id is threaded explicitly through chat calls because a user can have more
 * than one conversation.
 *
 * `lastChatTurn`/`lastChatError`/`chatTurnSeq` exist because of a React Query
 * v5 + StrictMode interaction: when `mutate()` is called from a mount-time
 * effect (the landing page's "start with this goal" auto-send), StrictMode's
 * dev-only setup->cleanup->setup cycle orphans the *per-call* onSuccess/onError
 * callbacks and the mutation's own reactive `data`/`isPending` -- the fetch
 * still completes, but the component that called `mutate()` never hears back.
 * Hook-level `useMutation({ onSuccess })` callbacks are unaffected (React Query
 * guarantees those always fire), so the chat hook writes the result here, and
 * ChatPage reacts to the store instead of trusting the mutation object.
 * `chatTurnSeq` increments on every turn so the effect fires even if two
 * responses were structurally identical.
 */
interface AppState {
  chatSessionId: string | null;
  planId: string | null;
  compareSelection: string[];
  adminToken: string;
  lastChatTurn: ChatResponse | null;
  lastChatError: string | null;
  chatTurnSeq: number;
  /**
   * Marketplaces the user has switched on. `null` means "hasn't chosen", which
   * the API layer sends as no filter at all -- distinct from `[]`, which is a
   * user who deliberately switched everything off and should see nothing
   * rather than silently getting all marketplaces back.
   */
  enabledSources: string[] | null;

  setChatSession: (chatSessionId: string) => void;
  setEnabledSources: (keys: string[] | null) => void;
  /** `allKeys` seeds the first toggle; the store cannot know the catalogue itself. */
  toggleSource: (key: string, allKeys: string[]) => void;
  setPlan: (planId: string | null) => void;
  toggleCompare: (productId: string) => void;
  clearCompare: () => void;
  setAdminToken: (token: string) => void;
  reportChatTurn: (turn: ChatResponse) => void;
  reportChatError: (message: string) => void;
}

const MAX_COMPARE = 4;

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      chatSessionId: null,
      planId: null,
      compareSelection: [],
      adminToken: "",
      lastChatTurn: null,
      lastChatError: null,
      chatTurnSeq: 0,
      enabledSources: null,

      setChatSession: (chatSessionId) => set({ chatSessionId }),
      setEnabledSources: (enabledSources) => set({ enabledSources }),
      toggleSource: (key, allKeys) => {
        // First interaction seeds from `all`, so switching one marketplace off
        // leaves the rest on rather than leaving only the one just clicked.
        const current = get().enabledSources ?? allKeys;
        set({
          enabledSources: current.includes(key)
            ? current.filter((k) => k !== key)
            : [...current, key],
        });
      },
      setPlan: (planId) => set({ planId }),
      reportChatTurn: (turn) =>
        set((s) => ({ lastChatTurn: turn, lastChatError: null, chatTurnSeq: s.chatTurnSeq + 1 })),
      reportChatError: (message) =>
        set((s) => ({ lastChatError: message, chatTurnSeq: s.chatTurnSeq + 1 })),

      toggleCompare: (productId) => {
        const current = get().compareSelection;
        if (current.includes(productId)) {
          set({ compareSelection: current.filter((id) => id !== productId) });
          return;
        }
        if (current.length >= MAX_COMPARE) return;
        set({ compareSelection: [...current, productId] });
      },
      clearCompare: () => set({ compareSelection: [] }),
      setAdminToken: (adminToken) => set({ adminToken }),
    }),
    {
      name: "smartbuy.app",
      partialize: (state) => ({
        chatSessionId: state.chatSessionId,
        planId: state.planId,
        adminToken: state.adminToken,
        enabledSources: state.enabledSources,
      }),
    },
  ),
);

export const MAX_COMPARE_ITEMS = MAX_COMPARE;
