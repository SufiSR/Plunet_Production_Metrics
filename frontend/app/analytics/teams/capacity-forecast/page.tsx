"use client";



import { useMemo, useState } from "react";

import {

  AnalyticsFilterPanel,

  FilterField,

  filterInputClassName,

} from "@/app/components/jira-analytics/AnalyticsReportControls";

import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";

import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";

import { FOCUSED_ENGINEERING_TEAMS } from "@/lib/jira-analytics-teams";

import {

  Area,

  AreaChart,

  CartesianGrid,

  Legend,

  Line,

  LineChart,

  ResponsiveContainer,

  Tooltip,

  XAxis,

  YAxis,

} from "recharts";

import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";

import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";

import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";

import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";

import { useReportChartTheme } from "@/lib/chart-colors";

import { normalizePeriods, sortRecordsByPeriodAsc } from "@/lib/jira-analytics-sort";

import type { ReportQueryParams } from "@/types/jira-analytics";



interface CapacityPersonRow {

  team: string;

  role_bucket: "Development" | "QA";

  role: string;

  person_key: string;

  person: string;

  hours_by_period: Record<string, number>;

  total_hours: number;

}



const ROLE_COLORS = {

  Development: "#4648d4",

  QA: "#0d9488",

};

const TEAM_COLORS = ["#4648d4", "#0d9488", "#c2410c", "#7c3aed"];

const CHART_TEAM_EXCLUDED = new Set<string>(["FreeDevs"]);



const copy = TEAM_PAGE_COPY["capacity-forecast"];



