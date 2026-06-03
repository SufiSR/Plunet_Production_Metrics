"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { JiraIssueLink, jiraBrowseUrl } from "@/app/components/jira-analytics/JiraIssueLink";
import { useJiraBaseUrl } from "@/app/components/jira-analytics/JiraAnalyticsContext";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { TeamStatsSection, type TeamStatsConfig } from "@/app/components/jira-analytics/TeamStatsSection";
import { useReportChartTheme } from "@/lib/chart-colors";
import {
  compareSortableValues,
  newestDateColumn,
  nextSortState,
  sortRecordsByPeriodAsc,
  type SortState,
} from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

interface AnalyticsReportViewProps {
  data: AnalyticsReportResponse;
  chartKeys?: string[];
  hiddenColumns?: string[];
  rowFilter?: (row: Record<string, unknown>) => boolean;
  defaultTableSort?: (a: Record<string, unknown>, b: Record<string, unknown>) => number;
  rowVisibilityToggle?: {
    showLabel: string;
    hideLabel: string;
    hiddenRowsLabel: string;
    shouldHideByDefault: (row: Record<string, unknown>) => boolean;
  };
  teamStats?: TeamStatsConfig;
  trendEyebrow?: string;
  trendTitle?: string;
  trendDescription?: string;
  detailsEyebrow?: string;
  detailsTitle?: string;
  detailsDescription?: string;
}

type SortDirection = "asc" | "desc";
type HeatmapSortKey = "person" | "topic" | "hours";

const ISSUE_KEY_COLUMNS = new Set([
  "issue_key",
  "issue",
  "feature",
  "feature_key",
  "featureKey",
  "root_key",
]);

