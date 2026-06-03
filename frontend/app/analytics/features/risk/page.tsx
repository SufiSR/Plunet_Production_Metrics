"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AnalyticsFilterPanel } from "@/app/components/jira-analytics/AnalyticsReportControls";
import { FeatureMetricCard, FeatureReportLayout } from "@/app/components/jira-analytics/FeatureReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

interface RiskRow {
  feature_key: string;
  feature_title: string;
  status: string;
  hours: number;
  production_duration_days: number | null;
  lifecycle_duration_days: number | null;
  idle_before_work_days: number | null;
  size_risk_points: number;
  duration_risk_points: number;
  risk_drivers: string[];
  risk_score: number;
  member_issue_count: number;
  child_issue_count: number;
  done_member_issue_count: number;
  open_member_issue_count: number;
  blocked_member_issue_count: number;
  max_hierarchy_depth: number;
  done_member_ratio: number;
  structure_signal: string;
}

export default function Page() {
  const [data, setData] = useState<AnalyticsReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [includeDone, setIncludeDone] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalyticsReport(reportPaths.featureRisk));
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Failed to load feature risk");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => (data?.table ?? []).map(toRiskRow).filter((row): row is RiskRow => row !== null), [data]);
  const visibleRows = useMemo(
    () => rows.filter((row) => includeDone || !isDoneStatus(row.status)),
    [includeDone, rows],
  );
  const hiddenDoneCount = rows.length - visibleRows.length;
  const empty = Boolean(!loading && !error && data && visibleRows.length === 0);

  return (
    <JiraAnalyticsShell
      title="Feature delivery risk"
      description="Features scored by size, duration, and workflow risk signals."
      hidePageHeader
      hideMethodology
    >
      <FeatureReportLayout
        activeReport="risk"
        title="Spot active features that need delivery attention."
        description="A live risk view for PMGT features that are still in motion. Completed features are hidden by default and can be included for retrospective analysis."
        metrics={<RiskMetrics rows={visibleRows} totalRows={rows.length} hiddenDoneCount={hiddenDoneCount} />}
        controls={
          <AnalyticsFilterPanel title="Filters" description="Operational view defaults to active work. Include done features when you want historical context.">
            <label className="inline-flex items-center gap-3 rounded-2xl border border-outline-variant/25 bg-surface px-4 py-3 text-sm font-semibold text-on-surface shadow-sm">
              <input
                type="checkbox"
                checked={includeDone}
                onChange={(event) => setIncludeDone(event.target.checked)}
                className="h-4 w-4 rounded border-outline-variant text-primary focus:ring-primary"
              />
              Include done features
              {hiddenDoneCount > 0 ? (
                <span className="rounded-full bg-surface-container-low px-2 py-0.5 text-xs font-medium text-on-surface-variant">
                  {hiddenDoneCount} hidden
                </span>
              ) : null}
            </label>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          error={error}
          empty={empty}
          emptyMessage="No active feature risks for the selected filters."
        >
          <ModernReportCard
            eyebrow="Active risk"
            title="Feature risk reasons"
            description="Each row shows the score, what drove it, and whether the feature is well decomposed or still structurally risky."
          >
            <RiskTable rows={visibleRows} />
          </ModernReportCard>
        </ReportPageFrame>
      </FeatureReportLayout>
    </JiraAnalyticsShell>
  );
}

function RiskMetrics({
  rows,
  totalRows,
  hiddenDoneCount,
}: {
  rows: RiskRow[];
  totalRows: number;
  hiddenDoneCount: number;
}) {
  const highRiskRows = rows.filter((row) => row.risk_score >= 40);
  const totalHours = rows.reduce((sum, row) => sum + row.hours, 0);

  return (
    <>
      <FeatureMetricCard label="Active features" value={totalRows ? String(rows.length) : "Loading"} detail={`${hiddenDoneCount} done hidden by default`} />
      <FeatureMetricCard label="High risk" value={totalRows ? String(highRiskRows.length) : "Loading"} detail="Risk score >= 40" />
      <FeatureMetricCard label="Hours" value={formatCompactHours(totalHours)} detail="Visible feature effort" />
    </>
  );
}

