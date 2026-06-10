"use client";

import { useCallback, useMemo, useState } from "react";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { previousMonthYearWindow } from "@/lib/jira-analytics-dates";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
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
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { PeopleDataGate } from "@/app/components/jira-analytics/PeopleDataGate";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { FOCUSED_ENGINEERING_TEAMS } from "@/lib/jira-analytics-teams";
import { useReportChartTheme } from "@/lib/chart-colors";
import {
  compareSortableValues,
  nextSortState,
  sortRecordsByPeriodAsc,
  type SortState,
} from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

interface UtilizationRow {
  month: string;
  team: string;
  person: string;
  role: string | null;
  available_hours: number;
  clocked_hours: number;
  logged_hours: number;
  remaining_hours: number;
  utilization_ratio: number | null;
}

interface UtilizationPerson {
  person: string;
  role: string | null;
  available_hours: number;
  clocked_hours: number;
  logged_hours: number;
  remaining_hours: number;
  utilization_ratio: number | null;
}

interface UtilizationTeam {
  team: string;
  available_hours: number;
  clocked_hours: number;
  logged_hours: number;
  remaining_hours: number;
  utilization_ratio: number | null;
  people: UtilizationPerson[];
}

type UtilizationSortKey =
  | "month"
  | "team"
  | "person"
  | "role"
  | "available_hours"
  | "logged_hours"
  | "utilization_ratio";

const copy = TEAM_PAGE_COPY["availability-vs-booked"];

