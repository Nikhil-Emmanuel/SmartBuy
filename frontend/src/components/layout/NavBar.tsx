import { motion, useReducedMotion } from "framer-motion";
import { LayoutGrid, LogIn, MessageCircle, ShieldCheck, User } from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router-dom";

import { SignInDialog } from "@/components/profile/SignInDialog";
import { Logo } from "@/components/shared/Logo";
import { MarketplaceToggle } from "@/components/shared/MarketplaceToggle";
import { Button } from "@/components/ui/button";
import { usePersonalization } from "@/hooks/useProfile";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";

const links = [
  { to: "/chat", label: "Shop", icon: MessageCircle },
  { to: "/profile", label: "Profile", icon: User },
  { to: "/admin", label: "Admin", icon: ShieldCheck },
];

/**
 * One nav item.
 *
 * The active background is a single shared `layoutId` element rather than a
 * class on each link, so switching tabs *slides* the highlight from the old
 * tab to the new one. That is the animation carrying meaning: it shows where
 * you came from. Text colour still changes per-link, so the active tab is
 * legible the instant it renders and does not depend on the motion landing.
 */
function NavItem({
  to,
  label,
  icon: Icon,
}: {
  to: string;
  label: string;
  icon: typeof MessageCircle;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "relative inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "text-accent-foreground"
            : "text-muted-foreground hover:bg-accent/60 hover:text-accent-foreground",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-active"
              className="absolute inset-0 -z-10 rounded-lg bg-accent"
              transition={SPRING}
            />
          )}
          <Icon className="size-4" />
          <span className="hidden sm:inline">{label}</span>
        </>
      )}
    </NavLink>
  );
}

export function NavBar() {
  const planId = useAppStore((s) => s.planId);
  const [signInOpen, setSignInOpen] = useState(false);
  const personalization = usePersonalization();
  const reduced = useReducedMotion();

  // The nav shows the segment only once the model has actually committed to
  // one. A pill that says "Deal seeker" next to a status of low_confidence
  // would be the UI overstating what the model returned.
  const segmentLabel =
    personalization.data?.status === "ok" ? personalization.data.label : null;

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <NavLink to="/" className="shrink-0">
          <Logo />
        </NavLink>

        <nav className="flex items-center gap-1">
          {links.map((link) => (
            <NavItem key={link.to} {...link} />
          ))}
          {planId && <NavItem to={`/plan/${planId}`} label="My plan" icon={LayoutGrid} />}
        </nav>

        <div className="flex items-center gap-1">
          <MarketplaceToggle />

          <motion.button
            type="button"
            onClick={() => setSignInOpen(true)}
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            <LogIn className="size-3.5" />
            {/*
              Keyed remount rather than AnimatePresence: an exit animation here
              would hold the stale label on screen until it finished, and a tab
              that never gets a frame (background, or a preview pane that pins
              reduced motion) would leave "Sign in" showing forever. Remounting
              swaps the text immediately and animates it in afterwards.
            */}
            <motion.span
              key={segmentLabel ?? "signin"}
              initial={reduced ? false : { opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              className="hidden sm:inline"
            >
              {segmentLabel ?? "Sign in"}
            </motion.span>
          </motion.button>

          <Button asChild size="sm" className="hidden sm:inline-flex">
            <NavLink to="/chat">Start shopping</NavLink>
          </Button>
        </div>
      </div>

      <SignInDialog open={signInOpen} onOpenChange={setSignInOpen} />
    </header>
  );
}
