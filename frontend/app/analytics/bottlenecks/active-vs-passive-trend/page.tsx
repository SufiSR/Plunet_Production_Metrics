"use client";

import { useMemo, useState } from "react";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import {
  BottleneckMetricCard,
  BottleneckReportLayout,
} from "@/app/components/jira-analytics/BottleneckReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { lastFourQuartersRange } from "@/lib/jira-analytics-dates";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { useReportChartTheme } from "@/lib/chart-colors";
import { comparePeriodValuesAsc } from "@/lib/jira-analytics-sort";
import {
  ELAPSED_TIME_NOTE,
  formatElapsedDays,
  formatElapsedDaysDelta,
  hoursToElapsedDays,
} from "@/lib/elapsed-time-format";
import {
  MAIN_DELIVERY_WORKFLOWS,
  MAIN_DELIVERY_WORKFLOW_LABELS,
} from "@/lib/jira-analytics-workflows";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

interface TrendFilters {
  from: string;
  to: string;
  team: string;
  workflow: string;
}

interface TrendRow {
  period: string;
  quarter: string;
  quarter_start: string;
  quarter_end: string;
  team: string;
  workflow: string;
  active_hours: number;
  passive_hours: number;
  product_queue_hours: number;
  dev_queue_hours: number;
  qa_queue_hours: number;
  total_hours: number;
  passive_share: number | null;
  passive_share_delta: number | null;
  total_hours_delta: number | null;
}

interface TrendSeriesRow {
  period: string;
  quarter: string;
  quarter_start: string;
  quarter_end: string;
  active_hours: number;
  passive_hours: number;
  product_queue_hours: number;
  dev_queue_hours: number;
  qa_queue_hours: number;
  total_hours: number;
  passive_share: number | null;
  passive_share_delta: number | null;
}

const QUEUE_COLUMNS = [
  { key: "product_queue_hours", label: "Product Queue" },
  { key: "dev_queue_hours", label: "Dev Queue" },
  { key: "qa_queue_hours", label: "QA Queue" },
] as const;

function toQueryParams(filters: TrendFilters): ReportQueryParams {
  return {
    from: filters.from,
    to: filters.to,
    team: filters.team || undefined,
    workflow: filters.workflow || undefined,
  };
}

