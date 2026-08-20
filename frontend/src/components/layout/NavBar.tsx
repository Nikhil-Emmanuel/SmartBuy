import { motion } from "framer-motion";
import { LayoutGrid, LogIn, MessageCircle, ShieldCheck, User } from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router-dom";

import { SignInDialog } from "@/components/profile/SignInDialog";
import { Logo } from "@/components/shared/Logo";
import { MarketplaceToggle } from "@/components/shared/MarketplaceToggle";
import { Button } from "@/components/ui/button";
import { usePersonalization } from "@/hooks/useProfile";
import { SPRING, useReducedMotion } from "@/lib/motion";
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

  const segmentLabel =
    personalization.data?.status === "ok" ? personalization.data.label : null;

  return (
    <header className="sticky top-0 z-40 glass-nav shadow-glass">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <NavLink to="/" className="shrink-0">
          <motion.div
            whileHover={reduced ? undefined : { scale: 1.03 }}
            whileTap={reduced ? undefined : { scale: 0.97 }}
            transition={SPRING}
          >
            <Logo />
          </motion.div>
        </NavLink>

        <nav className="flex items-center gap-1">
          {links.map((link) => (
            <NavItem key={link.to} {...link} />
          ))}
          {planId && <NavItem to={`/plan/${planId}`} label="My plan" icon={LayoutGrid} />}
        </nav>

        <div className="flex items-center gap-1.5">
          <MarketplaceToggle />

          <motion.button
            type="button"
            onClick={() => setSignInOpen(true)}
            whileHover={reduced ? undefined : { y: -1, scale: 1.02 }}
            whileTap={reduced ? undefined : { scale: 0.95 }}
            transition={SPRING}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-card/60 px-3 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur transition-colors hover:border-primary/40 hover:text-foreground"
          >
            <LogIn className="size-3.5" />
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

          <motion.div
            whileHover={reduced ? undefined : { scale: 1.03 }}
            whileTap={reduced ? undefined : { scale: 0.96 }}
            transition={SPRING}
            className="hidden sm:inline-flex"
          >
            <Button asChild size="sm">
              <NavLink to="/chat">Start shopping</NavLink>
            </Button>
          </motion.div>
        </div>
      </div>

      <SignInDialog open={signInOpen} onOpenChange={setSignInOpen} />
    </header>
  );
}
