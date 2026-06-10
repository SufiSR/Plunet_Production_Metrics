"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
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
  SegmentToggle,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import {
  CustomerMetricCard,
  CustomerReportLayout,
} from "@/app/components/jira-analytics/CustomerReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { JiraIssueLink, jiraBrowseUrl } from "@/app/components/jira-analytics/JiraIssueLink";
import { useJiraBaseUrl } from "@/app/components/jira-analytics/JiraAnalyticsContext";
import { EmptyCardMessage, ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { PeopleDataGate } from "@/app/components/jira-analytics/PeopleDataGate";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { useReportChartTheme } from "@/lib/chart-colors";
import { lastTwelveMonths } from "@/lib/jira-analytics-dates";
import {
  comparePeriodValuesAsc,
  compareSortableValues,
  nextSortState,
  type SortState,
} from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

type BreakdownMode = "monthly" | "yearly";
type SortKey =
  | "customer"
  | "feature_hours"
  | "bugfix_hours"
  | "support_hours"
  | "improvement_hours"
  | "other_hours"
  | "total_hours";

const TOPIC_COLUMNS: SortKey[] = [
  "feature_hours",
  "bugfix_hours",
  "support_hours",
  "improvement_hours",
  "other_hours",
  "total_hours",
];

interface CustomerIssueDrilldownRow {
  issue_key: string;
  issue_summary: string | null;
  topic_type: string | null;
  total_hours: number;
  people: Array<{ person: string; hours: number }>;
}

export default function Page() {
  const jiraBaseUrl = useJiraBaseUrl();
  const defaultRange = useMemo(() => lastTwelveMonths(), []);
  const [params, setParams] = useState<ReportQueryParams>(defaultRange);
  const [mode, setMode] = useState<BreakdownMode>("monthly");
  const [sort, setSort] = useState<SortState<SortKey> | null>({ key: "total_hours", direction: "desc" });
  const [selectedDrilldownCustomer, setSelectedDrilldownCustomer] = useState<string | null>(null);
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [params],
    load: (signal) => fetchAnalyticsReport(reportPaths.customerEffort, params, signal),
  });

  const customers = useMemo(() => stringList(data?.filters?.available_customers), [data?.filters?.available_customers]);
  const yearlySeries = useMemo(() => recordList(data?.filters?.yearly_series), [data?.filters?.yearly_series]);
  const issueDrilldowns = useMemo(
    () => customerIssueDrilldowns(data?.filters?.issue_drilldowns),
    [data?.filters?.issue_drilldowns],
  );
  const restricted = data?.summary?.people_data_restricted === true;
  const breakdownRows = useMemo(
    () => (mode === "monthly" ? data?.series ?? [] : yearlySeries),
    [data?.series, mode, yearlySeries],
  );
  const periodKey = mode === "monthly" ? "period" : "year";
  const chartCustomers = useMemo(() => topCustomers(data?.table ?? [], 8), [data?.table]);
  const trendCustomers = useMemo(() => topCustomers(data?.table ?? [], 5), [data?.table]);
  const sortedRows = useMemo(() => {
    const rows = [...(data?.table ?? [])];
    if (!sort) {
      return rows.sort((a, b) => compareSortableValues(b.total_hours, a.total_hours, "desc"));
    }
    return rows.sort((a, b) => compareSortableValues(a[sort.key], b[sort.key], sort.direction));
  }, [data?.table, sort]);
  const activeDrilldownCustomer =
    selectedDrilldownCustomer && issueDrilldowns[selectedDrilldownCustomer]
      ? selectedDrilldownCustomer
      : params.customer && issueDrilldowns[params.customer]
        ? params.customer
        : null;
  const empty = Boolean(!loading && !refreshing && !error && data && !data.table.length && !breakdownRows.length);

  return (
    <JiraAnalyticsShell
      title="Customer effort"
      description="Engineering capacity attributed to Jira customer field values."
      hidePageHeader
      hideMethodology
    >
      <CustomerReportLayout
        title="See which customers consume disproportionate engineering capacity."
        description="Allocated hours from monthly work allocation, attributed through Jira customfield_10123 on linked issues. Multi-customer issues split hours equally."
        metrics={<CustomerMetrics data={data} rows={data?.table ?? []} />}
        controls={
          <AnalyticsFilterPanel
            title="Period and customer"
            description="Default view uses the last twelve months to keep the report responsive."
          >
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
            <FilterField label="Customer" className="min-w-[14rem]">
              <select
                value={params.customer ?? ""}
                onChange={(event) =>
                  setParams((prev) => ({ ...prev, customer: event.target.value || undefined }))
                }
                className={filterInputClassName()}
              >
                <option value="">All customers</option>
                {customers.map((customer) => (
                  <option key={customer} value={customer}>
                    {customer}
                  </option>
                ))}
              </select>
            </FilterField>
            <SegmentToggle
              value={mode}
              options={[
                { value: "monthly", label: "Monthly trend" },
                { value: "yearly", label: "Yearly trend" },
              ]}
              onChange={setMode}
            />
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage="No customer-attributed allocation data for the selected period."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
          {data ? (
            <div className="space-y-6">
              {numberValue(data.filters?.unattributed_hours) > 0 ? (
                <div className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-3 text-xs text-on-surface-variant">
                  <p>
                    {formatCompactHours(numberValue(data.filters?.unattributed_hours))} in the selected period have no
                    customer field and are excluded from the ranking below. Multi-customer issues use equal split
                    attribution.
                  </p>
                </div>
              ) : null}

              <ModernReportCard
                eyebrow="Ranking"
                title="Top customers by attributed hours"
                description="Pareto-style view of the largest customer demand in the selected period."
              >
                <CustomerRankingChart rows={data.table ?? []} customers={chartCustomers} />
              </ModernReportCard>

              <ModernReportCard
                eyebrow="Trend"
                title={`${mode === "monthly" ? "Monthly" : "Yearly"} customer effort`}
                description="Track whether demand from the largest customers is rising or easing over time."
              >
                <CustomerTrendChart rows={breakdownRows} periodKey={periodKey} customers={trendCustomers} />
              </ModernReportCard>

              <ModernReportCard
                eyebrow="Breakdown"
                title="Customer effort by topic"
                description="Feature, bugfix, support, and improvement hours per customer."
              >
                <CustomerTopicTable
                  rows={sortedRows}
                  sort={sort}
                  setSort={setSort}
                  onSelectCustomer={setSelectedDrilldownCustomer}
                  selectedCustomer={activeDrilldownCustomer}
                />
              </ModernReportCard>

              <ModernReportCard
                eyebrow="Drilldown"
                title="Customer issue and contributor hours"
                description="Issues that contributed to the selected customer total, split by the individuals whose allocated work went into them."
              >
                {restricted ? (
                  <PeopleDataGate restricted />
                ) : (
                  <CustomerIssueDrilldown
                    customer={activeDrilldownCustomer}
                    rows={activeDrilldownCustomer ? issueDrilldowns[activeDrilldownCustomer] ?? [] : []}
                    jiraBaseUrl={jiraBaseUrl}
                  />
                )}
              </ModernReportCard>
            </div>
          ) : null}
        </ReportPageFrame>
      </CustomerReportLayout>
    </JiraAnalyticsShell>
  );
}