export default function Page() {

  const chartTheme = useReportChartTheme();

  const [params, setParams] = useState<ReportQueryParams>({});

  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({

    deps: [params],

    load: (signal) => fetchAnalyticsReport(reportPaths.capacityForecast, params, signal),

  });



  const periods = useMemo(() => normalizePeriods(stringList(data?.filters?.periods)), [data?.filters?.periods]);

  const teams = useMemo(() => stringList(data?.filters?.available_teams), [data?.filters?.available_teams]);

  const chartTeams = useMemo(

    () => stringList(data?.filters?.chart_teams).filter((team) => !CHART_TEAM_EXCLUDED.has(team)),

    [data?.filters?.chart_teams],

  );

  const rows = useMemo(() => parseRows(data?.table), [data?.table]);

  const heatmapTeams = useMemo(() => orderedHeatmapTeams(rows, teams), [rows, teams]);

  const summary = data?.summary ?? {};

  const series = useMemo(() => parseSeries(data?.series), [data?.series]);

  const explanation = typeof data?.filters?.explanation === "string" ? data.filters.explanation : "";

  const chartYMax = useMemo(() => sharedCapacityYMax(series, chartTeams), [series, chartTeams]);

  const empty = Boolean(!loading && !refreshing && !error && rows.length === 0 && series.length === 0);



  return (

    <JiraAnalyticsShell title="Capacity Forecast" description="" hidePageHeader hideMethodology>

      <TeamReportLayout

        activeReport="capacity-forecast"

        title={copy.heroTitle}

        description={copy.heroDescription}

        readingTip={copy.readingTip}

        metrics={

          <>

            <TeamMetricCard label="Periods" value={periods.length ? String(periods.length) : "Loading"} detail="Recent + forecast months" />

            <TeamMetricCard label="People" value={rows.length ? String(rows.length) : "Loading"} detail="Dev and QA rows" />

            <TeamMetricCard

              label="Total capacity"

              value={formatHours(numberValue(summary.total_hours))}

              detail="Across visible forecast window"

            />

          </>

        }

        controls={

          <AnalyticsFilterPanel

            title="Team filter"

            description="Default window: previous month, current month, and next five months."

          >

            <FilterField label="Team" className="min-w-[14rem]">

              <select

                value={params.team ?? ""}

                onChange={(event) => setParams((prev) => ({ ...prev, team: event.target.value || undefined }))}

                className={filterInputClassName()}

              >

                <option value="">All forecast teams</option>

                {teams.map((team) => (

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

          emptyMessage="No HRWorks capacity data for Developer or QA roles in the selected forecast window."

          slowLoading={slowLoading}

          elapsedSeconds={elapsedSeconds}

          onRetry={retry}

        >

        <div className="grid gap-3 md:grid-cols-4">

          <SummaryCard label="Available hours" value={formatHours(numberValue(summary.available_hours))} />

          <SummaryCard label="Development" value={formatHours(numberValue(summary.development_hours))} />

          <SummaryCard label="QA" value={formatHours(numberValue(summary.qa_hours))} />

          <SummaryCard label="People" value={String(numberValue(summary.people))} />

        </div>



        <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">

          <div className="mb-3">

            <h2 className="font-editorial text-lg font-semibold text-on-surface">Team Capacity Trend</h2>

            <p className="text-xs text-on-surface-variant">

              {explanation || "Capacity means available working hours from HRWorks, already reduced by out-of-office."}

              {chartTeams.length > 1 ? " Charts share the same vertical scale for direct comparison." : ""}

            </p>

          </div>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-stretch">

            {chartTeams.map((team) => (

              <TeamCapacityChart key={team} team={team} data={series} yMax={chartYMax} />

            ))}

          </div>

        </section>



        <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">

          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">

            <div>

              <h2 className="font-editorial text-lg font-semibold text-on-surface">Team Heatmap / Matrix</h2>

              <p className="text-xs text-on-surface-variant">

                Rows are people, columns are months, and cells show available HRWorks hours. FreeDevs appears here but not in the trend charts.

              </p>

            </div>

            <HeatmapLegend />

          </div>

          <CapacityHeatmap rows={rows} periods={periods} teams={heatmapTeams} />

        </section>



        <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">

          <div className="mb-3">

            <h2 className="font-editorial text-lg font-semibold text-on-surface">Monthly Team Capacity</h2>

            <p className="text-xs text-on-surface-variant">Total Development + QA capacity per team and month (focused teams only).</p>

          </div>

          <div className="analytics-chart-plot h-[24rem] w-full p-2">

            <ResponsiveContainer width="100%" height="100%">

              <LineChart data={series}>

                <CartesianGrid {...chartTheme.gridProps} />

                <XAxis
                  dataKey="periodLabel"
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                />

                <YAxis
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                  domain={[0, chartYMax]}
                />

                <Tooltip

                  formatter={(value, name) => [formatHours(numberValue(value)), String(name)]}

                  labelFormatter={(label) => `Month: ${String(label)}`}

                  contentStyle={{
                    background: chartTheme.colors.tooltipBg,
                    color: chartTheme.colors.tooltipText,
                    border: "none",
                    borderRadius: "0.5rem",
                  }}

                />

                <Legend />

                {chartTeams.map((team, index) => (

                  <Line

                    key={team}

                    type="monotone"

                    dataKey={`${team}__total_hours`}

                    name={team}

                    stroke={chartTheme.series[index % chartTheme.series.length]}

                    strokeWidth={2}

                    dot={{ r: 3 }}

                  />

                ))}

              </LineChart>

            </ResponsiveContainer>

          </div>

        </section>

      </ReportPageFrame>

      </TeamReportLayout>

    </JiraAnalyticsShell>

  );

}



function TeamCapacityChart({

  team,

  data,

  yMax,

}: {

  team: string;

  data: Record<string, string | number>[];

  yMax: number;

}) {

  const chartTheme = useReportChartTheme();
  const devColor = chartTheme.series[0];
  const qaColor = chartTheme.series[1];

  return (

    <div className="flex min-w-0 flex-1 flex-col rounded-lg border border-outline-variant/25 bg-surface-container-low p-3">

      <h3 className="mb-2 shrink-0 text-sm font-semibold text-on-surface">{team}</h3>

      <div className="min-h-72 w-full flex-1">

        <ResponsiveContainer width="100%" height="100%">

          <AreaChart data={data}>

            <CartesianGrid {...chartTheme.gridProps} />

            <XAxis
              dataKey="periodLabel"
              tick={chartTheme.axisTick}
              axisLine={chartTheme.axisLine}
              tickLine={chartTheme.tickLine}
            />

            <YAxis
              tick={chartTheme.axisTick}
              axisLine={chartTheme.axisLine}
              tickLine={chartTheme.tickLine}
              domain={[0, yMax]}
              width={48}
            />

            <Tooltip

              formatter={(value, name) => [formatHours(numberValue(value)), labelForRoleKey(String(name))]}

              labelFormatter={(label) => `Month: ${String(label)}`}

            />

            <Legend formatter={(value) => labelForRoleKey(String(value))} />

            <Area

              type="monotone"

              dataKey={`${team}__development_hours`}

              name="Development"

              stackId={team}

              stroke={devColor}

              fill={devColor}

              fillOpacity={0.72}

            />

            <Area

              type="monotone"

              dataKey={`${team}__qa_hours`}

              name="QA"

              stackId={team}

              stroke={qaColor}

              fill={qaColor}

              fillOpacity={0.72}

            />

          </AreaChart>

        </ResponsiveContainer>

      </div>

    </div>

  );

}



function CapacityHeatmap({

  rows,

  periods,

  teams,

}: {

  rows: CapacityPersonRow[];

  periods: string[];

  teams: string[];

}) {

  return (

    <div className="space-y-8">

      {teams.map((team) => {

        const teamRows = rows.filter((row) => row.team === team);

        return (

          <div

            key={team}

            className="overflow-hidden rounded-xl border-2 border-outline-variant/25 bg-surface-container-low shadow-sm"

          >

            <div className="border-b border-outline-variant/20 bg-surface-container px-4 py-3">

              <h3 className="text-base font-semibold text-on-surface">{team}</h3>

            </div>

            <div className="space-y-4 p-4">

              {(["Development", "QA"] as const).map((bucket) => (

                <RoleMatrix

                  key={`${team}-${bucket}`}

                  title={bucket}

                  rows={teamRows.filter((row) => row.role_bucket === bucket)}

                  periods={periods}

                />

              ))}

            </div>

          </div>

        );

      })}

    </div>

  );

}



function RoleMatrix({

  title,

  rows,

  periods,

}: {

  title: "Development" | "QA";

  rows: CapacityPersonRow[];

  periods: string[];

}) {

  return (

    <div className="overflow-x-auto rounded-lg border border-outline-variant/20 bg-surface-container-lowest">

      <table className="w-full min-w-[720px] text-sm">

        <thead className="bg-surface-container-low">

          <tr className="border-b border-outline-variant/20">

            <th className="w-64 px-3 py-2 text-left font-medium text-on-surface-variant">{title}</th>

            {periods.map((period) => (

              <th key={period} className="px-3 py-2 text-right font-medium text-on-surface-variant">

                {formatMonth(period)}

              </th>

            ))}

            <th className="px-3 py-2 text-right font-medium text-on-surface-variant">Total</th>

          </tr>

        </thead>

        <tbody>

          {rows.length === 0 ? (

            <tr>

              <td className="px-3 py-3 text-sm text-on-surface-variant" colSpan={periods.length + 2}>

                No {title.toLowerCase()} people assigned for this forecast window.

              </td>

            </tr>

          ) : (

            rows.map((row) => (

              <tr key={`${row.team}-${row.role_bucket}-${row.person_key}`} className="border-b border-outline-variant/10">

                <td className="px-3 py-2 text-on-surface">

                  <div className="font-medium">{row.person}</div>

                  <div className="text-xs text-on-surface-variant">{row.role}</div>

                </td>

                {periods.map((period) => {

                  const hours = numberValue(row.hours_by_period[period]);

                  return (

                    <td key={period} className="px-2 py-2 text-right">

                      <span

                        className={`inline-flex min-w-16 justify-end rounded-md px-2 py-1 text-xs font-medium tabular-nums ${cellClass(hours)}`}

                        title={`${row.person}: ${formatHours(hours)} in ${formatMonth(period)}`}

                      >

                        {hours > 0 ? formatHours(hours) : "absent"}

                      </span>

                    </td>

                  );

                })}

                <td className="px-3 py-2 text-right font-medium tabular-nums text-on-surface">

                  {formatHours(row.total_hours)}

                </td>

              </tr>

            ))

          )}

        </tbody>

      </table>

    </div>

  );

}



function HeatmapLegend() {

  return (

    <div className="flex flex-wrap gap-2 text-xs">

      <LegendPill className="bg-emerald-100 text-emerald-800" label="healthy >= 120h" />

      <LegendPill className="bg-amber-100 text-amber-800" label="reduced >= 80h" />

      <LegendPill className="bg-red-100 text-red-800" label="low > 0h" />

      <LegendPill className="bg-slate-100 text-slate-500" label="absent" />

    </div>

  );

}



function LegendPill({ className, label }: { className: string; label: string }) {

  return <span className={`rounded-full px-2 py-1 font-medium ${className}`}>{label}</span>;

}



function SummaryCard({ label, value }: { label: string; value: string }) {

  return (

    <div className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">

      <div className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</div>

      <div className="mt-1 text-2xl font-semibold text-on-surface">{value}</div>

    </div>

  );

}



function orderedHeatmapTeams(rows: CapacityPersonRow[], teams: string[]): string[] {

  const fromRows = new Set(rows.map((row) => row.team));

  const ordered: string[] = [...FOCUSED_ENGINEERING_TEAMS.filter(
    (team) => fromRows.has(team) || teams.includes(team),
  )];

  for (const team of teams) {
    if (!ordered.includes(team)) {
      ordered.push(team);

    }

  }

  return ordered;

}



function sharedCapacityYMax(series: Record<string, string | number>[], chartTeams: string[]): number {

  let max = 0;

  for (const point of series) {

    for (const team of chartTeams) {

      const total =

        numberValue(point[`${team}__development_hours`]) + numberValue(point[`${team}__qa_hours`]);

      max = Math.max(max, total);

    }

  }

  if (max <= 0) {

    return 160;

  }

  return Math.ceil(max * 1.08 / 10) * 10;

}



function parseRows(value: unknown): CapacityPersonRow[] {

  if (!Array.isArray(value)) return [];

  return value.flatMap((row) => {

    if (!row || typeof row !== "object") return [];

    const record = row as Record<string, unknown>;

    const team = stringValue(record.team);

    const roleBucket = stringValue(record.role_bucket);

    const person = stringValue(record.person);

    if (!team || !person || (roleBucket !== "Development" && roleBucket !== "QA")) return [];

    return [

      {

        team,

        role_bucket: roleBucket,

        role: stringValue(record.role) || roleBucket,

        person_key: stringValue(record.person_key) || `${team}-${roleBucket}-${person}`,

        person,

        hours_by_period: numberMap(record.hours_by_period),

        total_hours: numberValue(record.total_hours),

      },

    ];

  });

}



function parseSeries(value: unknown): Record<string, string | number>[] {

  if (!Array.isArray(value)) return [];

  const rows = value.flatMap((row) => {

    if (!row || typeof row !== "object") return [];

    const record = row as Record<string, unknown>;

    const period = stringValue(record.period);

    if (!period) return [];

    const shaped: Record<string, string | number> = { period, periodLabel: formatMonth(period) };

    for (const [key, rawValue] of Object.entries(record)) {

      if (key === "period" || key === "teams") continue;

      shaped[key] = numberValue(rawValue);

    }

    return [shaped];

  });

  return sortRecordsByPeriodAsc(rows);

}



function cellClass(hours: number): string {

  if (hours <= 0) return "bg-slate-100 text-slate-500";

  if (hours < 80) return "bg-red-100 text-red-800";

  if (hours < 120) return "bg-amber-100 text-amber-800";

  return "bg-emerald-100 text-emerald-800";

}



function labelForRoleKey(value: string): string {

  if (value.endsWith("__development_hours")) return "Development";

  if (value.endsWith("__qa_hours")) return "QA";

  return value;

}



function stringList(value: unknown): string[] {

  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

}



function numberMap(value: unknown): Record<string, number> {

  if (!value || typeof value !== "object") return {};

  return Object.fromEntries(

    Object.entries(value as Record<string, unknown>).map(([key, rawValue]) => [key, numberValue(rawValue)]),

  );

}



function stringValue(value: unknown): string {

  return typeof value === "string" ? value : "";

}



function numberValue(value: unknown): number {

  return typeof value === "number" && Number.isFinite(value) ? value : 0;

}



function formatHours(value: number): string {

  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}h`;

}



function formatMonth(period: string): string {

  const [year, month] = period.split("-");

  if (!year || !month) return period;

  return `${month}/${year.slice(2)}`;

}


