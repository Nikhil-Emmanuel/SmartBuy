import { motion, useReducedMotion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { DegradedBanner } from "@/components/shared/StatusBanners";
import { EASE_OUT } from "@/lib/motion";
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
  const reduced = useReducedMotion();
  const shown = useTypewriter(content, stream && !isUser, onStreamEnd);
  const typing = shown.length < content.length;

  return (
    /*
      The entrance moved off the `animate-message-in` CSS keyframe and onto
      Framer. The keyframe starts at `opacity: 0` and relies on the animation
      actually running to get back to 1 -- so anywhere the animation is frozen
      or skipped (a throttled background tab, a reduced-motion user whose
      duration is clamped to 0.01ms), the message risks painting invisible.
      With `initial={false}` under reduced motion the bubble is simply there.
      A chat message must never depend on an animation to be readable.
    */
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.32, ease: EASE_OUT }}
      className={cn("flex gap-3", isUser && "flex-row-reverse")}
    >
      {!isUser && (
        <motion.div
          initial={reduced ? false : { scale: 0.6 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 400, damping: 22 }}
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"
        >
          <Sparkles className="size-4" />
        </motion.div>
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
    </motion.div>
  );
}

export function TypingIndicator() {
  const reduced = useReducedMotion();
  return (
    <div className="flex gap-3">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Sparkles className="size-4" />
      </div>
      <div
        className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3.5"
        role="status"
        aria-label="Assistant is thinking"
      >
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="size-1.5 rounded-full bg-muted-foreground"
            // Under reduced motion the dots hold still rather than disappear:
            // they are the only signal that a request is in flight, so they
            // must stay visible even when nothing is allowed to move.
            animate={reduced ? { opacity: 0.6 } : { opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
            transition={
              reduced
                ? { duration: 0 }
                : { duration: 1.2, repeat: Infinity, ease: "easeInOut", delay: i * 0.15 }
            }
          />
        ))}
      </div>
    </div>
  );
}
