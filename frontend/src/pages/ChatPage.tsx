import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ListChecks, Wallet } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ChatBubble, TypingIndicator } from "@/components/chat/ChatBubble";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { SlotSidebar } from "@/components/chat/SlotSidebar";
import { SuggestionDeck } from "@/components/chat/SuggestionDeck";
import { Button } from "@/components/ui/button";
import { useSendMessage, useSession, useUpdateSlots } from "@/hooks/useChat";
import { FADE, SPRING, useReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";
import type { ChatResponse, Slots } from "@/types/api";

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  degraded?: boolean;
  /** Only a turn that just arrived types itself out; replayed history does not. */
  stream?: boolean;
}

const EMPTY_SLOTS: Slots = {
  goal_text: null,
  activity: null,
  location: null,
  region_type: null,
  season: null,
  duration_days: null,
  people_count: null,
  experience_level: null,
  budget_total: null,
  currency: "INR",
  camping: null,
  existing_items: [],
  preferences: { brands: [], price_bias: "balanced", delivery_bias: "standard" },
};

const GREETING =
  "Pick one of the options below to get started -- a goal like a trip or a move, or a category " +
  "to browse. You can also type a specific product if you already know what you want.";

export function ChatPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const reduced = useReducedMotion();

  const chatSessionId = useAppStore((s) => s.chatSessionId);
  const chatTurnSeq = useAppStore((s) => s.chatTurnSeq);
  const { data: session } = useSession(chatSessionId);
  const sendMessage = useSendMessage();
  const updateSlots = useUpdateSlots();

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [turn, setTurn] = useState<ChatResponse | null>(null);
  const [slots, setSlots] = useState<Slots>(EMPTY_SLOTS);
  const [waiting, setWaiting] = useState(false);
  const [revealing, setRevealing] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentInitial = useRef(false);
  const hydrated = useRef(false);
  const lastSeenSeq = useRef(chatTurnSeq);

  // Hydrate from a persisted conversation on refresh -- refresh-survival per the contract.
  useEffect(() => {
    if (!session || messages.length > 0 || hydrated.current) return;
    hydrated.current = true;
    setMessages(
      session.messages.map((m, i) => ({
        id: `${m.created_at ?? i}-${i}`,
        role: m.role,
        content: m.content,
      })),
    );
    setSlots(session.slots);
  }, [session, messages.length]);

  // Slots have two writers. A chat turn sets them from its own payload below;
  // a manual edit in the sidebar comes back as a session, which `useUpdateSlots`
  // writes into this query's cache -- so following the cache is what makes the
  // corrected budget show up. Sending a message does not touch this query, so
  // this cannot overwrite a fresher turn.
  useEffect(() => {
    if (session) setSlots(session.slots);
  }, [session]);

  // React to the store rather than the mutation object -- see the note on
  // `lastChatTurn` in useAppStore for why the mutation's own callbacks and
  // reactive state cannot be trusted here.
  useEffect(() => {
    if (chatTurnSeq === lastSeenSeq.current) return;
    lastSeenSeq.current = chatTurnSeq;
    setWaiting(false);

    const { lastChatTurn, lastChatError } = useAppStore.getState();
    if (lastChatTurn) {
      const id = crypto.randomUUID();
      setTurn(lastChatTurn);
      setSlots(lastChatTurn.slots);
      setRevealing(id);
      setMessages((prev) => [
        ...prev,
        {
          id,
          role: "assistant",
          content: lastChatTurn.assistant_message,
          degraded: lastChatTurn.degraded,
          stream: true,
        },
      ]);
    } else if (lastChatError) {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: lastChatError },
      ]);
    }
  }, [chatTurnSeq]);

  useEffect(() => {
    const initial = (location.state as { initialMessage?: string } | null)?.initialMessage;
    if (initial && !sentInitial.current && messages.length === 0) {
      sentInitial.current = true;
      navigate(location.pathname, { replace: true, state: null });
      handleSend(initial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  useEffect(() => {
    const stick = () =>
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    stick();
    // A streaming bubble grows after it mounts, so keep the view pinned to it.
    if (!revealing) return;
    const timer = setInterval(stick, 120);
    return () => clearInterval(timer);
  }, [messages, waiting, revealing]);

  function handleSend(message: string) {
    setWaiting(true);
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: message }]);
    sendMessage.mutate(message);
  }

  const settled = !waiting && !revealing;
  const showGreeting = messages.length === 0 && !waiting;
  const planId = turn?.plan_id ?? session?.plan_id ?? null;
  const nextAction = turn?.next_action;

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_300px]">
      <div className="flex min-h-[calc(100vh-9rem)] flex-col rounded-2xl border border-border bg-card/40">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5">
          {/*
            The greeting fades out as the first real turn arrives rather than
            vanishing between frames -- an element that disappears instantly
            reads as a glitch, and this one sits right where the user is looking.
          */}
          <AnimatePresence>
            {showGreeting && (
              <motion.div
                key="greeting"
                exit={reduced ? undefined : { opacity: 0, y: -8, transition: { duration: 0.16 } }}
                className="space-y-4"
              >
                <ChatBubble role="assistant" content={GREETING} />
              </motion.div>
            )}
          </AnimatePresence>

          {messages.map((m) => (
            <ChatBubble
              key={m.id}
              role={m.role}
              content={m.content}
              degraded={m.degraded}
              stream={m.stream}
              onStreamEnd={() => setRevealing((id) => (id === m.id ? null : id))}
            />
          ))}

          <AnimatePresence>
            {waiting && (
              <motion.div
                key="typing"
                initial={reduced ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, transition: { duration: 0.12 } }}
                transition={FADE}
              >
                <TypingIndicator />
              </motion.div>
            )}
          </AnimatePresence>

          {settled && nextAction && nextAction !== "none" && nextAction !== "answer_question" && planId && (
            <motion.div
              className="pl-11"
              initial={reduced ? false : { opacity: 0, y: 10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={SPRING}
            >
              <Button
                onClick={() =>
                  navigate(
                    nextAction === "view_requirements"
                      ? `/plan/${planId}/requirements`
                      : `/plan/${planId}`,
                  )
                }
                className="gap-2"
              >
                {nextAction === "view_requirements" ? (
                  <>
                    <ListChecks className="size-4" /> See what you need
                  </>
                ) : (
                  <>
                    <Wallet className="size-4" /> View your shopping plan
                  </>
                )}
                <ArrowRight className="size-4" />
              </Button>
            </motion.div>
          )}
        </div>

        {/*
          The tray sits above the composer and is always mounted -- that is the
          point. Agent chips ride on top of it when the assistant has asked
          something specific, so the answer to the current question is never
          buried under the general options.
        */}
        <div className="space-y-3 border-t border-border p-4">
          <SuggestionDeck
            onSelect={handleSend}
            disabled={waiting}
            agentChips={settled ? turn?.chips : undefined}
          />
          <ChatComposer onSend={handleSend} disabled={waiting} />
        </div>
      </div>

      <div className={cn("hidden lg:block", messages.length === 0 && "opacity-60")}>
        <SlotSidebar
          slots={slots}
          collected={turn?.collected ?? []}
          missing={turn?.missing ?? []}
          assumptions={turn?.assumptions ?? []}
          progress={turn?.progress ?? 0}
          onUpdateBudget={(value) => updateSlots.mutate({ budget_total: value })}
          updatingBudget={updateSlots.isPending}
        />
      </div>
    </div>
  );
}