export default function Page() {
  const chartTheme = useReportChartTheme();
  const defaultRange = useMemo(() => previousMonthYearWindow(), []);
  const [params, setParams] = useState<ReportQueryParams>(defaultRange);
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [params],
    load: (signal) => fetchAnalyticsReport(reportPaths.availabilityVsBooked, params, signal),
  });
  const [expandedTeams, setExpandedTeams] = useState<Set<string>>(() => new Set());
  const [sort, setSort] = useState<SortState<UtilizationSortKey> | null>({
    key: "month",
    direction: "desc",
  });

  const filterTeams = FOCUSED_ENGINEERING_TEAMS;
  const chartTeams = useMemo(() => {
    const chart = stringList(data?.filters?.chart_teams);
    return chart.length > 0 ? chart : filterTeams;
  }, [data?.filters?.chart_teams, filterTeams]);
  const rows = useMemo(() => parseRows(data?.table), [data?.table]);
  const teamGroups = useMemo(() => groupRowsByTeam(rows), [rows]);
  const chartData = useMemo(() => parseChartData(data?.series), [data?.series]);
  const summary = data?.summary ?? {};
  const restricted = summary.people_data_restricted === true;

  const sortedRows = useMemo(() => {
    const defaultSorted = [...rows].sort(
      (a, b) =>
        compareSortableValues(a.month, b.month, "desc") ||
        compareSortableValues(a.team, b.team, "asc") ||
        compareSortableValues(a.person, b.person, "asc"),
    );
    if (!sort) return defaultSorted;
    return [...defaultSorted].sort((a, b) => compareSortableValues(a[sort.key], b[sort.key], sort.direction));
  }, [rows, sort]);

  const toggleTeam = useCallback((team: string) => {
    setExpandedTeams((current) => {
      const next = new Set(current);
      if (next.has(team)) {
        next.delete(team);
      } else {
        next.add(team);
      }
      return next;
    });
  }, []);

  const empty = Boolean(!loading && !refreshing && !error && rows.length === 0 && chartData.length === 0);

  return (
    <JiraAnalyticsShell title="Capacity utilization" description="" hidePageHeader hideMethodology>
      <TeamReportLayout
        activeReport="availability-vs-booked"
        title={copy.heroTitle}
        description={copy.heroDescription}
        readingTip={copy.readingTip}
        metrics={
          <>
            <TeamMetricCard
              label="People"
              value={restricted ? "Restricted" : rows.length ? String(rows.length) : "Loading"}
              detail="Person-month rows"
            />
            <TeamMetricCard
              label="Teams"
              value={chartTeams.length ? String(chartTeams.length) : "Loading"}
              detail="With utilization data"
            />
            <TeamMetricCard
              label="Avg utilization"
              value={
                loading || refreshing
                  ? "Loading"
                  : formatRatio(nullableNumberValue(summary.utilization_ratio))
              }
              detail="Booked hours / available hours"
            />
          </>
        }
        controls={
          <AnalyticsFilterPanel title="Month range" description="Developer and QA roles from HRWorks and Jira worklogs.">
            <FilterField label="From month">
              <input
                type="month"
                value={monthInputValue(params.from)}
                onChange={(event) => {
                  const from = event.target.value ? monthStartDate(event.target.value) : undefined;
                  setParams((prev) => ({ ...prev, from }));
                }}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="To month">
              <input
                type="month"
                value={monthInputValue(params.to)}
                onChange={(event) => {
                  const to = event.target.value ? monthEndDate(event.target.value) : undefined;
                  setParams((prev) => ({ ...prev, to }));
                }}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="Team" className="min-w-[14rem]">
              <select
                value={params.team ?? ""}
                onChange={(event) => setParams((prev) => ({ ...prev, team: event.target.value || undefined }))}
                className={filterInputClassName()}
              >
                <option value="">All teams</option>
                {filterTeams.map((team) => (
                  <option key={team} value={team}>
                    {team}
                  </option>
                ))}
              </select>
            </FilterField>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage="No Developer or QA availability/booked-hour data for the selected period."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
        <div className="grid gap-3 md:grid-cols-4">
          <SummaryCard label="Available hours" value={formatHours(numberValue(summary.available_hours))} />
          <SummaryCard label="Booked hours" value={formatHours(numberValue(summary.logged_hours))} />
          <SummaryCard label="Remaining hours" value={formatHours(numberValue(summary.remaining_hours))} />
          <SummaryCard label="Booked / available" value={formatRatio(nullableNumberValue(summary.utilization_ratio))} />
        </div>

        <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="font-editorial text-lg font-semibold text-on-surface">Monthly team comparison</h2>
              <p className="text-xs text-on-surface-variant">
                Each team stack shows booked Jira hours filled inside total HRWorks availability.
              </p>
            </div>
            {numberValue(summary.missing_hrworks_people) > 0 ? (
              <span className="rounded-full bg-error/10 px-3 py-1 text-xs font-medium text-error">
                {numberValue(summary.missing_hrworks_people)} people with booked hours but no HRWorks capacity
              </span>
            ) : null}
          </div>
          <div className="analytics-chart-plot h-[28rem] w-full p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid {...chartTheme.gridProps} />
                <XAxis
                  dataKey="period"
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                />
                <YAxis tick={chartTheme.axisTick} axisLine={chartTheme.axisLine} tickLine={chartTheme.tickLine} />
                <Tooltip content={<UtilizationChartTooltip />} cursor={{ fill: "rgba(148,163,184,0.12)" }} shared={false} />
                <Legend />
                {chartTeams.map((team, index) => (
                  <Bar
                    key={`${team}-logged`}
                    dataKey={`${team}__logged_hours`}
                    stackId={team}
                    fill={chartTheme.series[index % chartTheme.series.length]}
                    name={team}
                  />
                ))}
                {chartTeams.map((team, index) => (
                  <Bar
                    key={`${team}-remaining`}
                    dataKey={`${team}__remaining_hours`}
                    stackId={team}
                    fill={chartTheme.series[index % chartTheme.series.length]}
                    fillOpacity={0.22}
                    legendType="none"
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="font-editorial text-lg font-semibold text-on-surface">Team drilldown</h2>
          {restricted ? <PeopleDataGate restricted /> : null}
          {!restricted ? (
            <div className="space-y-3">
              {teamGroups.map((group) => {
              const expanded = expandedTeams.has(group.team);
              return (
                <section key={group.team} className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest">
                  <button
                    type="button"
                    onClick={() => toggleTeam(group.team)}
                    aria-expanded={expanded}
                    className="flex w-full flex-wrap items-center justify-between gap-3 border-b border-outline-variant/28 px-4 py-3 text-left hover:bg-surface-container-low/60"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="material-symbols-outlined text-[20px] text-on-surface-variant">
                        {expanded ? "expand_more" : "chevron_right"}
                      </span>
                      <span className="text-sm font-editorial font-semibold text-on-surface">{group.team}</span>
                    </span>
                    <HoursSummary item={group} />
                  </button>
                  {expanded ? (
                    <div className="divide-y divide-outline-variant/10">
                      {group.people.map((person) => (
                        <div
                          key={`${group.team}-${person.person}-${person.role ?? "role"}`}
                          className="flex flex-wrap items-baseline justify-between gap-3 px-4 py-2 text-sm"
                        >
                          <span className="min-w-0 text-on-surface">
                            {person.person}
                            {person.role ? (
                              <span className="ml-2 text-xs text-on-surface-variant">{person.role}</span>
                            ) : null}
                          </span>
                          <HoursSummary item={person} />
                        </div>
                      ))}
                    </div>
                  ) : null}
                </section>
              );
              })}
            </div>
          ) : null}
        </section>

        <section className="space-y-3">
          <h2 className="font-editorial text-lg font-semibold text-on-surface">Monthly person rows</h2>
          {restricted ? <PeopleDataGate restricted /> : null}
          {!restricted ? (
          <div className="max-h-[32rem] overflow-auto rounded-xl border border-outline-variant/20">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-surface-container-low">
                <tr className="border-b border-outline-variant/20">
                  <HeaderCell label="Month" sortKey="month" sort={sort} setSort={setSort} />
                  <HeaderCell label="Team" sortKey="team" sort={sort} setSort={setSort} />
                  <HeaderCell label="Person" sortKey="person" sort={sort} setSort={setSort} />
                  <HeaderCell label="Role" sortKey="role" sort={sort} setSort={setSort} />
                  <HeaderCell label="Available" sortKey="available_hours" sort={sort} setSort={setSort} numeric />
                  <HeaderCell label="Booked" sortKey="logged_hours" sort={sort} setSort={setSort} numeric />
                  <HeaderCell label="Ratio" sortKey="utilization_ratio" sort={sort} setSort={setSort} numeric />
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, index) => (
                  <tr key={`${row.month}-${row.team}-${row.person}-${index}`} className="border-b border-outline-variant/10">
                    <td className="px-3 py-2 text-on-surface">{row.month}</td>
                    <td className="px-3 py-2 text-on-surface">{row.team}</td>
                    <td className="px-3 py-2 text-on-surface">{row.person}</td>
                    <td className="px-3 py-2 text-on-surface">{row.role ?? "Unknown"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatHours(row.available_hours)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatHours(row.logged_hours)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-on-surface">
                      {formatRatio(row.utilization_ratio)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          ) : null}
        </section>
      </ReportPageFrame>
      </TeamReportLayout>
    </JiraAnalyticsShell>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</div>
      <div className="mt-1 text-xl font-editorial font-semibold text-on-surface">{value}</div>
    </div>
  );
}

function HoursSummary({ item }: { item: Pick<UtilizationTeam, "available_hours" | "logged_hours" | "utilization_ratio"> }) {
  return (
    <span className="flex flex-wrap items-center justify-end gap-3 text-xs text-on-surface-variant">
      <span>Available: {formatHours(item.available_hours)}</span>
      <span>Booked: {formatHours(item.logged_hours)}</span>
      <span>Ratio: {formatRatio(item.utilization_ratio)}</span>
    </span>
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
  sortKey: UtilizationSortKey;
  sort: SortState<UtilizationSortKey> | null;
  setSort: (sort: SortState<UtilizationSortKey> | null) => void;
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

function groupRowsByTeam(rows: UtilizationRow[]): UtilizationTeam[] {
  const teams = new Map<string, Map<string, UtilizationPerson>>();
  for (const row of rows) {
    if (!teams.has(row.team)) teams.set(row.team, new Map());
    const people = teams.get(row.team);
    if (!people) continue;
    const key = `${row.person}::${row.role ?? ""}`;
    const existing = people.get(key) ?? {
      person: row.person,
      role: row.role,
      available_hours: 0,
      clocked_hours: 0,
      logged_hours: 0,
      remaining_hours: 0,
      utilization_ratio: null,
    };
    existing.available_hours += row.available_hours;
    existing.clocked_hours += row.clocked_hours;
    existing.logged_hours += row.logged_hours;
    existing.remaining_hours += row.remaining_hours;
    existing.utilization_ratio =
      existing.available_hours > 0 ? existing.logged_hours / existing.available_hours : null;
    people.set(key, existing);
  }

  return [...teams.entries()]
    .map(([team, peopleMap]) => {
      const people = [...peopleMap.values()]
        .map((person) => ({
          ...person,
          available_hours: round2(person.available_hours),
          clocked_hours: round2(person.clocked_hours),
          logged_hours: round2(person.logged_hours),
          remaining_hours: round2(person.remaining_hours),
          utilization_ratio: person.utilization_ratio === null ? null : round4(person.utilization_ratio),
        }))
        .sort((a, b) => compareSortableValues(a.logged_hours, b.logged_hours, "desc"));
      const available = people.reduce((sum, person) => sum + person.available_hours, 0);
      const clocked = people.reduce((sum, person) => sum + person.clocked_hours, 0);
      const logged = people.reduce((sum, person) => sum + person.logged_hours, 0);
      const remaining = available - logged;
      return {
        team,
        available_hours: round2(available),
        clocked_hours: round2(clocked),
        logged_hours: round2(logged),
        remaining_hours: round2(remaining),
        utilization_ratio: available > 0 ? round4(logged / available) : null,
        people,
      };
    })
    .sort((a, b) => compareSortableValues(a.team, b.team, "asc"));
}

function parseRows(value: AnalyticsReportResponse["table"] | undefined): UtilizationRow[] {
  return (value ?? []).flatMap((row) => {
    const month = stringValue(row.month);
    const team = stringValue(row.team);
    const person = stringValue(row.person);
    if (!month || !team || !person) return [];
    return [
      {
        month,
        team,
        person,
        role: stringValue(row.role),
        available_hours: numberValue(row.available_hours),
        clocked_hours: numberValue(row.clocked_hours),
        logged_hours: numberValue(row.logged_hours),
        remaining_hours: numberValue(row.remaining_hours),
        utilization_ratio: nullableNumberValue(row.utilization_ratio),
      },
    ];
  });
}

function UtilizationChartTooltip({
  active,
  label,
  payload,
}: {
  active?: boolean;
  label?: string | number;
  payload?: Array<{ dataKey?: string; color?: string; payload?: Record<string, unknown> }>;
}) {
  if (!active || !payload?.length) return null;

  const entry = payload[0];
  const dataKey = String(entry.dataKey ?? "");
  const team = teamFromChartDataKey(dataKey);
  if (!team) return null;

  const row = entry.payload ?? {};
  const booked = numberValue(row[`${team}__logged_hours`]);
  const notBooked = numberValue(row[`${team}__remaining_hours`]);
  const color = entry.color ?? "#64748b";

  return (
    <div className="rounded-lg border border-outline-variant/20 bg-surface-container-lowest px-3 py-2 text-xs shadow-md">
      <p className="mb-1.5 font-medium text-on-surface">{String(label ?? "")}</p>
      <div className="space-y-1 text-on-surface-variant">
        <p>
          <span className="font-medium" style={{ color }}>
            {team} booked
          </span>
          {": "}
          {formatHours(booked)}
        </p>
        <p>
          <span className="font-medium" style={{ color }}>
            {team} not booked
          </span>
          {": "}
          {formatHours(notBooked)}
        </p>
      </div>
    </div>
  );
}

function teamFromChartDataKey(key: string): string | null {
  const suffix = key.endsWith("__logged_hours")
    ? "__logged_hours"
    : key.endsWith("__remaining_hours")
      ? "__remaining_hours"
      : null;
  if (!suffix) return null;
  const team = key.slice(0, -suffix.length);
  return team || null;
}

function parseChartData(value: AnalyticsReportResponse["series"] | undefined): Array<Record<string, string | number>> {
  const rows = (value ?? []).flatMap((row) => {
    const period = stringValue(row.period);
    if (!period) return [];
    const parsed: Record<string, string | number> = { period };
    for (const [key, raw] of Object.entries(row)) {
      if (key.endsWith("__logged_hours") || key.endsWith("__remaining_hours")) {
        parsed[key] = numberValue(raw);
      }
    }
    return [parsed];
  });
  return sortRecordsByPeriodAsc(rows);
}

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function monthInputValue(value: string | undefined): string {
  return value ? value.slice(0, 7) : "";
}

function monthStartDate(value: string): string {
  return `${value}-01`;
}

function monthEndDate(value: string): string {
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return `${value}-01`;
  return formatDate(new Date(year, month, 0));
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nullableNumberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function formatHours(value: number): string {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}h`;
}

function formatRatio(value: number | null): string {
  if (value === null) return "n/a";
  return `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}
