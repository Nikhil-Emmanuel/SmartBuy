import { CloudOff, WifiOff } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { USE_MOCKS } from "@/services/client";

/** Persistent banner while the whole app is running off recorded fixtures. */
export function MockModeBanner() {
  if (!USE_MOCKS) return null;
  return (
    <Alert variant="caution" className="rounded-none border-x-0 border-t-0">
      <CloudOff />
      <div>
        <AlertTitle>Offline demo mode</AlertTitle>
        <AlertDescription>
          Showing recorded fixtures because the live backend is not configured. Interactions
          replay the same captured journey rather than a live catalog.
        </AlertDescription>
      </div>
    </Alert>
  );
}

/** Per-turn banner: the LLM was unavailable and a deterministic template answered instead. */
export function DegradedBanner({ className }: { className?: string }) {
  return (
    <Alert variant="info" className={className}>
      <WifiOff />
      <div>
        <AlertTitle>Running without the language model</AlertTitle>
        <AlertDescription>
          The assistant answered using deterministic rules instead of Gemini. Every number
          shown is still computed the same way -- only the phrasing is templated.
        </AlertDescription>
      </div>
    </Alert>
  );
}
