import { Outlet } from "react-router-dom";

import { NavBar } from "@/components/layout/NavBar";
import { MockModeBanner } from "@/components/shared/StatusBanners";

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <MockModeBanner />
      <NavBar />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
