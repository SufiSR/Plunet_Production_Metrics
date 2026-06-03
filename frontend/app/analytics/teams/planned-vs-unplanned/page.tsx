"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { lastTwelveMonths } from "@/lib/jira-analytics-dates";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
import { useReportChartTheme } from "@/lib/chart-colors";
import {
  compareSortableValues,
  nextSortState,
  sortRecordsByPeriodAsc,
  type SortState,
} from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

const copy = TEAM_PAGE_COPY["planned-vs-unplanned"];

export default function Page() {
  const chartTheme = useReportChartTheme();
  const defaultRange = useMemo(() => lastTwelveMonths(), []);
  const [params, setParams] = useState<ReportQueryParams>(defaultRange);
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [params],
    load: (signal) => fetchAnalyticsReport(reportPaths.plannedVsUnplanned, params, signal),
  });
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");
  const [sort, setSort] = useState<
    SortState<"month" | "team" | "roadmap_hours" | "continuous_improvement_hours" | "roadmap_focus"> | null
  >({
    key: "month",
    direction: "desc",
  });

  const teams = useMemo(() => {
    const availableTeams = new Set(stringList(data?.filters?.available_teams));
    return FOCUSED_TEAMS.filter((team) => availableTeams.has(team));
  }, [data?.filters?.available_teams]);
  const rows = useMemo(() => {
    const table = (data?.table ?? []) as Array<Record<string, unknown>>;
    return table.flatMap((row) => {
      const month = typeof row.month === "string" ? row.month : null;
      const team = typeof row.team === "string" ? row.team : null;
      if (!month || !team) return [];
      if (!FOCUSED_TEAMS_SET.has(team)) return [];
      return [
        {
          month,
          team,
          roadmap_hours: numberValue(row.roadmap_hours),
          continuous_improvement_hours: numberValue(row.continuous_improvement_hours),
          roadmap_focus: nullableNumberValue(row.roadmap_focus),
        },
      ];
    });
  }, [data?.table]);

  const sortedRows = useMemo(() => {
    const defaultSorted = [...rows].sort(
      (a, b) => compareSortableValues(a.month, b.month, "desc") || compareSortableValues(a.team, b.team, "asc"),
    );
    if (!sort) return defaultSorted;
    return [...defaultSorted].sort((a, b) => compareSortableValues(a[sort.key], b[sort.key], sort.direction));
  }, [rows, sort]);

  const chartData = useMemo(() => {
    const source = (data?.series ?? []) as Array<Record<string, unknown>>;
    const chartRows = source.flatMap((row) => {
      const period = typeof row.period === "string" ? row.period : null;
      if (!period) return [];
      const shaped: Record<string, string | number> = { period };
      for (const team of teams) {
        shaped[team] = numberValue(row[team]);
      }
      return [shaped];
    });
    return sortRecordsByPeriodAsc(chartRows);
  }, [data?.series, teams]);

  const empty = Boolean(!loading && !refreshing && !error && rows.length === 0);
  const latestFocus = rows.length
    ? rows.reduce((best, row) => ((row.roadmap_focus ?? -1) > (best.roadmap_focus ?? -1) ? row : best))
    : null;

  return (
    <JiraAnalyticsShell title="Roadmap focus" description="" hidePageHeader hideMethodology>
      <TeamReportLayout
        activeReport="planned-vs-unplanned"
        title={copy.heroTitle}
        description={copy.heroDescription}
        readingTip={copy.readingTip}
        metrics={
          <>
            <TeamMetricCard label="Rows" value={rows.length ? String(rows.length) : "Loading"} detail="Team-month slices" />
            <TeamMetricCard label="Teams" value={teams.length ? String(teams.length) : "Loading"} detail="Focused engineering teams" />
            <TeamMetricCard
              label="Peak focus"
              value={formatRatio(latestFocus?.roadmap_focus ?? null)}
              detail={latestFocus ? `${latestFocus.team} · ${latestFocus.month}` : "Highest roadmap share"}
            />
          </>
        }
        controls={
          <AnalyticsFilterPanel title="Period and view" description="Focused teams: Cosmic Coders, Team Tantrum, Team World.">
            <FilterField label="From">
              <input
                type="date"
                value={params.from ?? ""}
                onChange={(event) => setParams((prev) => ({ ...prev, from: event.target.value || undefined }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="To">
              <input
                type="date"
                value={params.to ?? ""}
                onChange={(event) => setParams((prev) => ({ ...prev, to: event.target.value || undefined }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="Team" className="min-w-[14rem]">
              <select
                value={params.team ?? ""}
                onChange={(event) => setParams((prev) => ({ ...prev, team: event.target.value || undefined }))}
                className={filterInputClassName()}
              >
                <option value="">All focused teams</option>
                {teams.map((team) => (
                  <option key={team} value={team}>
                    {team}
                  </option>
                ))}
              </select>
            </FilterField>
            <div className="flex gap-2 self-end">
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`h-11 rounded-xl border px-4 text-sm font-semibold ${
                  viewMode === "table"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-outline-variant/40 text-on-surface"
                }`}
              >
                Table
              </button>
              <button
                type="button"
                onClick={() => setViewMode("chart")}
                className={`h-11 rounded-xl border px-4 text-sm font-semibold ${
                  viewMode === "chart"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-outline-variant/40 text-on-surface"
                }`}
              >
                Chart
              </button>
            </div>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage="No roadmap focus data for the selected period."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
          <ModernReportCard
            eyebrow={viewMode === "chart" ? "Trend" : "Evidence"}
            title={viewMode === "chart" ? "Roadmap focus over time" : "Monthly team breakdown"}
            description="Roadmap hours versus continuous improvement (tech support, unassigned bugs, issues without feature)."
          >
        {viewMode === "chart" ? (
          <div className="analytics-chart-plot h-[26rem] w-full p-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid {...chartTheme.gridProps} />
                <XAxis
                  dataKey="period"
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                />
                <YAxis tick={chartTheme.axisTick} axisLine={chartTheme.axisLine} tickLine={chartTheme.tickLine} />
                <Tooltip
                  formatter={(value, name) => [formatRatio(value), String(name)]}
                  labelFormatter={(label) => `Month: ${String(label)}`}
                  contentStyle={{
                    background: chartTheme.colors.tooltipBg,
                    color: chartTheme.colors.tooltipText,
                    border: "none",
                    borderRadius: "0.5rem",
                  }}
                />
                <Legend />
                {teams.map((team, index) => (
                  <Line
                    key={team}
                    type="monotone"
                    dataKey={team}
                    stroke={chartTheme.series[index % chartTheme.series.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-outline-variant/20 max-h-[32rem] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-surface-container-low">
                <tr className="border-b border-outline-variant/20">
                  <HeaderCell label="Month" sortKey="month" sort={sort} setSort={setSort} />
                  <HeaderCell label="Team" sortKey="team" sort={sort} setSort={setSort} />
                  <HeaderCell label="Roadmap Hours" sortKey="roadmap_hours" sort={sort} setSort={setSort} numeric />
                  <HeaderCell label="Continuous Improvement" sortKey="continuous_improvement_hours" sort={sort} setSort={setSort} numeric />
                  <HeaderCell label="Roadmap Focus" sortKey="roadmap_focus" sort={sort} setSort={setSort} numeric />
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, index) => (
                  <tr key={`${row.team}-${row.month}-${index}`} className="border-b border-outline-variant/10">
                    <td className="px-3 py-2 text-on-surface">{row.month}</td>
                    <td className="px-3 py-2 text-on-surface">{row.team}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.roadmap_hours.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.continuous_improvement_hours.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatRatio(row.roadmap_focus)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
          </ModernReportCard>
        </ReportPageFrame>
      </TeamReportLayout>
    </JiraAnalyticsShell>
  );
}

const FOCUSED_TEAMS = ["Cosmic Coders", "Team Tantrum", "Team World"] as const;
const FOCUSED_TEAMS_SET = new Set<string>(FOCUSED_TEAMS);

function HeaderCell({
  label,
  sortKey,
  sort,
  setSort,
  numeric = false,
}: {
  label: string;
  sortKey: "month" | "team" | "roadmap_hours" | "continuous_improvement_hours" | "roadmap_focus";
  sort: SortState<"month" | "team" | "roadmap_hours" | "continuous_improvement_hours" | "roadmap_focus"> | null;
  setSort: (
    sort: SortState<"month" | "team" | "roadmap_hours" | "continuous_improvement_hours" | "roadmap_focus"> | null,
  ) => void;
  numeric?: boolean;
}) {
  const direction = sort?.key === sortKey ? sort.direction : null;
  return (
    <th className={`px-3 py-2 font-medium text-on-surface-variant ${numeric ? "text-right" : "text-left"}`}>
      <button
        type="button"
        onClick={() => setSort(nextSortState(sort, sortKey))}
        className={`inline-flex items-center gap-1 hover:text-on-surface ${numeric ? "justify-end" : "justify-start"}`}
      >
        <span>{label}</span>
        <span className="text-[10px]">{direction === "asc" ? "▲" : direction === "desc" ? "▼" : "↕"}</span>
      </button>
    </th>
  );
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nullableNumberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatRatio(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}
