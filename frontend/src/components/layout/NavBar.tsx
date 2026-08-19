import { LayoutGrid, MessageCircle, ShieldCheck, User } from "lucide-react";
import { NavLink } from "react-router-dom";

import { Logo } from "@/components/shared/Logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";

const links = [
  { to: "/chat", label: "Shop", icon: MessageCircle },
  { to: "/profile", label: "Profile", icon: User },
  { to: "/admin", label: "Admin", icon: ShieldCheck },
];

export function NavBar() {
  const planId = useAppStore((s) => s.planId);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <NavLink to="/" className="shrink-0">
          <Logo />
        </NavLink>

        <nav className="flex items-center gap-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                  isActive && "bg-accent text-accent-foreground",
                )
              }
            >
              <Icon className="size-4" />
              <span className="hidden sm:inline">{label}</span>
            </NavLink>
          ))}
          {planId && (
            <NavLink
              to={`/plan/${planId}`}
              className={({ isActive }) =>
                cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                  isActive && "bg-accent text-accent-foreground",
                )
              }
            >
              <LayoutGrid className="size-4" />
              <span className="hidden sm:inline">My plan</span>
            </NavLink>
          )}
        </nav>

        <Button asChild size="sm" className="hidden sm:inline-flex">
          <NavLink to="/chat">Start shopping</NavLink>
        </Button>
      </div>
    </header>
  );
}
