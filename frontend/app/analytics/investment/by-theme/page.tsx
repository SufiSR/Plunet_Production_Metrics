"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { AnalyticsFilterPanel, SegmentToggle } from "@/app/components/jira-analytics/AnalyticsReportControls";
import { InvestmentMetricCard, InvestmentReportLayout } from "@/app/components/jira-analytics/InvestmentReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { EmptyCardMessage, ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { useReportChartTheme } from "@/lib/chart-colors";
import { comparePeriodValuesDesc } from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

type BreakdownMode = "monthly" | "yearly";

export default function Page() {
  const [mode, setMode] = useState<BreakdownMode>("monthly");
  const [data, setData] = useState<AnalyticsReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAnalyticsReport(reportPaths.investmentByTheme);
      setData(result);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Failed to load investment by Product");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const yearlySeries = useMemo(() => yearlyRows(data), [data]);
  const breakdownRows = useMemo(
    () =>
      [...(mode === "monthly" ? data?.series ?? [] : yearlySeries)].sort((a, b) =>
        comparePeriodValuesDesc(a[mode === "monthly" ? "period" : "year"], b[mode === "monthly" ? "period" : "year"]),
      ),
    [data?.series, mode, yearlySeries],
  );
  const periodKey = mode === "monthly" ? "period" : "year";
  const breakdownColumns = useMemo(
    () => productColumns(breakdownRows, periodKey),
    [breakdownRows, periodKey],
  );
  const chartColumns = useMemo(
    () => topProductColumns(breakdownRows, periodKey, 8),
    [breakdownRows, periodKey],
  );
  const empty = Boolean(!loading && !error && data && !data.table.length && !breakdownRows.length);

  return (
    <JiraAnalyticsShell
      title="Investment by Product"
      description="Portfolio effort grouped by PMGT Product values."
      hidePageHeader
      hideMethodology
    >
      <InvestmentReportLayout
        activeReport="by-theme"
        title="Read investment through the Product lens."
        description="A PMGT Product view that explains which roadmap ownership areas are absorbing portfolio capacity and how that mix changes over time."
        metrics={<ProductMetrics data={data} rows={data?.table ?? []} />}
        controls={
          <AnalyticsFilterPanel title="View controls" description="Switch between monthly detail and yearly rollups.">
            <SegmentToggle
              value={mode}
              options={[
                { value: "monthly", label: "Monthly" },
                { value: "yearly", label: "Yearly" },
              ]}
              onChange={setMode}
            />
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          error={error}
          empty={empty}
          emptyMessage="No allocated Product investment data yet."
        >
          {data ? (
            <div className="space-y-6">
              <ModernReportCard
                eyebrow="Product mix"
                title={`${mode === "monthly" ? "Monthly" : "Yearly"} Product investment`}
                description="Stacked hours by PMGT Product. The chart shows the largest products and keeps the full data in the table below."
              >
                <ProductInvestmentChart rows={breakdownRows} periodKey={periodKey} columns={chartColumns} />
              </ModernReportCard>

              <ModernReportCard
                eyebrow="Totals"
                title="Total by Product"
                description="A ranked table of Product values by allocated hours."
              >
                <SimpleTable rows={data.table} periodKey="theme" columns={["hours"]} />
              </ModernReportCard>

              <ModernReportCard
                eyebrow="Breakdown"
                title={`${mode === "monthly" ? "Monthly" : "Yearly"} Product allocation table`}
                description="Detailed allocation matrix for comparing Product investment across periods."
              >
                <SimpleTable rows={breakdownRows} periodKey={periodKey} columns={breakdownColumns} />
              </ModernReportCard>
            </div>
          ) : null}
        </ReportPageFrame>
      </InvestmentReportLayout>
    </JiraAnalyticsShell>
  );
}

function SimpleTable({
  rows,
  periodKey,
  columns,
}: {
  rows: Record<string, unknown>[];
  periodKey: string;
  columns: string[];
}) {
  if (rows.length === 0) {
    return <EmptyCardMessage>No data available.</EmptyCardMessage>;
  }

  return (
    <div className="max-h-[32rem] overflow-auto rounded-2xl elevated-panel">
      <table className="w-full min-w-max text-sm">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant/20 text-on-surface-variant">
            <th className="px-3 py-2 text-left font-medium">{humanize(periodKey)}</th>
            {columns.map((column) => (
              <th key={column} className="px-3 py-2 text-right font-medium">
                {humanize(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row[periodKey])} className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5">
              <td className="px-3 py-2 font-medium text-on-surface">
                {formatPeriodValue(row[periodKey])}
              </td>
              {columns.map((column) => (
                <td key={column} className="px-3 py-2 text-right tabular-nums text-on-surface">
                  {formatNumber(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProductInvestmentChart({
  rows,
  periodKey,
  columns,
}: {
  rows: Record<string, unknown>[];
  periodKey: string;
  columns: string[];
}) {
  const chartTheme = useReportChartTheme();

  if (rows.length === 0 || columns.length === 0) {
    return <EmptyCardMessage>No chart data available for this Product view.</EmptyCardMessage>;
  }

  const chartRows = [...rows]
    .sort((a, b) => comparePeriodValuesDesc(a[periodKey], b[periodKey]))
    .map((row) => ({
      ...row,
      _label: formatPeriodValue(row[periodKey]),
    }));

  return (
    <div className="analytics-chart-plot h-[360px] w-full p-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartRows} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid {...chartTheme.gridProps} vertical={false} />
          <XAxis
            dataKey="_label"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
          />
          <YAxis tick={chartTheme.axisTick} axisLine={chartTheme.axisLine} tickLine={chartTheme.tickLine} />
          <Tooltip
            formatter={(value, name) => [formatChartNumber(value), humanize(String(name))]}
            contentStyle={{
              background: chartTheme.colors.tooltipBg,
              color: chartTheme.colors.tooltipText,
              border: "none",
              borderRadius: "0.5rem",
            }}
          />
          <Legend formatter={(value) => humanize(String(value))} />
          {columns.map((column, index) => (
            <Bar
              key={column}
              dataKey={column}
              stackId="product"
              radius={index === columns.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
              fill={chartTheme.series[index % chartTheme.series.length]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProductMetrics({
  data,
  rows,
}: {
  data: AnalyticsReportResponse | null;
  rows: Record<string, unknown>[];
}) {
  const totalHours = rows.reduce((sum, row) => sum + numberValue(row.hours), 0);
  const topProduct = [...rows].sort((a, b) => numberValue(b.hours) - numberValue(a.hours))[0];
  const periods = new Set((data?.series ?? []).map((row) => String(row.period ?? "")).filter(Boolean)).size;

  return (
    <>
      <InvestmentMetricCard label="Products" value={rows.length ? String(rows.length) : "Loading"} detail="PMGT Product values" />
      <InvestmentMetricCard label="Allocated hours" value={formatCompactHours(totalHours)} detail="Total Product allocation" />
      <InvestmentMetricCard label="Top Product" value={String(topProduct?.theme ?? "Loading")} detail={periods ? `${periods} monthly periods` : "Largest allocation"} />
    </>
  );
}

function yearlyRows(data: AnalyticsReportResponse | null): Record<string, unknown>[] {
  const value = data?.filters?.yearly_series;
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function productColumns(rows: Record<string, unknown>[], periodKey: string): string[] {
  const keys = new Set<string>();
  for (const row of rows) {
    for (const [key, value] of Object.entries(row)) {
      if (key !== periodKey && typeof value === "number") keys.add(key);
    }
  }
  return [...keys].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

function topProductColumns(rows: Record<string, unknown>[], periodKey: string, limit: number): string[] {
  const totals = new Map<string, number>();
  for (const row of rows) {
    for (const [key, value] of Object.entries(row)) {
      if (key !== periodKey && typeof value === "number" && value > 0) {
        totals.set(key, (totals.get(key) ?? 0) + value);
      }
    }
  }
  return [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([key]) => key);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatNumber(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value.toFixed(2) : "—";
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatChartNumber(value: unknown): string {
  return typeof value === "number" ? `${value.toFixed(1)} h` : String(value);
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}

function formatPeriodValue(value: unknown): string {
  if (typeof value !== "string") return String(value ?? "—");
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month] = value.split("-");
    return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString(undefined, {
      month: "short",
      year: "numeric",
    });
  }
  return value;
}