function RiskTable({ rows }: { rows: RiskRow[] }) {
  return (
    <div className="max-h-[36rem] overflow-auto rounded-2xl elevated-panel">
      <table className="w-full min-w-[1120px] text-sm">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant/20 text-on-surface-variant">
            <th className="px-3 py-3 text-left font-medium">Feature</th>
            <th className="px-3 py-3 text-left font-medium">Status</th>
            <th className="px-3 py-3 text-left font-medium">Why risky?</th>
            <th className="px-3 py-3 text-left font-medium">Structure</th>
            <th className="px-3 py-3 text-right font-medium">Hours</th>
            <th className="px-3 py-3 text-right font-medium">Production days</th>
            <th className="px-3 py-3 text-right font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.feature_key} className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5">
              <td className="max-w-xs px-3 py-3 align-top">
                <Link href={`/analytics/features/${encodeURIComponent(row.feature_key)}`} className="font-semibold text-primary hover:underline">
                  {row.feature_key}
                </Link>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-on-surface-variant">{row.feature_title}</p>
              </td>
              <td className="px-3 py-3 align-top text-on-surface">{row.status || "Unknown"}</td>
              <td className="px-3 py-3 align-top">
                <div className="flex max-w-md flex-wrap gap-1.5">
                  {riskBadges(row).map((badge) => (
                    <span
                      key={badge.key}
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${badge.className}`}
                      title={badge.title}
                    >
                      {badge.label}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-xs text-on-surface-variant">
                  {row.size_risk_points.toFixed(1)} score points from size, {row.duration_risk_points.toFixed(1)} from production duration.
                </p>
              </td>
              <td className="px-3 py-3 align-top">
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${structureBadgeClass(row.structure_signal)}`}>
                  {structureLabel(row.structure_signal)}
                </span>
                <p className="mt-2 text-xs leading-5 text-on-surface-variant">
                  {row.child_issue_count} child issues, {row.open_member_issue_count} open, {formatPercent(row.done_member_ratio)} done.
                </p>
              </td>
              <td className="px-3 py-3 text-right tabular-nums align-top text-on-surface">{formatNumber(row.hours)}</td>
              <td className="px-3 py-3 text-right tabular-nums align-top text-on-surface">
                {row.production_duration_days ?? "Unknown"}
              </td>
              <td className="px-3 py-3 text-right tabular-nums align-top">
                <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${riskScoreClass(row.risk_score)}`}>
                  {row.risk_score.toFixed(1)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function toRiskRow(row: Record<string, unknown>): RiskRow | null {
  const featureKey = stringValue(row.feature_key);
  if (!featureKey) return null;
  return {
    feature_key: featureKey,
    feature_title: stringValue(row.feature_title) || featureKey,
    status: stringValue(row.status),
    hours: numberValue(row.hours),
    production_duration_days: nullableNumber(row.production_duration_days),
    lifecycle_duration_days: nullableNumber(row.lifecycle_duration_days),
    idle_before_work_days: nullableNumber(row.idle_before_work_days),
    size_risk_points: numberValue(row.size_risk_points),
    duration_risk_points: numberValue(row.duration_risk_points),
    risk_drivers: stringList(row.risk_drivers),
    risk_score: numberValue(row.risk_score),
    member_issue_count: numberValue(row.member_issue_count),
    child_issue_count: numberValue(row.child_issue_count),
    done_member_issue_count: numberValue(row.done_member_issue_count),
    open_member_issue_count: numberValue(row.open_member_issue_count),
    blocked_member_issue_count: numberValue(row.blocked_member_issue_count),
    max_hierarchy_depth: numberValue(row.max_hierarchy_depth),
    done_member_ratio: numberValue(row.done_member_ratio),
    structure_signal: stringValue(row.structure_signal) || "unknown_structure",
  };
}

function riskBadges(row: RiskRow): { key: string; label: string; title: string; className: string }[] {
  const badges = row.risk_drivers.map((driver) => ({
    key: driver,
    label: driverLabel(driver, row),
    title: driverTitle(driver),
    className: driverClass(driver),
  }));
  if (badges.length === 0) {
    badges.push({
      key: "balanced",
      label: "No dominant driver",
      title: "Risk is currently spread across smaller signals.",
      className: "bg-surface-container text-on-surface-variant",
    });
  }
  return badges;
}

function driverLabel(driver: string, row: RiskRow): string {
  switch (driver) {
    case "large_scope":
      return `Large: ${formatNumber(row.hours)}h`;
    case "medium_scope":
      return `Size: ${formatNumber(row.hours)}h`;
    case "long_running":
      return `Long-running: ${row.production_duration_days}d`;
    case "extended_duration":
      return `Duration: ${row.production_duration_days}d`;
    case "idle_before_start":
      return `Idle before start: ${row.idle_before_work_days}d`;
    case "missing_production_duration":
      return "No production span yet";
    case "under_defined":
      return "Under-defined";
    case "broad_scope":
      return "Broad scope";
    case "integration_risk":
      return "Integration risk";
    case "blocked_structure":
      return "Blocked child work";
    case "well_decomposed":
      return "Well decomposed";
    default:
      return humanize(driver);
  }
}

function driverTitle(driver: string): string {
  switch (driver) {
    case "well_decomposed":
      return "The feature has several child issues and most are already complete.";
    case "under_defined":
      return "The feature has little or no child issue breakdown.";
    case "broad_scope":
      return "The feature has many child issues but less than half are complete.";
    case "integration_risk":
      return "The feature has deep or broad open child work, which can add coordination risk.";
    default:
      return humanize(driver);
  }
}

function driverClass(driver: string): string {
  if (driver === "well_decomposed") return "bg-emerald-500/10 text-emerald-700";
  if (driver === "missing_production_duration") return "bg-surface-container text-on-surface-variant";
  if (driver === "medium_scope" || driver === "extended_duration") return "bg-amber-500/10 text-amber-700";
  return "bg-error/10 text-error";
}

function structureLabel(signal: string): string {
  switch (signal) {
    case "well_decomposed":
      return "Well decomposed";
    case "some_decomposition":
      return "Some decomposition";
    case "under_defined":
      return "Under-defined";
    case "broad_scope":
      return "Broad scope";
    case "integration_risk":
      return "Integration risk";
    case "blocked_structure":
      return "Blocked structure";
    default:
      return "Unknown structure";
  }
}

function structureBadgeClass(signal: string): string {
  if (signal === "well_decomposed") return "bg-emerald-500/10 text-emerald-700";
  if (signal === "some_decomposition") return "bg-primary/10 text-primary";
  if (signal === "unknown_structure") return "bg-surface-container text-on-surface-variant";
  return "bg-amber-500/10 text-amber-700";
}

function riskScoreClass(score: number): string {
  if (score >= 40) return "bg-error/10 text-error";
  if (score >= 20) return "bg-amber-500/10 text-amber-700";
  return "bg-emerald-500/10 text-emerald-700";
}

function isDoneStatus(status: string): boolean {
  const normalized = status.trim().toLowerCase();
  return ["done", "closed", "resolved", "released", "shipped"].includes(normalized);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
