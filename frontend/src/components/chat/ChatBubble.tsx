import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { DegradedBanner } from "@/components/shared/StatusBanners";
import { cn } from "@/lib/utils";

/**
 * Reveals text word by word. Purely cosmetic: the full string is already in
 * hand (the API is not a streaming endpoint), so this only paces the paint --
 * it must never gate anything the user needs, and `stream={false}` on replayed
 * history keeps old turns from re-typing themselves on every mount.
 */
function useTypewriter(text: string, enabled: boolean, onDone?: () => void) {
  const [shown, setShown] = useState(() => (enabled ? "" : text));
  const doneFor = useRef<string | null>(enabled ? null : text);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    if (!enabled || doneFor.current === text) {
      setShown(text);
      return;
    }
    const words = text.split(" ");
    let i = 0;
    setShown("");
    const timer = setInterval(() => {
      i += 1;
      setShown(words.slice(0, i).join(" "));
      if (i >= words.length) {
        doneFor.current = text;
        clearInterval(timer);
        done.current?.();
      }
    }, 28);
    return () => clearInterval(timer);
  }, [text, enabled]);

  return shown;
}

export function ChatBubble({
  role,
  content,
  degraded = false,
  stream = false,
  onStreamEnd,
}: {
  role: "user" | "assistant";
  content: string;
  degraded?: boolean;
  stream?: boolean;
  onStreamEnd?: () => void;
}) {
  const isUser = role === "user";
  const shown = useTypewriter(content, stream && !isUser, onStreamEnd);
  const typing = shown.length < content.length;

  return (
    <div className={cn("animate-message-in flex gap-3", isUser && "flex-row-reverse")}>
      {!isUser && (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Sparkles className="size-4" />
        </div>
      )}
      <div className={cn("flex max-w-[80%] flex-col gap-1.5", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "rounded-tr-sm bg-primary text-primary-foreground"
              : "rounded-tl-sm border border-border bg-card text-card-foreground",
          )}
        >
          {shown}
          {typing && (
            <span className="ml-0.5 inline-block h-3.5 w-0.5 translate-y-0.5 animate-thinking bg-current" />
          )}
        </div>
        {!isUser && degraded && !typing && (
          <DegradedBanner className="w-full max-w-md py-2 text-xs" />
        )}
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Sparkles className="size-4" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="animate-thinking size-1.5 rounded-full bg-muted-foreground"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}
