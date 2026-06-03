"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { AnalyticsFilterPanel, FilterField, filterInputClassName } from "@/app/components/jira-analytics/AnalyticsReportControls";
import { InvestmentMetricCard, InvestmentReportLayout } from "@/app/components/jira-analytics/InvestmentReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { useReportChartTheme } from "@/lib/chart-colors";
import {
  comparePeriodValuesDesc,
  compareSortableValues,
  nextSortState,
  type SortState,
} from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

interface RankingRow {
  feature: string;
  feature_key: string;
  status: "planned" | "running" | "done";
  direct_dev: number;
  direct_qa: number;
  direct_ux: number;
  product_overhead: number;
  dev_overhead: number;
  total: number;
  rank: number;
}

interface MonthlyRow {
  feature: string;
  feature_key: string;
  period: string;
  direct_dev: number;
  direct_qa: number;
  direct_ux: number;
  product_overhead: number;
  dev_overhead: number;
  total: number;
}

const METRIC_COLUMNS = [
  { key: "direct_dev", label: "Direct Dev" },
  { key: "direct_qa", label: "Direct QA" },
  { key: "direct_ux", label: "Direct UX" },
  { key: "product_overhead", label: "Product Overhead" },
  { key: "dev_overhead", label: "Dev Overhead" },
] as const;

type RankingSortKey = keyof RankingRow;

