import { ArrowRight, ListChecks, Wallet } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ChatBubble, TypingIndicator } from "@/components/chat/ChatBubble";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChipRow } from "@/components/chat/ChipRow";
import { SlotSidebar } from "@/components/chat/SlotSidebar";
import { Button } from "@/components/ui/button";
import { useSendMessage, useSession, useUpdateSlots } from "@/hooks/useChat";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";
import type { ChatResponse, Slots } from "@/types/api";

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  degraded?: boolean;
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
  "Tell me what you're shopping for -- a goal like a trip or move, or a specific product. " +
  "I'll work out the details as we go.";

const STARTER_CHIPS = [
  "4-day trek in Manali",
  "Setting up my first flat",
  "Waterproof shoes under Rs 3,000",
];

export function ChatPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const chatSessionId = useAppStore((s) => s.chatSessionId);
  const chatTurnSeq = useAppStore((s) => s.chatTurnSeq);
  const { data: session } = useSession(chatSessionId);
  const sendMessage = useSendMessage();
  const updateSlots = useUpdateSlots();

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [turn, setTurn] = useState<ChatResponse | null>(null);
  const [slots, setSlots] = useState<Slots>(EMPTY_SLOTS);
  const [waiting, setWaiting] = useState(false);
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

  // React to the store rather than the mutation object -- see the note on
  // `lastChatTurn` in useAppStore for why the mutation's own callbacks and
  // reactive state cannot be trusted here.
  useEffect(() => {
    if (chatTurnSeq === lastSeenSeq.current) return;
    lastSeenSeq.current = chatTurnSeq;
    setWaiting(false);

    const { lastChatTurn, lastChatError } = useAppStore.getState();
    if (lastChatTurn) {
      setTurn(lastChatTurn);
      setSlots(lastChatTurn.slots);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: lastChatTurn.assistant_message,
          degraded: lastChatTurn.degraded,
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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, waiting]);

  function handleSend(message: string) {
    setWaiting(true);
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: message }]);
    sendMessage.mutate(message);
  }

  const showGreeting = messages.length === 0 && !waiting;
  const planId = turn?.plan_id ?? session?.plan_id ?? null;
  const nextAction = turn?.next_action;

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_300px]">
      <div className="flex min-h-[calc(100vh-9rem)] flex-col rounded-2xl border border-border bg-card/40">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5">
          {showGreeting && (
            <>
              <ChatBubble role="assistant" content={GREETING} />
              <ChipRow chips={STARTER_CHIPS} onSelect={handleSend} />
            </>
          )}

          {messages.map((m) => (
            <ChatBubble key={m.id} role={m.role} content={m.content} degraded={m.degraded} />
          ))}

          {waiting && <TypingIndicator />}

          {!waiting && turn && turn.chips.length > 0 && (
            <ChipRow chips={turn.chips} onSelect={handleSend} />
          )}

          {!waiting && nextAction && nextAction !== "none" && nextAction !== "answer_question" && planId && (
            <div className="animate-rise pl-11">
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
            </div>
          )}
        </div>

        <div className="border-t border-border p-4">
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
