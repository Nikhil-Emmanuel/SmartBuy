import { FlaskConical } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * Every product in this build is `is_simulated: true` -- a curated, generated
 * catalog, not a live marketplace feed. Master prompt: never imply real-time
 * or real marketplace data. This badge is the one honest disclosure that has
 * to appear everywhere a price is shown.
 */
export function SimulatedBadge({ className }: { className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border border-caution/25 bg-caution-soft px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-caution",
            className,
          )}
        >
          <FlaskConical className="size-2.5" />
          Simulated
        </span>
      </TooltipTrigger>
      <TooltipContent>
        Prices and stock come from a curated demo catalog, not a live marketplace feed.
      </TooltipContent>
    </Tooltip>
  );
}
