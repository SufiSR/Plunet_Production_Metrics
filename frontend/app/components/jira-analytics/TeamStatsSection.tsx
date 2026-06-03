"use client";

import { useMemo, useState, type ReactNode } from "react";
import { YearlyTeamTrendChart } from "@/app/components/jira-analytics/YearlyTeamTrendChart";

type TeamStatsView = "chart" | "table";

export interface TeamStatsConfig {
  metricKey: string;
  yAxisLabel: string;
  formatChartValue?: (value: number) => string;
  yDomain?: [number | "auto", number | "auto"];
  showSummaryYearNote?: boolean;
}

interface TeamStatsSectionProps {
  rows: Record<string, unknown>[];
  config: TeamStatsConfig;
  formatCell: (value: unknown, column: string) => ReactNode;
  humanizeColumn: (column: string) => string;
}

export function TeamStatsSection({
  rows,
  config,
  formatCell,
  humanizeColumn,
}: TeamStatsSectionProps) {
  const { metricKey, yAxisLabel, formatChartValue, yDomain } = config;
  const [view, setView] = useState<TeamStatsView>("chart");
  const metricColumns = useMemo(() => reportColumns(rows, ["team", "year"]), [rows]);
  const hasChart = rows.some((row) => typeof row[metricKey] === "number");
  const tableRows = useMemo(
    () =>
      [...rows].sort(
        (a, b) =>
          compareYearDesc(a.year, b.year) ||
          String(a.team ?? "").localeCompare(String(b.team ?? ""), undefined, { sensitivity: "base" }),
      ),
    [rows],
  );

  if (!rows.length) {
    return null;
  }

  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-editorial font-semibold text-on-surface">Team Stats</h2>
        <div
          className="inline-flex rounded-lg border border-outline-variant/30 p-0.5 text-xs"
          role="tablist"
          aria-label="Team stats view"
        >
          <TabButton active={view === "chart"} onClick={() => setView("chart")} disabled={!hasChart}>
            Chart
          </TabButton>
          <TabButton active={view === "table"} onClick={() => setView("table")}>
            Table
          </TabButton>
        </div>
      </div>

      {view === "chart" && hasChart ? (
        <YearlyTeamTrendChart
          rows={rows}
          metricKey={metricKey}
          yAxisLabel={yAxisLabel}
          formatValue={formatChartValue}
          yDomain={yDomain}
        />
      ) : null}

      {view === "table" ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="border-b border-outline-variant/20 text-on-surface-variant">
                <th className="px-3 py-2 text-left font-medium">Team</th>
                <th className="px-3 py-2 text-right font-medium">Year</th>
                {metricColumns.map((column) => (
                  <th key={column} className="px-3 py-2 text-right font-medium">
                    {humanizeColumn(column)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row, idx) => (
                <tr
                  key={`${String(row.team)}-${String(row.year)}-${idx}`}
                  className="border-b border-outline-variant/10"
                >
                  <td className="px-3 py-2 font-medium text-on-surface">{formatCell(row.team, "team")}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">
                    {formatCell(row.year, "year")}
                  </td>
                  {metricColumns.map((column) => (
                    <td key={column} className="px-3 py-2 text-right tabular-nums text-on-surface">
                      {formatCell(row[column], column)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {view === "chart" && !hasChart ? (
        <p className="text-sm text-on-surface-variant">No chart data for the selected filters.</p>
      ) : null}
    </section>
  );
}

function TabButton({
  active,
  onClick,
  disabled = false,
  children,
}: {
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
        active
          ? "bg-primary text-on-primary"
          : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      {children}
    </button>
  );
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

function compareYearDesc(a: unknown, b: unknown): number {
  const aYear = typeof a === "number" ? a : Number(a);
  const bYear = typeof b === "number" ? b : Number(b);
  if (Number.isFinite(aYear) && Number.isFinite(bYear)) return bYear - aYear;
  return String(b ?? "").localeCompare(String(a ?? ""), undefined, { numeric: true, sensitivity: "base" });
}