function CustomerMetrics({
  data,
  rows,
}: {
  data: AnalyticsReportResponse | null;
  rows: Record<string, unknown>[];
}) {
  const totalHours = rows.reduce((sum, row) => sum + numberValue(row.total_hours), 0);
  const topCustomer = [...rows].sort((a, b) => numberValue(b.total_hours) - numberValue(a.total_hours))[0];
  const unattributed = numberValue(data?.summary?.unattributed_hours ?? data?.filters?.unattributed_hours);

  return (
    <>
      <CustomerMetricCard
        label="Customers"
        value={rows.length ? String(rows.length) : "Loading"}
        detail="With attributed hours"
      />
      <CustomerMetricCard
        label="Attributed hours"
        value={formatCompactHours(totalHours)}
        detail="Equal split across listed customers"
      />
      <CustomerMetricCard
        label="Top customer"
        value={String(topCustomer?.customer ?? "Loading")}
        detail={
          unattributed > 0
            ? `${formatCompactHours(unattributed)} without customer field`
            : "Largest attributed share"
        }
      />
    </>
  );
}

function CustomerRankingChart({
  rows,
  customers,
}: {
  rows: Record<string, unknown>[];
  customers: string[];
}) {
  const chartTheme = useReportChartTheme();

  if (rows.length === 0 || customers.length === 0) {
    return <EmptyCardMessage>No customer ranking data for this period.</EmptyCardMessage>;
  }

  const chartRows = customers.map((customer) => {
    const row = rows.find((entry) => entry.customer === customer);
    return {
      customer,
      total_hours: numberValue(row?.total_hours),
    };
  });

  return (
    <div className="analytics-chart-plot h-[360px] w-full p-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartRows} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid {...chartTheme.gridProps} horizontal={false} />
          <XAxis
            type="number"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
          />
          <YAxis
            type="category"
            dataKey="customer"
            width={160}
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
          />
          <Tooltip
            formatter={(value) => [formatChartNumber(value), "Attributed hours"]}
            contentStyle={{
              background: chartTheme.colors.tooltipBg,
              color: chartTheme.colors.tooltipText,
              border: "none",
              borderRadius: "0.5rem",
            }}
          />
          <Bar dataKey="total_hours" fill={chartTheme.colors.primary} radius={[0, 8, 8, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CustomerTrendChart({
  rows,
  periodKey,
  customers,
}: {
  rows: Record<string, unknown>[];
  periodKey: string;
  customers: string[];
}) {
  const chartTheme = useReportChartTheme();

  if (rows.length === 0 || customers.length === 0) {
    return <EmptyCardMessage>No trend data available for this customer view.</EmptyCardMessage>;
  }

  const chartRows = [...rows]
    .sort((a, b) => comparePeriodValuesAsc(a[periodKey], b[periodKey]))
    .map((row) => ({
      ...row,
      _label: formatPeriodValue(row[periodKey]),
    }));

  return (
    <div className="analytics-chart-plot h-[360px] w-full p-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartRows} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid {...chartTheme.gridProps} vertical={false} />
          <XAxis
            dataKey="_label"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
          />
          <YAxis tick={chartTheme.axisTick} axisLine={chartTheme.axisLine} tickLine={chartTheme.tickLine} />
          <Tooltip
            formatter={(value, name) => [formatChartNumber(value), String(name)]}
            contentStyle={{
              background: chartTheme.colors.tooltipBg,
              color: chartTheme.colors.tooltipText,
              border: "none",
              borderRadius: "0.5rem",
            }}
          />
          <Legend />
          {customers.map((customer, index) => (
            <Line
              key={customer}
              type="monotone"
              dataKey={customer}
              stroke={chartTheme.series[index % chartTheme.series.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function CustomerTopicTable({
  rows,
  sort,
  setSort,
  onSelectCustomer,
  selectedCustomer,
}: {
  rows: Record<string, unknown>[];
  sort: SortState<SortKey> | null;
  setSort: (sort: SortState<SortKey> | null) => void;
  onSelectCustomer: (customer: string) => void;
  selectedCustomer: string | null;
}) {
  if (rows.length === 0) {
    return <EmptyCardMessage>No customer topic breakdown available.</EmptyCardMessage>;
  }

  return (
    <div className="max-h-[32rem] overflow-auto rounded-2xl elevated-panel">
      <table className="w-full min-w-max text-sm">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant/20 text-on-surface-variant">
            <HeaderCell label="Customer" sortKey="customer" sort={sort} setSort={setSort} />
            {TOPIC_COLUMNS.map((column) => (
              <HeaderCell key={column} label={humanize(column)} sortKey={column} sort={sort} setSort={setSort} numeric />
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const customer = String(row.customer ?? "");
            const selected = customer && customer === selectedCustomer;
            return (
              <tr
                key={customer || "unknown"}
                className={`border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5 ${
                  selected ? "bg-primary/10" : ""
                }`}
              >
              <td className="px-3 py-2 font-medium text-on-surface">
                {customer ? (
                  <button
                    type="button"
                    onClick={() => onSelectCustomer(customer)}
                    className="font-medium text-primary underline-offset-2 hover:underline"
                  >
                    {customer}
                  </button>
                ) : (
                  "—"
                )}
              </td>
              {TOPIC_COLUMNS.map((column) => (
                <td key={column} className="px-3 py-2 text-right tabular-nums text-on-surface">
                  {formatNumber(row[column])}
                </td>
              ))}
            </tr>
          );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CustomerIssueDrilldown({
  customer,
  rows,
  jiraBaseUrl,
}: {
  customer: string | null;
  rows: CustomerIssueDrilldownRow[];
  jiraBaseUrl: string;
}) {
  if (!customer) {
    return <EmptyCardMessage>Select a customer in the breakdown table to see issue and contributor hours.</EmptyCardMessage>;
  }
  if (rows.length === 0) {
    return <EmptyCardMessage>No issue drilldown data available for {customer}.</EmptyCardMessage>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-on-surface-variant">
        Showing {rows.length} issue{rows.length === 1 ? "" : "s"} for <span className="font-medium text-on-surface">{customer}</span>.
      </p>
      <div className="max-h-[34rem] overflow-auto rounded-2xl elevated-panel">
        <table className="w-full min-w-[56rem] text-sm">
          <thead className="sticky top-0 z-10 bg-surface-container-low">
            <tr className="border-b border-outline-variant/20 text-on-surface-variant">
              <th className="px-3 py-2 text-left font-medium">Issue</th>
              <th className="px-3 py-2 text-left font-medium">Summary</th>
              <th className="px-3 py-2 text-left font-medium">Topic</th>
              <th className="px-3 py-2 text-right font-medium">Attributed Hours</th>
              <th className="px-3 py-2 text-left font-medium">Individuals</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.issue_key} className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35">
                <td className="px-3 py-2 font-medium text-on-surface">
                  {jiraBaseUrl && /^[A-Z][A-Z0-9]+-\d+$/.test(row.issue_key) ? (
                    <JiraIssueLink
                      issueKey={row.issue_key}
                      issueUrl={jiraBrowseUrl(jiraBaseUrl, row.issue_key)}
                      jiraBaseUrl={jiraBaseUrl}
                    />
                  ) : (
                    row.issue_key
                  )}
                </td>
                <td className="max-w-md px-3 py-2 text-on-surface" title={row.issue_summary ?? undefined}>
                  <span className="line-clamp-2">{row.issue_summary ?? "—"}</span>
                </td>
                <td className="px-3 py-2 text-on-surface">{row.topic_type ? humanize(row.topic_type) : "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatNumber(row.total_hours)}</td>
                <td className="px-3 py-2 text-on-surface">
                  <div className="flex max-w-lg flex-wrap gap-1.5">
                    {row.people.map((person) => (
                      <span
                        key={`${row.issue_key}-${person.person}`}
                        className="rounded-full bg-surface-container px-2 py-1 text-xs text-on-surface-variant"
                      >
                        {person.person}: {formatNumber(person.hours)}h
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HeaderCell({
  label,
  sortKey,
  sort,
  setSort,
  numeric = false,
}: {
  label: string;
  sortKey: SortKey;
  sort: SortState<SortKey> | null;
  setSort: (sort: SortState<SortKey> | null) => void;
  numeric?: boolean;
}) {
  const direction = sort?.key === sortKey ? sort.direction : null;
  return (
    <th className={`px-3 py-2 font-medium ${numeric ? "text-right" : "text-left"}`}>
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

function topCustomers(rows: Record<string, unknown>[], limit: number): string[] {
  return [...rows]
    .sort((a, b) => numberValue(b.total_hours) - numberValue(a.total_hours))
    .slice(0, limit)
    .flatMap((row) => {
      const customer = row.customer;
      return typeof customer === "string" && customer.length > 0 ? [customer] : [];
    });
}

function recordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function customerIssueDrilldowns(value: unknown): Record<string, CustomerIssueDrilldownRow[]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([customer, rows]) => [
      customer,
      Array.isArray(rows) ? rows.flatMap(customerIssueDrilldownRow) : [],
    ]),
  );
}

function customerIssueDrilldownRow(value: unknown): CustomerIssueDrilldownRow[] {
  if (!isRecord(value)) return [];
  const issueKey = typeof value.issue_key === "string" && value.issue_key ? value.issue_key : null;
  if (!issueKey) return [];
  const people = Array.isArray(value.people)
    ? value.people.flatMap((person) => {
        if (!isRecord(person) || typeof person.person !== "string") return [];
        return [{ person: person.person, hours: numberValue(person.hours) }];
      })
    : [];
  return [
    {
      issue_key: issueKey,
      issue_summary: typeof value.issue_summary === "string" ? value.issue_summary : null,
      topic_type: typeof value.topic_type === "string" ? value.topic_type : null,
      total_hours: numberValue(value.total_hours),
      people,
    },
  ];
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatNumber(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value.toFixed(2) : "—";
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

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
