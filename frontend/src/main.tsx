import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";
import { queryClient } from "@/lib/queryClient";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/*
        Motion is unconditional in this build. `reducedMotion="never"` is the
        half of that decision Framer Motion enforces internally: without it,
        `motion` components silently drop transform animations (x/y/scale/
        rotate) on a device that reports the OS preference, keeping only
        opacity. The other half is the `useReducedMotion` shim in
        src/lib/motion.ts, which this provider does NOT cover -- the public
        hook reads matchMedia directly and ignores MotionConfig entirely.
      */}
      <MotionConfig reducedMotion="never">
        <App />
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