export default function Page() {
  const defaultRange = useMemo(() => lastFourQuartersRange(), []);
  const [draftFilters, setDraftFilters] = useState<TrendFilters>({
    from: defaultRange.from,
    to: defaultRange.to,
    team: "",
    workflow: "",
  });
  const [queryParams, setQueryParams] = useState<ReportQueryParams>(toQueryParams({
    from: defaultRange.from,
    to: defaultRange.to,
    team: "",
    workflow: "",
  }));
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [queryParams],
    load: (signal) => fetchAnalyticsReport(reportPaths.activeVsPassiveTrend, queryParams, signal),
    slowAfterMs: 8_000,
  });

  const rows = useMemo(() => (data?.table ?? []).map(toTrendRow).filter((row): row is TrendRow => row !== null), [data]);
  const series = useMemo(
    () =>
      (data?.series ?? [])
        .map(toTrendSeriesRow)
        .filter((row): row is TrendSeriesRow => row !== null)
        .sort((a, b) => comparePeriodValuesAsc(a.quarter_start, b.quarter_start)),
    [data],
  );
  const availableTeams = stringList(data?.filters?.available_teams);
  const availableWorkflows = useMemo(() => {
    const fromApi = stringList(data?.filters?.available_workflows);
    return fromApi.length > 0 ? fromApi : [...MAIN_DELIVERY_WORKFLOW_LABELS];
  }, [data?.filters?.available_workflows]);
  const sortedRows = useMemo(
    () =>
      [...rows].sort(
        (a, b) =>
          b.quarter_start.localeCompare(a.quarter_start) ||
          numberOrMinusOne(b.passive_share) - numberOrMinusOne(a.passive_share) ||
          a.team.localeCompare(b.team),
      ),
    [rows],
  );
  const empty = Boolean(!loading && !refreshing && !error && data && rows.length === 0 && series.length === 0);

  const applyDateFilters = () => {
    setQueryParams(toQueryParams(draftFilters));
  };

  const updateSliceFilter = (patch: Partial<Pick<TrendFilters, "team" | "workflow">>) => {
    setDraftFilters((prev) => {
      const next = { ...prev, ...patch };
      setQueryParams(toQueryParams(next));
      return next;
    });
  };

  return (
    <JiraAnalyticsShell
      title="Active vs passive trend"
      description="Quarterly trend for active work compared with queue and waiting elapsed time."
      hidePageHeader
      hideMethodology
    >
      <BottleneckReportLayout
        activeReport="active-vs-passive-trend"
        title="See whether workflow waiting is improving or degrading."
        description={`A quarterly trend view that attributes active and passive workflow elapsed time to the quarter where it actually happened, not just to when the issue was created. ${ELAPSED_TIME_NOTE}`}
        mainWorkflowLineage={MAIN_DELIVERY_WORKFLOWS.map((workflow) => ({
          label: workflow.label,
          purpose: workflow.purpose,
          issueTypes: workflow.issueTypes,
        }))}
        metrics={<TrendMetrics data={data} series={series} />}
        controls={
          <AnalyticsFilterPanel
            title="Quarterly filters"
            description="Date range uses Refresh. Team and workflow apply immediately. Default window is the last four quarters."
          >
            <FilterField label="From">
              <input
                type="date"
                value={draftFilters.from}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, from: event.target.value }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="To">
              <input
                type="date"
                value={draftFilters.to}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, to: event.target.value }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="Team" className="min-w-[14rem]">
              <select
                value={draftFilters.team}
                onChange={(event) => updateSliceFilter({ team: event.target.value })}
                className={filterInputClassName()}
              >
                <option value="">All teams</option>
                {availableTeams.map((team) => (
                  <option key={team} value={team}>
                    {team}
                  </option>
                ))}
              </select>
            </FilterField>
            <FilterField label="Workflow" className="min-w-[16rem]">
              <select
                value={draftFilters.workflow}
                onChange={(event) => updateSliceFilter({ workflow: event.target.value })}
                className={filterInputClassName()}
              >
                <option value="">All workflows</option>
                {availableWorkflows.map((workflow) => (
                  <option key={workflow} value={workflow}>
                    {workflow}
                  </option>
                ))}
              </select>
            </FilterField>
            <div className="flex gap-2 self-end">
              <button
                type="button"
                onClick={applyDateFilters}
                disabled={loading && !refreshing}
                className="h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Apply dates
              </button>
              <button
                type="button"
                onClick={() => {
                  const range = lastFourQuartersRange();
                  const next = { from: range.from, to: range.to, team: "", workflow: "" };
                  setDraftFilters(next);
                  setQueryParams(toQueryParams(next));
                }}
                className="h-11 rounded-xl border border-outline-variant/40 px-4 text-sm font-semibold text-on-surface hover:bg-surface-container-high"
              >
                Last 4 quarters
              </button>
            </div>
          </AnalyticsFilterPanel>
        }
        readingTip="Read the line first: down means passive share improved, up means more elapsed time is waiting. Then use the table to find which team and workflow drove the quarterly movement."
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage="No active/passive trend data for the selected filters."
          loadingTitle="Building quarterly trend"
          loadingHint="Splitting status intervals across quarters and teams. This can take longer than simpler reports."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
          <div className="space-y-6">
            <ModernReportCard
              eyebrow="Quarterly trend"
              title="Active work vs passive elapsed time"
              description={`Bars show active and passive elapsed calendar days by quarter. The line shows passive share, so improvement or degradation is visible even when volume changes. ${ELAPSED_TIME_NOTE}`}
            >
              <TrendChart rows={series} />
            </ModernReportCard>

            <ModernReportCard
              eyebrow="Quarter evidence"
              title="Team and workflow deltas"
              description="Quarterly rows with passive share and elapsed-day delta against the previous quarter for the same team and workflow."
            >
              <TrendTable rows={sortedRows} />
            </ModernReportCard>
          </div>
        </ReportPageFrame>
      </BottleneckReportLayout>
    </JiraAnalyticsShell>
  );
}

