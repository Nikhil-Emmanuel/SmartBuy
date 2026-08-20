import { motion } from "framer-motion";
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

import { CountUp } from "@/components/shared/CountUp";
import { EmptyState, ErrorState } from "@/components/shared/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminMetrics, useAuditLogs } from "@/hooks/useAdmin";
import { compactNumber, percent, timeLabel, titleCase } from "@/lib/format";
import { EASE_OUT, HOVER_LIFT, useReducedMotion } from "@/lib/motion";
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
            <MetricCard
              icon={Users}
              label="Users"
              value={metrics.data.users}
              format={compactNumber}
              index={0}
            />
            <MetricCard
              icon={Activity}
              label="Sessions"
              value={metrics.data.sessions}
              format={compactNumber}
              index={1}
            />
            <MetricCard
              icon={Package}
              label="Plans generated"
              value={metrics.data.plans_generated}
              format={compactNumber}
              index={2}
            />
            <MetricCard
              icon={Sparkles}
              label="Recommendations"
              value={metrics.data.recommendations_generated}
              format={compactNumber}
              index={3}
            />
            <MetricCard
              icon={Wallet}
              label="Avg bundle value"
              value={metrics.data.avg_bundle_value}
              format={(v) => `₹${compactNumber(v)}`}
              index={4}
            />
            <MetricCard
              icon={Target}
              label="Budget compliance"
              value={metrics.data.budget_compliance_rate}
              format={(v) => percent(v)}
              index={5}
            />
            <MetricCard
              icon={Target}
              label="Requirement coverage"
              value={metrics.data.requirement_coverage_avg}
              format={(v) => percent(v)}
              index={6}
            />
            <MetricCard
              icon={Sparkles}
              label="Recommendation acceptance"
              value={metrics.data.recommendation_acceptance_rate}
              format={(v) => percent(v)}
              index={7}
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
                <Metric label="Calls" value={metrics.data.llm.calls} format={compactNumber} />
                <Metric label="Failures" value={metrics.data.llm.failures} format={compactNumber} />
                <Metric
                  label="Fallback rate"
                  value={metrics.data.llm.fallback_rate}
                  format={(v) => percent(v, 1)}
                />
                <Metric
                  label="Avg latency"
                  value={metrics.data.llm.avg_latency_ms}
                  format={(v) => `${Math.round(v)} ms`}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Feedback breakdown</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                {Object.entries(metrics.data.feedback).map(([type, count], i) => (
                  <BarRow
                    key={type}
                    label={titleCase(type)}
                    value={count}
                    max={Math.max(...Object.values(metrics.data!.feedback), 1)}
                    index={i}
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
                {metrics.data.top_categories.map((c, i) => (
                  <BarRow
                    key={c.category}
                    label={titleCase(c.category)}
                    value={c.count}
                    max={metrics.data!.top_categories[0].count}
                    index={i}
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
                      {logs.data.logs.map((log, i) => (
                        <motion.tr
                          key={log.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          // Capped: 60 rows at a real stagger would take four
                          // seconds to finish, and this is a table you scan.
                          transition={{ duration: 0.25, delay: Math.min(i, 12) * 0.02 }}
                          className="border-b border-border/60 last:border-0"
                        >
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
                        </motion.tr>
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

/**
 * Metric cards take the raw number and a formatter rather than a
 * pre-formatted string, so the figure can count up to its value. The
 * formatter is the same one that would have produced the static string --
 * nothing here rounds or derives anything the API did not send.
 */
function MetricCard({
  icon: Icon,
  label,
  value,
  format,
  index = 0,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  format: (v: number) => string;
  index?: number;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: EASE_OUT, delay: reduced ? 0 : index * 0.04 }}
      whileHover={reduced ? undefined : HOVER_LIFT}
    >
      <Card>
        <CardContent className="p-4">
          <div className="mb-2 flex items-center gap-2 text-muted-foreground">
            <Icon className="size-3.5" />
            <span className="text-[11px] uppercase tracking-wide">{label}</span>
          </div>
          <p className="tabular text-xl font-semibold text-foreground">
            <CountUp value={value} format={format} duration={0.9} />
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function Metric({
  label,
  value,
  format,
}: {
  label: string;
  value: number;
  format: (v: number) => string;
}) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="tabular text-base font-semibold text-foreground">
        <CountUp value={value} format={format} duration={0.9} />
      </p>
    </div>
  );
}

function BarRow({
  label,
  value,
  max,
  index = 0,
}: {
  label: string;
  value: number;
  max: number;
  index?: number;
}) {
  const reduced = useReducedMotion();
  const width = `${max > 0 ? Math.round((value / max) * 100) : 0}%`;
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-32 shrink-0 text-muted-foreground">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <motion.div
          className={cn("h-full rounded-full bg-primary")}
          initial={reduced ? false : { width: 0 }}
          animate={{ width }}
          transition={{ duration: 0.6, ease: EASE_OUT, delay: reduced ? 0 : index * 0.06 }}
        />
      </div>
      <span className="tabular w-10 shrink-0 text-right font-medium">
        <CountUp value={value} format={(v) => String(Math.round(v))} duration={0.6} />
      </span>
    </div>
  );
}
