import { AnimatePresence, motion } from "framer-motion";
import { Outlet, useLocation } from "react-router-dom";

import { NavBar } from "@/components/layout/NavBar";
import { MockModeBanner } from "@/components/shared/StatusBanners";
import { pageEnter, useReducedMotion } from "@/lib/motion";

export function AppShell() {
  const location = useLocation();
  const reduced = useReducedMotion();

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <MockModeBanner />
      <NavBar />
      <main className="flex-1">
        {/*
          `mode="wait"` so the outgoing page is gone before the incoming one
          arrives -- overlapping two full pages mid-scroll looks like a
          rendering bug rather than a transition. Keyed on pathname only: a
          query-string change is a filter, not a navigation, and should not
          flash the page.
        */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            variants={pageEnter}
            initial={reduced ? false : "hidden"}
            animate="visible"
            exit={reduced ? undefined : "exit"}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