export default function Page() {
  const chartTheme = useReportChartTheme();
  const [data, setData] = useState<AnalyticsReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedFeatureKey, setSelectedFeatureKey] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState<RankingSortKey> | null>({ key: "rank", direction: "asc" });
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RankingRow["status"]>("all");
  const chartRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAnalyticsReport(reportPaths.investmentRanking);
      setData(result);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    return (data?.table ?? []).map(toRankingRow).filter((row): row is RankingRow => row !== null);
  }, [data]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesStatus = statusFilter === "all" || row.status === statusFilter;
      const matchesQuery =
        normalizedQuery.length === 0 ||
        row.feature.toLowerCase().includes(normalizedQuery) ||
        row.feature_key.toLowerCase().includes(normalizedQuery);
      return matchesStatus && matchesQuery;
    });
  }, [query, rows, statusFilter]);

  const sortedRows = useMemo(() => {
    if (!sort) return filteredRows;
    return [...filteredRows].sort((a, b) => compareSortableValues(a[sort.key], b[sort.key], sort.direction));
  }, [filteredRows, sort]);

  const monthlyRows = useMemo(() => {
    return (data?.series ?? []).map(toMonthlyRow).filter((row): row is MonthlyRow => row !== null);
  }, [data]);

  const selectedFeature = useMemo(
    () => rows.find((row) => row.feature_key === selectedFeatureKey) ?? null,
    [rows, selectedFeatureKey],
  );

  const selectedChartData = useMemo(() => {
    if (!selectedFeatureKey) return [];
    return monthlyRows
      .filter((row) => row.feature_key === selectedFeatureKey)
      .sort((a, b) => comparePeriodValuesDesc(a.period, b.period))
      .map((row) => ({
        ...row,
        periodLabel: formatPeriod(row.period),
      }));
  }, [monthlyRows, selectedFeatureKey]);

  const selectFeature = (featureKey: string) => {
    setSelectedFeatureKey(featureKey);
    window.setTimeout(() => {
      chartRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      chartRef.current?.focus({ preventScroll: true });
    }, 0);
  };

  const empty = Boolean(!loading && !error && data && rows.length === 0);

  return (
    <JiraAnalyticsShell
      title="Feature investment ranking"
      description="Features ranked by total allocated effort across direct delivery work and role-based overhead."
      hidePageHeader
      hideMethodology
    >
      <InvestmentReportLayout
        activeReport="ranking"
        title="Find the features carrying the most investment."
        description="A ranked portfolio view for moving from aggregate capacity conversations into concrete feature-level follow-up."
        metrics={<RankingMetrics rows={rows} visibleRows={sortedRows.length} />}
        controls={
          <AnalyticsFilterPanel title="Filters" description="Search and narrow the ranked feature list before opening the monthly profile.">
            <FilterField label="Search feature" className="min-w-[18rem]">
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Feature name or key"
                className={filterInputClassName("min-w-[18rem]")}
              />
            </FilterField>
            <FilterField label="Status">
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as "all" | RankingRow["status"])}
                className={filterInputClassName()}
              >
                <option value="all">All statuses</option>
                <option value="planned">Planned</option>
                <option value="running">Running</option>
                <option value="done">Done</option>
              </select>
            </FilterField>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          error={error}
          empty={empty}
          emptyMessage="No allocation data yet. Run a Jira analytics sync (or POST /api/jira-analytics/allocation/rebuild) after worklogs and HR hours are loaded."
        >
          <div className="space-y-6">
            <ModernReportCard
              eyebrow="Ranked features"
              title="Investment leaderboard"
              description="Click a feature name to reveal its monthly allocation profile below."
            >
              <div className="max-h-[32rem] overflow-auto rounded-2xl elevated-panel">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 z-10 bg-surface-container-low">
                    <tr className="border-b border-outline-variant/20">
                      <SortableHeader
                        label="Feature"
                        sortKey="feature"
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                      <SortableHeader
                        label="Feature Key"
                        sortKey="feature_key"
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                      <SortableHeader
                        label="Status"
                        sortKey="status"
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                      {METRIC_COLUMNS.map((column) => (
                        <SortableHeader
                          key={column.key}
                          label={column.label}
                          sortKey={column.key}
                          numeric
                          activeSort={sort}
                          onSort={(key) => setSort(nextSortState(sort, key))}
                        />
                      ))}
                    <SortableHeader
                      label="Total"
                      sortKey="total"
                      numeric
                      activeSort={sort}
                      onSort={(key) => setSort(nextSortState(sort, key))}
                    />
                      <SortableHeader
                        label="Rank"
                        sortKey="rank"
                        numeric
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRows.map((row) => (
                      <tr
                        key={row.feature_key}
                        className={`border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5 ${
                          row.feature_key === selectedFeatureKey ? "bg-primary/10" : ""
                        }`}
                      >
                        <td className="px-3 py-2 text-on-surface">
                          <button
                            type="button"
                            onClick={() => selectFeature(row.feature_key)}
                            className="rounded text-left font-semibold text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          >
                            {row.feature}
                          </button>
                        </td>
                        <td className="px-3 py-2 text-on-surface">{row.feature_key}</td>
                        <td className="px-3 py-2 text-on-surface capitalize">{row.status}</td>
                        {METRIC_COLUMNS.map((column) => (
                          <td key={column.key} className="px-3 py-2 text-right tabular-nums text-on-surface">
                            {formatHours(row[column.key])}
                          </td>
                        ))}
                        <td className="px-3 py-2 text-right tabular-nums font-semibold text-on-surface">
                          {formatHours(row.total)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.rank}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ModernReportCard>

            <ModernReportCard
              eyebrow="Monthly profile"
              title="Feature investment over time"
              description={
                selectedFeature
                  ? `${selectedFeature.feature} (${selectedFeature.feature_key})`
                  : "Select a feature name above to show the monthly breakdown."
              }
            >
              <div
                ref={chartRef}
                tabIndex={-1}
                className="focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {selectedFeature ? (
                  selectedChartData.length > 0 ? (
                    <div className="analytics-chart-plot h-[360px] w-full p-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={selectedChartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                          <CartesianGrid {...chartTheme.gridProps} vertical={false} />
                          <XAxis
                            dataKey="periodLabel"
                            tick={chartTheme.axisTick}
                            axisLine={chartTheme.axisLine}
                            tickLine={chartTheme.tickLine}
                          />
                          <YAxis tick={chartTheme.axisTick} axisLine={chartTheme.axisLine} tickLine={chartTheme.tickLine} />
                          <Tooltip
                            formatter={(value, name) => [
                              `${Number(value ?? 0).toFixed(1)} h`,
                              chartLabel(String(name)),
                            ]}
                            contentStyle={{
                              background: chartTheme.colors.tooltipBg,
                              color: chartTheme.colors.tooltipText,
                              border: "none",
                              borderRadius: "0.5rem",
                            }}
                          />
                          <Legend formatter={(value) => chartLabel(String(value))} />
                          {METRIC_COLUMNS.map((column, index) => (
                            <Bar
                              key={column.key}
                              dataKey={column.key}
                              stackId="hours"
                              radius={index === METRIC_COLUMNS.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
                              fill={chartTheme.series[index % chartTheme.series.length]}
                            />
                          ))}
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="text-sm text-on-surface-variant">No monthly data for this feature.</p>
                  )
                ) : (
                  <p className="rounded-2xl border border-dashed border-outline-variant/30 bg-surface-container-low p-6 text-sm text-on-surface-variant">
                    Select a feature in the leaderboard to inspect how direct and overhead effort accumulated month by month.
                  </p>
                )}
              </div>
            </ModernReportCard>
          </div>
        </ReportPageFrame>
      </InvestmentReportLayout>
    </JiraAnalyticsShell>
  );
}

