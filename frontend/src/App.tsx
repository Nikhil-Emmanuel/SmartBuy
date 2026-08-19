import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AdminPage } from "@/pages/AdminPage";
import { ChatPage } from "@/pages/ChatPage";
import { ComparePage } from "@/pages/ComparePage";
import { DiscoverPage } from "@/pages/DiscoverPage";
import { LandingPage } from "@/pages/LandingPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlanPage } from "@/pages/PlanPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RequirementsPage } from "@/pages/RequirementsPage";

export default function App() {
  return (
    <TooltipProvider delayDuration={200}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/plan/:planId/requirements" element={<RequirementsPage />} />
            <Route path="/plan/:planId/discover" element={<DiscoverPage />} />
            <Route path="/plan/:planId/compare" element={<ComparePage />} />
            <Route path="/plan/:planId" element={<PlanPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/404" element={<NotFoundPage />} />
            <Route path="*" element={<Navigate to="/404" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster />
    </TooltipProvider>
  );
}
