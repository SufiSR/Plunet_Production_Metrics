"use client";

import { useMemo, useState } from "react";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { lastTwelveMonths } from "@/lib/jira-analytics-dates";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
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
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { JiraIssueLink, jiraBrowseUrl } from "@/app/components/jira-analytics/JiraIssueLink";
import { useJiraBaseUrl } from "@/app/components/jira-analytics/JiraAnalyticsContext";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { useReportChartTheme } from "@/lib/chart-colors";
import {
  compareSortableValues,
  nextSortState,
  sortRecordsByPeriodAsc,
  type SortState,
} from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

type SummarySortKey =
  | "month"
  | "team"
  | "started_roadmap_issues"
  | "interrupting_issues"
  | "maybe_interrupted_issues"
  | "interruption_ratio"
  | "started_roadmap_hours"
  | "interrupting_hours"
  | "time_interruption_ratio";
type IssueSortKey = "active_start" | "issue_key" | "team" | "classification" | "confidence" | "score";

const copy = TEAM_PAGE_COPY["real-interruption-ratio"];

export default function Page() {
  const chartTheme = useReportChartTheme();
  const jiraBaseUrl = useJiraBaseUrl();
  const defaultRange = useMemo(() => lastTwelveMonths(), []);
  const [params, setParams] = useState<ReportQueryParams>(defaultRange);
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [params],
    load: (signal) => fetchAnalyticsReport(reportPaths.realInterruptionRatio, params, signal),
  });
  const [viewMode, setViewMode] = useState<"table" | "chart" | "issues">("table");
  const [basis, setBasis] = useState<"count" | "time">("count");
  const [summarySort, setSummarySort] = useState<SortState<SummarySortKey> | null>(null);
  const [issueSort, setIssueSort] = useState<SortState<IssueSortKey> | null>(null);

  const teams = useMemo(() => stringList(data?.filters?.available_teams), [data?.filters?.available_teams]);
  const notes = useMemo(() => stringList(data?.filters?.evidence_notes), [data?.filters?.evidence_notes]);
  const summaryRows = useMemo(() => {
    return (data?.table ?? []).flatMap((row) => {
      const month = stringValue(row.month);
      const team = stringValue(row.team);
      if (!month || !team) return [];
      return [
        {
          month,
          team,
          started_roadmap_issues: numberValue(row.started_roadmap_issues),
          interrupting_issues: numberValue(row.interrupting_issues),
          maybe_interrupted_issues: numberValue(row.maybe_interrupted_issues),
          interruption_ratio: numberValue(row.interruption_ratio),
          started_roadmap_hours: numberValue(row.started_roadmap_hours),
          interrupting_hours: numberValue(row.interrupting_hours),
          time_interruption_ratio: numberValue(row.time_interruption_ratio),
        },
      ];
    });
  }, [data?.table]);
  const issueRows = useMemo(() => issueRowList(data?.filters?.issue_rows), [data?.filters?.issue_rows]);

  const sortedSummaryRows = useMemo(() => {
      const rows = [...summaryRows].sort(
      (a, b) => compareSortableValues(a.month, b.month, "desc") || compareSortableValues(a.team, b.team, "asc"),
    );
    if (!summarySort) return rows;
    return rows.sort((a, b) => compareSortableValues(a[summarySort.key], b[summarySort.key], summarySort.direction));
  }, [summaryRows, summarySort]);

  const sortedIssueRows = useMemo(() => {
    const rows = [...issueRows].sort((a, b) => compareSortableValues(a.active_start, b.active_start, "desc"));
    if (!issueSort) return rows;
    return rows.sort((a, b) => compareSortableValues(a[issueSort.key], b[issueSort.key], issueSort.direction));
  }, [issueRows, issueSort]);

  const chartData = useMemo(() => {
    const source =
      basis === "time" && Array.isArray(data?.filters?.time_series)
        ? (data.filters.time_series as Record<string, unknown>[])
        : data?.series ?? [];
    const rows = source.flatMap((row) => {
      const period = stringValue(row.period);
      if (!period) return [];
      const shaped: Record<string, string | number> = { period };
      for (const team of teams) {
        shaped[team] = numberValue(row[team]);
      }
      return [shaped];
    });
    return sortRecordsByPeriodAsc(rows);
  }, [basis, data?.filters?.time_series, data?.series, teams]);

  const empty = Boolean(!loading && !refreshing && !error && summaryRows.length === 0);
  const avgRatio =
    summaryRows.length > 0
      ? summaryRows.reduce((sum, row) => sum + row.interruption_ratio, 0) / summaryRows.length
      : null;

  return (
    <JiraAnalyticsShell title="Real interruption ratio" description="" hidePageHeader hideMethodology>
      <TeamReportLayout
        activeReport="real-interruption-ratio"
        title={copy.heroTitle}
        description={copy.heroDescription}
        readingTip={copy.readingTip}
        metrics={
          <>
            <TeamMetricCard label="Team-months" value={summaryRows.length ? String(summaryRows.length) : "Loading"} detail="Summary rows" />
            <TeamMetricCard label="Issue evidence" value={issueRows.length ? String(issueRows.length) : "Loading"} detail="Interrupting candidates" />
            <TeamMetricCard label="Avg ratio" value={formatRatio(avgRatio)} detail="Issue-count basis" />
          </>
        }
        controls={
          <AnalyticsFilterPanel title="Period and view" description="Toggle count vs booked-time basis and inspect issue evidence.">
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
                <option value="">All teams</option>
                {teams.map((team) => (
                  <option key={team} value={team}>
                    {team}
                  </option>
                ))}
              </select>
            </FilterField>
            <div className="flex flex-wrap gap-2 self-end">
              {(["count", "time"] as const).map((nextBasis) => (
                <button
                  key={nextBasis}
                  type="button"
                  onClick={() => setBasis(nextBasis)}
                  className={`h-11 rounded-xl border px-4 text-sm font-semibold ${
                    basis === nextBasis
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-outline-variant/40 text-on-surface"
                  }`}
                >
                  {nextBasis === "count" ? "Issue count" : "Booked time"}
                </button>
              ))}
              {(["table", "chart", "issues"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setViewMode(mode)}
                  className={`h-11 rounded-xl border px-4 text-sm font-semibold capitalize ${
                    viewMode === mode
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-outline-variant/40 text-on-surface"
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage="No real interruption evidence for the selected period."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
          {notes.length > 0 ? (
            <div className="mb-4 rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-3 text-xs text-on-surface-variant">
              {notes.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </div>
          ) : null}
          <ModernReportCard
            eyebrow="Evidence"
            title={viewMode === "chart" ? "Interruption trend" : viewMode === "issues" ? "Issue drilldown" : "Monthly summary"}
            description="Tech support, unassigned bugs, and issues without feature started after roadmap work began."
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
                <YAxis
                  tick={chartTheme.axisTick}
                  axisLine={chartTheme.axisLine}
                  tickLine={chartTheme.tickLine}
                  tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}
                />
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
        ) : viewMode === "issues" ? (
          <IssueTable
            rows={sortedIssueRows}
            sort={issueSort}
            setSort={setIssueSort}
            jiraBaseUrl={jiraBaseUrl}
          />
        ) : (
          <SummaryTable rows={sortedSummaryRows} sort={summarySort} setSort={setSummarySort} basis={basis} />
        )}
          </ModernReportCard>
      </ReportPageFrame>
      </TeamReportLayout>
    </JiraAnalyticsShell>
  );
}

function SummaryTable({
  rows,
  sort,
  setSort,
  basis,
}: {
  rows: ReturnType<typeof summaryRowList>;
  sort: SortState<SummarySortKey> | null;
  setSort: (sort: SortState<SummarySortKey> | null) => void;
  basis: "count" | "time";
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-outline-variant/20 max-h-[32rem] overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant/20">
            <HeaderCell label="Month" sortKey="month" sort={sort} setSort={setSort} />
            <HeaderCell label="Team" sortKey="team" sort={sort} setSort={setSort} />
            {basis === "count" ? (
              <>
                <HeaderCell label="Started Roadmap Issues" sortKey="started_roadmap_issues" sort={sort} setSort={setSort} numeric />
                <HeaderCell label="Interrupting Issues" sortKey="interrupting_issues" sort={sort} setSort={setSort} numeric />
                <HeaderCell label="Maybe Interrupting" sortKey="maybe_interrupted_issues" sort={sort} setSort={setSort} numeric />
                <HeaderCell label="Interruption Ratio" sortKey="interruption_ratio" sort={sort} setSort={setSort} numeric />
              </>
            ) : (
              <>
                <HeaderCell label="Started Roadmap Hours" sortKey="started_roadmap_hours" sort={sort} setSort={setSort} numeric />
                <HeaderCell label="Interrupting Hours" sortKey="interrupting_hours" sort={sort} setSort={setSort} numeric />
                <HeaderCell label="Time Interruption Ratio" sortKey="time_interruption_ratio" sort={sort} setSort={setSort} numeric />
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.team}-${row.month}-${index}`} className="border-b border-outline-variant/10">
              <td className="px-3 py-2 text-on-surface">{row.month}</td>
              <td className="px-3 py-2 text-on-surface">{row.team}</td>
              {basis === "count" ? (
                <>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.started_roadmap_issues}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.interrupting_issues}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.maybe_interrupted_issues}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatRatio(row.interruption_ratio)}</td>
                </>
              ) : (
                <>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.started_roadmap_hours.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.interrupting_hours.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">{formatRatio(row.time_interruption_ratio)}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IssueTable({
  rows,
  sort,
  setSort,
  jiraBaseUrl,
}: {
  rows: ReturnType<typeof issueRowList>;
  sort: SortState<IssueSortKey> | null;
  setSort: (sort: SortState<IssueSortKey> | null) => void;
  jiraBaseUrl: string;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-outline-variant/20 max-h-[32rem] overflow-y-auto">
      <table className="w-full min-w-max text-sm">
        <thead className="sticky top-0 z-10 bg-surface-container-low">
          <tr className="border-b border-outline-variant/20">
            <HeaderCell label="Started" sortKey="active_start" sort={sort} setSort={setSort} />
            <HeaderCell label="Issue" sortKey="issue_key" sort={sort} setSort={setSort} />
            <HeaderCell label="Team" sortKey="team" sort={sort} setSort={setSort} />
            <HeaderCell label="Classification" sortKey="classification" sort={sort} setSort={setSort} />
            <HeaderCell label="Confidence" sortKey="confidence" sort={sort} setSort={setSort} />
            <HeaderCell label="Score" sortKey="score" sort={sort} setSort={setSort} numeric />
            <th className="px-3 py-2 text-left font-medium text-on-surface-variant">Signals</th>
            <th className="px-3 py-2 text-left font-medium text-on-surface-variant">Title</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.issue_key}-${index}`} className="border-b border-outline-variant/10">
              <td className="px-3 py-2 text-on-surface">{row.active_start}</td>
              <td className="px-3 py-2 text-on-surface">
                {jiraBaseUrl ? (
                  <JiraIssueLink
                    issueKey={row.issue_key}
                    issueUrl={jiraBrowseUrl(jiraBaseUrl, row.issue_key)}
                    jiraBaseUrl={jiraBaseUrl}
                  />
                ) : (
                  row.issue_key
                )}
              </td>
              <td className="px-3 py-2 text-on-surface">{row.team}</td>
              <td className="px-3 py-2 text-on-surface">{classificationLabel(row.classification)}</td>
              <td className="px-3 py-2 text-on-surface">
                <ConfidenceBadge confidence={row.confidence} />
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.score}</td>
              <td className="max-w-md px-3 py-2 text-on-surface">
                <SignalBadges signals={row.signals} />
              </td>
              <td className="max-w-lg truncate px-3 py-2 text-on-surface" title={row.issue_title ?? undefined}>
                {row.issue_title ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HeaderCell<TKey extends string>({
  label,
  sortKey,
  sort,
  setSort,
  numeric = false,
}: {
  label: string;
  sortKey: TKey;
  sort: SortState<TKey> | null;
  setSort: (sort: SortState<TKey> | null) => void;
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

function summaryRowList() {
  return [] as {
    month: string;
    team: string;
    started_roadmap_issues: number;
    interrupting_issues: number;
    maybe_interrupted_issues: number;
    interruption_ratio: number;
    started_roadmap_hours: number;
    interrupting_hours: number;
    time_interruption_ratio: number;
  }[];
}

function issueRowList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const record = row as Record<string, unknown>;
    const issueKey = stringValue(record.issue_key);
    const activeStart = stringValue(record.active_start);
    if (!issueKey || !activeStart) return [];
    return [
      {
        active_start: activeStart,
        issue_key: issueKey,
        issue_title: stringValue(record.issue_title),
        team: stringValue(record.team) ?? "Unknown",
        classification: stringValue(record.classification) ?? "planned_or_unknown",
        confidence: stringValue(record.confidence) ?? "none",
        score: numberValue(record.score),
        signals: stringList(record.signals),
      },
    ];
  });
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function formatRatio(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const badge = confidenceBadge(confidence);
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${badge.className}`}
      title={badge.title}
    >
      {badge.label}
    </span>
  );
}

