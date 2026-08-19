import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-primary/30">
        <Sparkles className="size-4" strokeWidth={2.25} />
      </span>
      <span>
        SmartBuy <span className="text-primary">AI</span>
      </span>
    </span>
  );
}