export function AnalyticsReportView({
  data,
  chartKeys,
  hiddenColumns = [],
  rowFilter,
  defaultTableSort,
  rowVisibilityToggle,
  teamStats,
  trendEyebrow = "Trend",
  trendTitle = "Capacity over time",
  trendDescription = "Stacked monthly allocation so the shape of the investment mix is visible before opening the table.",
  detailsEyebrow = "Details",
  detailsTitle = "Report table",
  detailsDescription = "Sortable source rows for auditability and follow-up analysis.",
}: AnalyticsReportViewProps) {
  const chartTheme = useReportChartTheme();
  const jiraBaseUrl = useJiraBaseUrl();
  const [sort, setSort] = useState<{ column: string; direction: SortDirection } | null>(null);
  const [heatmapSort, setHeatmapSort] = useState<SortState<HeatmapSortKey> | null>(null);
  const [showHiddenRows, setShowHiddenRows] = useState(false);
  const hiddenColumnSet = useMemo(() => new Set(hiddenColumns), [hiddenColumns]);

  const columns = useMemo(() => {
    if (!data.table?.length) return [];
    return Object.keys(data.table[0]).filter(
      (column) => !hiddenColumnSet.has(column) && !column.startsWith("_"),
    );
  }, [data.table, hiddenColumnSet]);
  const yearlyTeamAverages = useMemo(() => yearlyTeamAverageRows(data), [data]);
  const summaryYear =
    typeof data.filters?.summary_year === "number"
      ? data.filters.summary_year
      : new Date().getFullYear();
  const yearlyTeamAverageColumns = useMemo(
    () => reportColumns(yearlyTeamAverages, ["team", "year"]),
    [yearlyTeamAverages],
  );

  const filteredTable = useMemo(() => {
    if (!data.table?.length) return [];
    return rowFilter ? data.table.filter(rowFilter) : data.table;
  }, [data.table, rowFilter]);

  const displayedTable = useMemo(() => {
    if (!filteredTable.length) return [];
    if (!rowVisibilityToggle || showHiddenRows) return filteredTable;
    return filteredTable.filter((row) => !rowVisibilityToggle.shouldHideByDefault(row));
  }, [filteredTable, rowVisibilityToggle, showHiddenRows]);

  const hiddenRowCount = useMemo(() => {
    if (!filteredTable.length || !rowVisibilityToggle) return 0;
    return filteredTable.filter(rowVisibilityToggle.shouldHideByDefault).length;
  }, [filteredTable, rowVisibilityToggle]);

  const sortedTable = useMemo(() => {
    if (!displayedTable.length) return [];
    if (!sort && defaultTableSort) return [...displayedTable].sort(defaultTableSort);
    const defaultDateColumn = newestDateColumn(columns);
    if (!sort && defaultDateColumn) {
      return [...displayedTable].sort((a, b) =>
        compareValues(a[defaultDateColumn], b[defaultDateColumn], "desc"),
      );
    }
    if (!sort) return displayedTable;
    return [...displayedTable].sort((a, b) => compareValues(a[sort.column], b[sort.column], sort.direction));
  }, [columns, defaultTableSort, displayedTable, sort]);

  const chartData = useMemo(() => {
    const series = data.series ?? [];
    return series.some((row) => "period" in row) ? sortRecordsByPeriodAsc(series) : series;
  }, [data.series]);
  const keys =
    chartKeys ??
    (chartData.length
      ? Object.keys(chartData[0]).filter(
          (k) => k !== "period" && typeof chartData[0][k] === "number",
        )
      : []);

  const heatmapRows = useMemo(() => {
    if (data.table?.length) return null;
    if (!chartData.length) return null;
    const first = chartData[0];
    if (!("person" in first) || !("topics" in first)) return null;
    const rows: { person: string; topic: string; hours: number }[] = [];
    for (const entry of chartData) {
      const person = String(entry.person ?? "Unknown");
      const topics = entry.topics as Record<string, number> | undefined;
      if (!topics || typeof topics !== "object") continue;
      for (const [topic, hours] of Object.entries(topics)) {
        if (typeof hours === "number" && hours > 0) {
          rows.push({ person, topic, hours });
        }
      }
    }
    return rows.sort((a, b) => b.hours - a.hours).slice(0, 200);
  }, [chartData, data.table]);

  const sortedHeatmapRows = useMemo(() => {
    if (!heatmapRows) return null;
    if (!heatmapSort) return heatmapRows;
    return [...heatmapRows].sort((a, b) =>
      compareSortableValues(a[heatmapSort.key], b[heatmapSort.key], heatmapSort.direction),
    );
  }, [heatmapRows, heatmapSort]);

  return (
    <div className="space-y-8">
      {data.summary && Object.keys(data.summary).length > 0 ? (
        <div className="space-y-2">
          {teamStats?.showSummaryYearNote ? (
            <p className="text-xs text-on-surface-variant">
              Summary counts for calendar year {summaryYear} only.
            </p>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Object.entries(data.summary).map(([k, v]) => (
              <div key={k} className="elevated-panel rounded-2xl px-4 py-3">
                <span className="block text-xs font-medium uppercase tracking-[0.14em] text-on-surface-variant">{humanizeColumn(k)}</span>
                <span className="mt-2 block text-xl font-editorial font-bold text-on-surface">{formatSummaryValue(k, v)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {teamStats && yearlyTeamAverages.length > 0 ? (
        <TeamStatsSection
          rows={yearlyTeamAverages}
          config={teamStats}
          formatCell={(value, column) => formatCell(value, column, jiraBaseUrl)}
          humanizeColumn={humanizeColumn}
        />
      ) : null}

      {chartData.length > 0 && keys.length > 0 ? (
        <ModernReportCard
          eyebrow={trendEyebrow}
          title={trendTitle}
          description={trendDescription}
        >
          <div className="analytics-chart-plot h-80 w-full p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid {...chartTheme.gridProps} vertical={false} />
                <XAxis
                  dataKey="period"
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                />
                <YAxis
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                />
                <Tooltip
                  formatter={(value, name) => [formatChartValue(value), humanizeColumn(String(name))]}
                  contentStyle={{
                    background: chartTheme.colors.tooltipBg,
                    color: chartTheme.colors.tooltipText,
                    border: "none",
                    borderRadius: "0.5rem",
                  }}
                />
                <Legend formatter={(value) => humanizeColumn(String(value))} />
                {keys.map((key, i) => (
                  <Bar
                    key={key}
                    dataKey={key}
                    stackId="a"
                    radius={i === keys.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
                    fill={chartTheme.series[i % chartTheme.series.length]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ModernReportCard>
      ) : null}

      {yearlyTeamAverages.length > 0 && !teamStats ? (
        <ModernReportCard eyebrow="Team rollup" title="Yearly Team Averages">
          <div className="overflow-x-auto">
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="border-b border-outline-variant/20 text-on-surface-variant">
                  <th className="px-3 py-2 text-left font-medium">Team</th>
                  <th className="px-3 py-2 text-right font-medium">Year</th>
                  {yearlyTeamAverageColumns.map((column) => (
                    <th key={column} className="px-3 py-2 text-right font-medium">
                      {humanizeColumn(column)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {yearlyTeamAverages.map((row, idx) => (
                  <tr key={`${String(row.team)}-${String(row.year)}-${idx}`} className="border-b border-outline-variant/10">
                    <td className="px-3 py-2 font-medium text-on-surface">{formatCell(row.team, "team", jiraBaseUrl)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatCell(row.year, "year", jiraBaseUrl)}</td>
                    {yearlyTeamAverageColumns.map((column) => (
                      <td key={column} className="px-3 py-2 text-right tabular-nums text-on-surface">
                        {formatCell(row[column], column, jiraBaseUrl)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ModernReportCard>
      ) : null}

      {sortedHeatmapRows && sortedHeatmapRows.length > 0 ? (
        <ModernReportCard eyebrow="Allocation detail" title="Person and topic heatmap">
          <div className="max-h-[32rem] overflow-auto rounded-2xl elevated-panel">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-surface-container-low">
                <tr className="border-b border-outline-variant/20">
                  <HeatmapHeader
                    label="Person"
                    sortKey="person"
                    activeSort={heatmapSort}
                    onSort={(key) => setHeatmapSort(nextSortState(heatmapSort, key))}
                  />
                  <HeatmapHeader
                    label="Topic"
                    sortKey="topic"
                    activeSort={heatmapSort}
                    onSort={(key) => setHeatmapSort(nextSortState(heatmapSort, key))}
                  />
                  <HeatmapHeader
                    label="Hours"
                    sortKey="hours"
                    numeric
                    activeSort={heatmapSort}
                    onSort={(key) => setHeatmapSort(nextSortState(heatmapSort, key))}
                  />
                </tr>
              </thead>
              <tbody>
                {sortedHeatmapRows.map((row, idx) => (
                  <tr key={idx} className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5">
                    <td className="px-3 py-2">{row.person}</td>
                    <td className="px-3 py-2">{row.topic}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.hours.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ModernReportCard>
      ) : null}

      {data.table && data.table.length > 0 ? (
        <ModernReportCard
          eyebrow={detailsEyebrow}
          title={detailsTitle}
          description={detailsDescription}
        >
          {rowVisibilityToggle && hiddenRowCount > 0 ? (
            <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
              <button
                type="button"
                onClick={() => setShowHiddenRows((current) => !current)}
                className="rounded-lg border border-outline-variant/30 px-3 py-2 font-medium text-on-surface hover:bg-surface-container-low"
              >
                {showHiddenRows ? rowVisibilityToggle.hideLabel : rowVisibilityToggle.showLabel}
              </button>
              <span className="text-xs text-on-surface-variant">
                {hiddenRowCount} {rowVisibilityToggle.hiddenRowsLabel}
                {showHiddenRows ? " shown" : " hidden by default"}
              </span>
            </div>
          ) : null}
          <div className="max-h-[32rem] overflow-auto rounded-2xl elevated-panel">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-surface-container-low">
                <tr className="border-b border-outline-variant/20">
                  {columns.map((col) => {
                    const activeSort = sort?.column === col ? sort.direction : null;
                    return (
                    <th
                      key={col}
                      className={`px-3 py-2 font-medium text-on-surface-variant ${
                        isNumericColumn(col) ? "text-right" : "text-left"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setSort(nextSort(sort, col))}
                        className={`inline-flex items-center gap-1 hover:text-on-surface ${
                          isNumericColumn(col) ? "justify-end" : "justify-start"
                        }`}
                      >
                        <span>{humanizeColumn(col)}</span>
                        <span className="text-[10px]">{activeSort === "asc" ? "▲" : activeSort === "desc" ? "▼" : "↕"}</span>
                      </button>
                    </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {sortedTable.map((row, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5"
                  >
                    {columns.map((col) => (
                      <td
                        key={col}
                        title={col === "summary" && row[col] != null ? String(row[col]) : undefined}
                        className={`px-3 py-2 text-on-surface ${
                          isNumericColumn(col) ? "text-right tabular-nums" : ""
                        } ${col === "summary" ? "max-w-md truncate" : ""}`}
                      >
                        {formatCell(row[col], col, jiraBaseUrl)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {sortedTable.length >= 100 ? (
              <p className="px-3 py-2 text-xs text-on-surface-variant border-t border-outline-variant/10">
                Showing {sortedTable.length} rows (scroll for more).
              </p>
            ) : null}
          </div>
        </ModernReportCard>
      ) : null}
    </div>
  );
}

function HeatmapHeader({
  label,
  sortKey,
  numeric = false,
  activeSort,
  onSort,
}: {
  label: string;
  sortKey: HeatmapSortKey;
  numeric?: boolean;
  activeSort: SortState<HeatmapSortKey> | null;
  onSort: (key: HeatmapSortKey) => void;
}) {
  const direction = activeSort?.key === sortKey ? activeSort.direction : null;
  return (
    <th className={`px-3 py-2 font-medium text-on-surface-variant ${numeric ? "text-right" : "text-left"}`}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 hover:text-on-surface ${numeric ? "justify-end" : "justify-start"}`}
      >
        <span>{label}</span>
        <span className="text-[10px]">{direction === "asc" ? "▲" : direction === "desc" ? "▼" : "↕"}</span>
      </button>
    </th>
  );
}

const NUMERIC_SUFFIXES = ["_hours", "_days", "_score", "_ratio", "_share", "hours", "count", "rank"];

function isNumericColumn(col: string): boolean {
  if (col === "rank" || col === "delay_days" || col.endsWith("_hours")) return true;
  return NUMERIC_SUFFIXES.some((s) => col.includes(s) && col !== "feature_name");
}

function isHourColumn(col: string): boolean {
  return col === "hours" || col === "total_hours" || col.endsWith("_hours");
}

function humanizeColumn(col: string): string {
  return col.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function yearlyTeamAverageRows(data: AnalyticsReportResponse): Record<string, unknown>[] {
  const value = data.filters?.yearly_team_averages;
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function reportColumns(rows: Record<string, unknown>[], leadingColumns: string[]): string[] {
  const omitted = new Set(leadingColumns);
  const columns = new Set<string>();
  for (const row of rows) {
    for (const [key, value] of Object.entries(row)) {
      if (!omitted.has(key) && value !== undefined) columns.add(key);
    }
  }
  return [...columns].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function nextSort(
  current: { column: string; direction: SortDirection } | null,
  column: string,
): { column: string; direction: SortDirection } {
  if (current?.column !== column) return { column, direction: "asc" };
  return { column, direction: current.direction === "asc" ? "desc" : "asc" };
}

function compareValues(a: unknown, b: unknown, direction: SortDirection): number {
  const modifier = direction === "asc" ? 1 : -1;
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * modifier;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" }) * modifier;
}

function formatChartValue(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : String(value);
}

function formatSummaryValue(key: string, value: unknown): string {
  if (key === "reliability" && typeof value === "number") {
    return formatNumberMax2(value);
  }
  return String(value);
}

function formatCell(value: unknown, column: string, jiraBaseUrl: string): ReactNode {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  const text = String(value);
  if (jiraBaseUrl && ISSUE_KEY_COLUMNS.has(column) && /^[A-Z][A-Z0-9]+-\d+$/.test(text)) {
    return (
      <JiraIssueLink
        issueKey={text}
        issueUrl={jiraBrowseUrl(jiraBaseUrl, text)}
        jiraBaseUrl={jiraBaseUrl}
      />
    );
  }
  if (typeof value === "number" && (column.endsWith("_ratio") || column === "interruption_ratio")) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (typeof value === "number" && column === "reliability") {
    return formatNumberMax2(value);
  }
  if (typeof value === "number" && column.endsWith("_share")) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (typeof value === "number" && isHourColumn(column)) {
    return value.toFixed(2);
  }
  return text;
}

function formatNumberMax2(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}
