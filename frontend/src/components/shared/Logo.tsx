import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-primary/30">
        <Sparkles className="size-4" strokeWidth={2.25} />
      </span>
      {/*
        The wordmark is the first thing to go on a narrow header: the mark on
        its own still identifies the site, whereas dropping a nav item would
        remove somewhere to go. Kept in the DOM as a screen-reader label so the
        home link is not just an unlabelled icon.
      */}
      <span className="max-sm:sr-only">
        SmartBuy <span className="text-primary">AI</span>
      </span>
    </span>
  );
}