function TrendMetrics({ data, series }: { data: AnalyticsReportResponse | null; series: TrendSeriesRow[] }) {
  const latestShare = numberOrNull(data?.summary?.latest_passive_share);
  const delta = numberOrNull(data?.summary?.passive_share_delta);
  const latest = series.find((row) => row.total_hours > 0);
  const worstQueue = latest ? worstQueueBucket(latest) : null;

  return (
    <>
      <BottleneckMetricCard label="Latest passive share" value={formatPercent(latestShare)} detail={String(data?.summary?.latest_quarter ?? "Latest quarter")} />
      <BottleneckMetricCard label="Vs previous quarter" value={formatDeltaPercent(delta)} detail={delta === null ? "Needs two populated quarters" : delta <= 0 ? "Improved or stable" : "Degraded"} />
      <BottleneckMetricCard label="Worst queue" value={worstQueue?.label ?? "Loading"} detail={worstQueue ? `${formatElapsedDays(worstQueue.hours)} latest quarter` : "Latest quarter queue driver"} />
    </>
  );
}

function TrendChart({ rows }: { rows: TrendSeriesRow[] }) {
  const chartTheme = useReportChartTheme();

  if (!rows.length) {
    return <p className="text-sm text-on-surface-variant">No quarterly trend data for the selected filters.</p>;
  }

  const chartRows = rows.map((row) => ({
    ...row,
    active_elapsed_days: hoursToElapsedDays(row.active_hours),
    passive_elapsed_days: hoursToElapsedDays(row.passive_hours),
    passive_share_percent: row.passive_share === null ? null : row.passive_share * 100,
  }));

  return (
    <div className="analytics-chart-plot h-[360px] w-full p-2">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartRows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid {...chartTheme.gridProps} vertical={false} />
          <XAxis
            dataKey="period"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
          />
          <YAxis
            yAxisId="elapsedDays"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
            tickFormatter={(value) => `${Number(value ?? 0).toFixed(0)} d`}
          />
          <YAxis
            yAxisId="share"
            orientation="right"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            formatter={(value, name) => {
              if (name === "passive_share_percent") return [`${Number(value ?? 0).toFixed(1)}%`, "Passive share"];
              return [`${Number(value ?? 0).toFixed(1)} d`, chartLabel(String(name))];
            }}
            contentStyle={{
              background: chartTheme.colors.tooltipBg,
              color: chartTheme.colors.tooltipText,
              border: "none",
              borderRadius: "0.5rem",
            }}
          />
          <Legend formatter={(value) => chartLabel(String(value))} />
          <Bar
            yAxisId="elapsedDays"
            dataKey="active_elapsed_days"
            stackId="elapsedDays"
            fill={chartTheme.series[1]}
            radius={[0, 0, 0, 0]}
          />
          <Bar
            yAxisId="elapsedDays"
            dataKey="passive_elapsed_days"
            stackId="elapsedDays"
            fill={chartTheme.series[2]}
            radius={[8, 8, 0, 0]}
          />
          <Line
            yAxisId="share"
            type="monotone"
            dataKey="passive_share_percent"
            stroke={chartTheme.series[0]}
            strokeWidth={3}
            dot={{ r: 4 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function TrendTable({ rows }: { rows: TrendRow[] }) {
  if (!rows.length) {
    return <p className="text-sm text-on-surface-variant">No quarterly rows for the selected filters.</p>;
  }

  return (
    <div className="max-h-[34rem] overflow-auto rounded-2xl elevated-panel">
      <table className="w-full min-w-[68rem] text-sm">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant/20 text-on-surface-variant">
            <th className="px-3 py-2 text-left font-medium">Quarter</th>
            <th className="px-3 py-2 text-left font-medium">Team</th>
            <th className="px-3 py-2 text-left font-medium">Workflow</th>
            <th className="px-3 py-2 text-right font-medium">Active elapsed</th>
            <th className="px-3 py-2 text-right font-medium">Passive elapsed</th>
            <th className="px-3 py-2 text-right font-medium">Passive Share</th>
            <th className="px-3 py-2 text-right font-medium">Share Delta</th>
            <th className="px-3 py-2 text-right font-medium">Elapsed Delta</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.period}-${row.team}-${row.workflow}`} className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5">
              <td className="px-3 py-2 font-medium text-on-surface">{row.period}</td>
              <td className="px-3 py-2 text-on-surface">{row.team}</td>
              <td className="px-3 py-2 text-on-surface">{row.workflow}</td>
              <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatElapsedDays(row.active_hours)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatElapsedDays(row.passive_hours)}</td>
              <td className="px-3 py-2 text-right tabular-nums font-semibold text-on-surface">{formatPercent(row.passive_share)}</td>
              <td className={`px-3 py-2 text-right tabular-nums font-semibold ${deltaTone(row.passive_share_delta)}`}>
                {formatDeltaPercent(row.passive_share_delta)}
              </td>
              <td className={`px-3 py-2 text-right tabular-nums ${deltaTone(row.total_hours_delta)}`}>
                {formatElapsedDaysDelta(row.total_hours_delta)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function toTrendRow(row: Record<string, unknown>): TrendRow | null {
  const period = stringValue(row.period);
  const team = stringValue(row.team);
  const workflow = stringValue(row.workflow);
  if (!period || !team || !workflow) return null;
  return {
    period,
    quarter: stringValue(row.quarter) || period,
    quarter_start: stringValue(row.quarter_start),
    quarter_end: stringValue(row.quarter_end),
    team,
    workflow,
    active_hours: numberValue(row.active_hours),
    passive_hours: numberValue(row.passive_hours),
    product_queue_hours: numberValue(row.product_queue_hours),
    dev_queue_hours: numberValue(row.dev_queue_hours),
    qa_queue_hours: numberValue(row.qa_queue_hours),
    total_hours: numberValue(row.total_hours),
    passive_share: nullableNumber(row.passive_share),
    passive_share_delta: nullableNumber(row.passive_share_delta),
    total_hours_delta: nullableNumber(row.total_hours_delta),
  };
}

function toTrendSeriesRow(row: Record<string, unknown>): TrendSeriesRow | null {
  const period = stringValue(row.period);
  if (!period) return null;
  return {
    period,
    quarter: stringValue(row.quarter) || period,
    quarter_start: stringValue(row.quarter_start),
    quarter_end: stringValue(row.quarter_end),
    active_hours: numberValue(row.active_hours),
    passive_hours: numberValue(row.passive_hours),
    product_queue_hours: numberValue(row.product_queue_hours),
    dev_queue_hours: numberValue(row.dev_queue_hours),
    qa_queue_hours: numberValue(row.qa_queue_hours),
    total_hours: numberValue(row.total_hours),
    passive_share: nullableNumber(row.passive_share),
    passive_share_delta: nullableNumber(row.passive_share_delta),
  };
}

function worstQueueBucket(row: TrendSeriesRow): { label: string; hours: number } | null {
  const [bucket] = QUEUE_COLUMNS.map((column) => ({
    label: column.label,
    hours: row[column.key],
  })).sort((a, b) => b.hours - a.hours);
  return bucket && bucket.hours > 0 ? bucket : null;
}

function chartLabel(key: string): string {
  if (key === "active_elapsed_days") return "Active elapsed days";
  if (key === "passive_elapsed_days") return "Passive elapsed days";
  if (key === "passive_share_percent") return "Passive share";
  return key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.length > 0) : [];
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numberOrMinusOne(value: number | null): number {
  return value ?? -1;
}

function formatPercent(value: number | null): string {
  return value === null ? "Loading" : `${(value * 100).toFixed(1)}%`;
}

function formatDeltaPercent(value: number | null): string {
  if (value === null) return "n/a";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)} pp`;
}

function deltaTone(value: number | null): string {
  if (value === null || value === 0) return "text-on-surface-variant";
  return value > 0 ? "text-error" : "text-emerald-700";
}