function SignalBadges({ signals }: { signals: string[] }) {
  if (signals.length === 0) {
    return (
      <span
        className="inline-flex rounded-full bg-surface-container px-2.5 py-1 text-xs font-semibold text-on-surface-variant"
        title="No timing or changelog evidence matched the interruption heuristics."
      >
        No signals
      </span>
    );
  }

  return (
    <div className="flex max-w-md flex-wrap gap-1.5">
      {signals.map((signal) => {
        const badge = signalBadge(signal);
        return (
          <span
            key={signal}
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${badge.className}`}
            title={badge.title}
          >
            {badge.label}
          </span>
        );
      })}
    </div>
  );
}

function confidenceBadge(confidence: string): { label: string; title: string; className: string } {
  switch (confidence) {
    case "high":
      return {
        label: "High",
        title: "Strong interruption evidence from a recent bug, priority escalation, or combined score.",
        className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200",
      };
    case "medium":
      return {
        label: "Medium",
        title: "Issue was created within eight weeks before active start.",
        className: "bg-amber-100 text-amber-950 dark:bg-amber-950/60 dark:text-amber-200",
      };
    case "weak":
      return {
        label: "Weak",
        title: "Only late activity was detected; counts as maybe interrupted, not in the main ratio.",
        className: "bg-orange-100 text-orange-950 dark:bg-orange-950/60 dark:text-orange-200",
      };
    default:
      return {
        label: "None",
        title: "No changelog or timing evidence suggests this was an unplanned interruption.",
        className: "bg-surface-container text-on-surface-variant",
      };
  }
}

function signalBadge(signal: string): { label: string; title: string; className: string } {
  switch (signal) {
    case "bug_created_within_16_weeks_before_start":
      return {
        label: "Recent bug",
        title: "Bug-class issue created within 16 weeks before active start.",
        className: "bg-rose-100 text-rose-950 dark:bg-rose-950/60 dark:text-rose-200",
      };
    case "created_within_8_weeks_before_start":
      return {
        label: "Recently created",
        title: "Issue was created within 8 weeks before active start.",
        className: "bg-sky-100 text-sky-950 dark:bg-sky-950/60 dark:text-sky-200",
      };
    case "priority_increased_within_8_weeks_before_start":
      return {
        label: "Priority escalated",
        title: "Priority was raised within 8 weeks before active start.",
        className: "bg-violet-100 text-violet-950 dark:bg-violet-950/60 dark:text-violet-200",
      };
    case "serious_activity_within_4_weeks_before_start":
      return {
        label: "Late activity spike",
        title: "At least two activity events occurred within 4 weeks before active start.",
        className: "bg-teal-100 text-teal-950 dark:bg-teal-950/60 dark:text-teal-200",
      };
    default:
      return {
        label: humanize(signal),
        title: humanize(signal),
        className: "bg-surface-container text-on-surface-variant",
      };
  }
}

function classificationLabel(value: string): string {
  switch (value) {
    case "interrupted":
      return "Interrupted";
    case "maybe_interrupted":
      return "Maybe interrupted";
    case "planned_or_unknown":
      return "Planned or unknown";
    default:
      return humanize(value);
  }
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
