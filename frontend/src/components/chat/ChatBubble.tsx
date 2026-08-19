import { Sparkles } from "lucide-react";

import { DegradedBanner } from "@/components/shared/StatusBanners";
import { cn } from "@/lib/utils";

export function ChatBubble({
  role,
  content,
  degraded = false,
}: {
  role: "user" | "assistant";
  content: string;
  degraded?: boolean;
}) {
  const isUser = role === "user";

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
          {content}
        </div>
        {!isUser && degraded && <DegradedBanner className="w-full max-w-md py-2 text-xs" />}
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