function RankingMetrics({ rows, visibleRows }: { rows: RankingRow[]; visibleRows: number }) {
  const totalHours = rows.reduce((sum, row) => sum + row.total, 0);
  const topFeature = [...rows].sort((a, b) => b.total - a.total)[0];

  return (
    <>
      <InvestmentMetricCard label="Features" value={rows.length ? String(rows.length) : "Loading"} detail={`${visibleRows} visible after filters`} />
      <InvestmentMetricCard label="Allocated hours" value={formatCompactHours(totalHours)} detail="Total ranked effort" />
      <InvestmentMetricCard label="Top feature" value={topFeature?.feature_key ?? "Loading"} detail={topFeature ? `${formatHours(topFeature.total)} h` : "Highest total"} />
    </>
  );
}

function SortableHeader({
  label,
  sortKey,
  numeric = false,
  activeSort,
  onSort,
}: {
  label: string;
  sortKey: RankingSortKey;
  numeric?: boolean;
  activeSort: SortState<RankingSortKey> | null;
  onSort: (key: RankingSortKey) => void;
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

function toRankingRow(row: Record<string, unknown>): RankingRow | null {
  const feature = stringValue(row.feature);
  const featureKey = stringValue(row.feature_key);
  if (!feature || !featureKey) return null;
  return {
    feature,
    feature_key: featureKey,
    status: statusValue(row.status),
    direct_dev: numberValue(row.direct_dev),
    direct_qa: numberValue(row.direct_qa),
    direct_ux: numberValue(row.direct_ux),
    product_overhead: numberValue(row.product_overhead),
    dev_overhead: numberValue(row.dev_overhead),
    total: numberValue(row.total),
    rank: numberValue(row.rank),
  };
}

function toMonthlyRow(row: Record<string, unknown>): MonthlyRow | null {
  const feature = stringValue(row.feature);
  const featureKey = stringValue(row.feature_key);
  const period = stringValue(row.period);
  if (!feature || !featureKey || !period) return null;
  return {
    feature,
    feature_key: featureKey,
    period,
    direct_dev: numberValue(row.direct_dev),
    direct_qa: numberValue(row.direct_qa),
    direct_ux: numberValue(row.direct_ux),
    product_overhead: numberValue(row.product_overhead),
    dev_overhead: numberValue(row.dev_overhead),
    total: numberValue(row.total),
  };
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function statusValue(value: unknown): RankingRow["status"] {
  return value === "running" || value === "done" ? value : "planned";
}

function formatHours(value: number): string {
  return value.toFixed(1);
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}

function chartLabel(key: string): string {
  return METRIC_COLUMNS.find((column) => column.key === key)?.label ?? key;
}

function formatPeriod(period: string): string {
  const [year, month] = period.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}
