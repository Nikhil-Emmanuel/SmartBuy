import {
  Activity,
  Bot,
  KeyRound,
  Package,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminMetrics, useAuditLogs } from "@/hooks/useAdmin";
import { compactNumber, percent, timeLabel, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";

const STATUS_VARIANT: Record<string, "savings" | "danger" | "caution" | "outline"> = {
  ok: "savings",
  fallback: "caution",
  blocked: "danger",
  error: "danger",
};

export function AdminPage() {
  const adminToken = useAppStore((s) => s.adminToken);
  const setAdminToken = useAppStore((s) => s.setAdminToken);
  const [draft, setDraft] = useState(adminToken);

  const metrics = useAdminMetrics(Boolean(adminToken));
  const logs = useAuditLogs(Boolean(adminToken));

  const unauthorized = metrics.isError;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <div className="flex items-center gap-3">
        <div className="flex size-11 items-center justify-center rounded-full bg-primary-soft text-primary">
          <ShieldCheck className="size-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-foreground">Admin dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Every number below is a real aggregate query -- nothing is hard-coded.
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="flex-1 space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              X-Admin-Token
            </label>
            <Input
              type="password"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setAdminToken(draft)}
              placeholder="Paste the shared admin token"
              className="max-w-sm"
            />
          </div>
          <Button onClick={() => setAdminToken(draft)}>
            <KeyRound className="size-4" /> Apply
          </Button>
        </CardContent>
      </Card>

      {!adminToken && (
        <EmptyState
          icon={KeyRound}
          title="Enter the admin token to view metrics"
          description="This dashboard has no login screen by design -- it's gated by a single shared token, per ADR-005."
        />
      )}

      {adminToken && unauthorized && (
        <ErrorState
          title="Could not authenticate"
          description="The token was rejected, or the service is unreachable. Double-check the token."
          onRetry={() => metrics.refetch()}
        />
      )}

      {adminToken && metrics.isLoading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      )}

      {adminToken && metrics.data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MetricCard icon={Users} label="Users" value={compactNumber(metrics.data.users)} />
            <MetricCard
              icon={Activity}
              label="Sessions"
              value={compactNumber(metrics.data.sessions)}
            />
            <MetricCard
              icon={Package}
              label="Plans generated"
              value={compactNumber(metrics.data.plans_generated)}
            />
            <MetricCard
              icon={Sparkles}
              label="Recommendations"
              value={compactNumber(metrics.data.recommendations_generated)}
            />
            <MetricCard
              icon={Wallet}
              label="Avg bundle value"
              value={`₹${compactNumber(metrics.data.avg_bundle_value)}`}
            />
            <MetricCard
              icon={Target}
              label="Budget compliance"
              value={percent(metrics.data.budget_compliance_rate)}
            />
            <MetricCard
              icon={Target}
              label="Requirement coverage"
              value={percent(metrics.data.requirement_coverage_avg)}
            />
            <MetricCard
              icon={Sparkles}
              label="Recommendation acceptance"
              value={percent(metrics.data.recommendation_acceptance_rate)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Bot className="size-4 text-primary" /> LLM health
                </CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 pt-0 text-sm">
                <Metric label="Calls" value={compactNumber(metrics.data.llm.calls)} />
                <Metric label="Failures" value={compactNumber(metrics.data.llm.failures)} />
                <Metric label="Fallback rate" value={percent(metrics.data.llm.fallback_rate, 1)} />
                <Metric label="Avg latency" value={`${Math.round(metrics.data.llm.avg_latency_ms)} ms`} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Feedback breakdown</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                {Object.entries(metrics.data.feedback).map(([type, count]) => (
                  <BarRow
                    key={type}
                    label={titleCase(type)}
                    value={count}
                    max={Math.max(...Object.values(metrics.data!.feedback), 1)}
                  />
                ))}
              </CardContent>
            </Card>
          </div>

          {metrics.data.top_categories.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Top categories</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                {metrics.data.top_categories.map((c) => (
                  <BarRow
                    key={c.category}
                    label={titleCase(c.category)}
                    value={c.count}
                    max={metrics.data!.top_categories[0].count}
                  />
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Recent audit log</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {logs.isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : logs.data && logs.data.logs.length > 0 ? (
                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-card">
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-2 pr-3 font-medium">Time</th>
                        <th className="py-2 pr-3 font-medium">Action</th>
                        <th className="py-2 pr-3 font-medium">Status</th>
                        <th className="py-2 pr-3 font-medium">Latency</th>
                        <th className="py-2 font-medium">Summary</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.data.logs.map((log) => (
                        <tr key={log.id} className="border-b border-border/60 last:border-0">
                          <td className="py-2 pr-3 tabular text-muted-foreground">
                            {log.created_at ? timeLabel(log.created_at) : "—"}
                          </td>
                          <td className="py-2 pr-3 font-medium text-foreground">{log.action}</td>
                          <td className="py-2 pr-3">
                            <Badge variant={STATUS_VARIANT[log.status] ?? "outline"}>
                              {log.status}
                            </Badge>
                          </td>
                          <td className="py-2 pr-3 tabular text-muted-foreground">
                            {log.latency_ms !== null ? `${Math.round(log.latency_ms)} ms` : "—"}
                          </td>
                          <td className="max-w-xs truncate py-2 text-muted-foreground">
                            {log.output_summary ?? log.input_summary ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No audit entries yet.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="mb-2 flex items-center gap-2 text-muted-foreground">
          <Icon className="size-3.5" />
          <span className="text-[11px] uppercase tracking-wide">{label}</span>
        </div>
        <p className="tabular text-xl font-semibold text-foreground">{value}</p>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="tabular text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}

function BarRow({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-32 shrink-0 text-muted-foreground">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full bg-primary transition-all duration-500")}
          style={{ width: `${max > 0 ? Math.round((value / max) * 100) : 0}%` }}
        />
      </div>
      <span className="tabular w-10 shrink-0 text-right font-medium">{value}</span>
    </div>
  );
}
