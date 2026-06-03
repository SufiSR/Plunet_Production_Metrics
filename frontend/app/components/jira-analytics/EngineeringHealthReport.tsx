"use client";

import { useMemo, useState } from "react";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import { MonthlyTeamTrendChart } from "@/app/components/jira-analytics/MonthlyTeamTrendChart";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import type { TeamReportId } from "@/app/components/jira-analytics/TeamReportLayout";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { lastSixMonths } from "@/lib/jira-analytics-dates";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
import { comparePeriodValuesDesc } from "@/lib/jira-analytics-sort";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

type ComponentKey =
  | "flow_efficiency"
  | "focus_health"
  | "interruption_health"
  | "execution_predictability"
  | "work_shape_health";

interface HealthRow {
  team: string;
  month: string;
  health_index: number | null;
  confidence: number;
  biggest_drag: string | null;
  second_drag: string | null;
  flow_efficiency: number | null;
  focus_health: number | null;
  interruption_health: number | null;
  execution_predictability: number | null;
  work_shape_health: number | null;
  roadmap_hours: number | null;
  continuous_improvement_hours: number | null;
  roadmap_focus: number | null;
  interruption_ratio: number | null;
  time_interruption_ratio: number | null;
  active_work_hours: number | null;
  queue_hours: number | null;
  avg_done_per_week: number | null;
  feature_hours: number | null;
  risk_adjusted_feature_hours: number | null;
  avg_feature_risk: number | null;
  dev_workforce_strength_hours: number | null;
  qa_workforce_strength_hours: number | null;
  workforce_strength_hours: number | null;
  dev_booked_hours: number | null;
  qa_booked_hours: number | null;
  booked_hours: number | null;
  dev_utilization_ratio: number | null;
  qa_utilization_ratio: number | null;
  utilization_ratio: number | null;
}

interface EngineeringHealthReportProps {
  activeReport: Extract<TeamReportId, "health" | "comparison">;
  comparisonMode?: boolean;
}

const COMPONENT_KEYS: ComponentKey[] = [
  "flow_efficiency",
  "focus_health",
  "interruption_health",
  "execution_predictability",
  "work_shape_health",
];

const DEFAULT_COMPONENT_LABELS: Record<ComponentKey, string> = {
  flow_efficiency: "Flow efficiency",
  focus_health: "Roadmap focus",
  interruption_health: "Interruption pressure",
  execution_predictability: "Throughput predictability",
  work_shape_health: "Work shape risk",
};

const DEFAULT_WEIGHTS: Record<ComponentKey, number> = {
  flow_efficiency: 0.25,
  focus_health: 0.2,
  interruption_health: 0.2,
  execution_predictability: 0.2,
  work_shape_health: 0.15,
};

const KPI_EXPLANATIONS: Record<ComponentKey, { source: string; formula: string; notes: string }> = {
  flow_efficiency: {
    source: "Active vs passive workflow time",
    formula: "active_work_hours / (active_work_hours + queue_hours) × 100",
    notes:
      "Queue hours combine Product Queue, Dev Queue, and QA Queue from status dwell time for issues created in that calendar month.",
  },
  focus_health: {
    source: "Roadmap focus / planned-vs-unplanned allocated hours",
    formula: "50 + 50 × roadmap_focus, where roadmap_focus = roadmap_hours / (roadmap_hours + continuous_improvement_hours)",
    notes:
      "The lower bound is softened so necessary support and improvement work is treated as pressure, not as total delivery failure.",
  },
  interruption_health: {
    source: "Real interruption ratio, with roadmap-focus fallback",
    formula: "(1 − time_interruption_ratio) × 100, or roadmap_focus × 100 when real-interruption evidence is unavailable",
    notes:
      "Real interruption uses active-start timing and Jira changelog evidence for the focused teams. The fallback keeps other teams comparable but is less precise.",
  },
  execution_predictability: {
    source: "Throughput stability",
    formula: "predictability × 100, where predictability = 1 − (weekly throughput stddev / average weekly throughput)",
    notes:
      "This is computed separately per calendar month from resolved issues per ISO week, so it can change month by month.",
  },
  work_shape_health: {
    source: "Feature delivery risk weighted by team feature hours",
    formula: "100 − weighted_average(feature_risk_score), weighted by allocated feature hours",
    notes:
      "Feature risk combines feature size and production/lifecycle duration. The raw table shows risk-adjusted feature hours, not the same roadmap hours used for focus.",
  },
};

export function EngineeringHealthReport({
  activeReport,
  comparisonMode = false,
}: EngineeringHealthReportProps) {
  const defaultRange = useMemo(() => lastSixMonths(), []);
  const [params, setParams] = useState<ReportQueryParams>(defaultRange);
  const copy = TEAM_PAGE_COPY[activeReport];
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [params],
    load: (signal) => fetchAnalyticsReport(reportPaths.engineeringHealth, params, signal),
  });

  const teams = useMemo(() => stringList(data?.filters?.focused_teams), [data?.filters?.focused_teams]);
  const availableTeams = useMemo(
    () => stringList(data?.filters?.available_teams),
    [data?.filters?.available_teams],
  );
  const componentLabels = useMemo(
    () => componentLabelMap(data?.filters?.component_labels),
    [data?.filters?.component_labels],
  );
  const weights = useMemo(() => weightMap(data?.filters?.weights), [data?.filters?.weights]);
  const rows = useMemo(() => healthRows(data?.table), [data?.table]);
  const latestRows = useMemo(() => latestRowByTeam(rows, teams), [rows, teams]);
  const teamDeltas = useMemo(() => scoreDeltaByTeam(rows, teams), [rows, teams]);
  const chartData = useMemo(() => data?.series ?? [], [data?.series]);
  const empty = Boolean(!loading && !refreshing && !error && rows.length === 0);

  return (
    <TeamReportLayout
      activeReport={activeReport}
      title={copy.heroTitle}
      description={copy.heroDescription}
      readingTip={copy.readingTip}
      lineageTitle={copy.lineageTitle}
      metrics={data ? <HealthSummaryMetrics data={data} /> : undefined}
      controls={
        <AnalyticsFilterPanel title="Period and team" description="Composite health is computed per calendar month.">
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
              <option value="">Focused teams</option>
              {availableTeams.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </FilterField>
          <div className="self-end">
            <button
              type="button"
              onClick={() => setParams(defaultRange)}
              className="h-11 rounded-xl border border-outline-variant/40 px-4 text-sm font-semibold text-on-surface hover:bg-surface-container-high"
            >
              Last 6 months
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
        emptyMessage="No engineering health data for the selected filters."
        slowLoading={slowLoading}
        elapsedSeconds={elapsedSeconds}
        onRetry={retry}
      >
        {data ? (
          <div className="space-y-6">
            <ModernReportCard
              eyebrow="Score model"
              title="How the index is built"
              description="Five weighted components roll up into the monthly health index shown below."
            >
              <KpiExplanation labels={componentLabels} weights={weights} comparisonMode={comparisonMode} />
            </ModernReportCard>
            <TeamScoreCards rows={latestRows} deltas={teamDeltas} comparisonMode={comparisonMode} />
            <WorkforceStrengthPanel rows={rows} teams={teams} comparisonMode={comparisonMode} />
            <ModernReportCard
              eyebrow="Trend"
              title="Health over time"
              description="Monthly composite score. Missing component coverage lowers confidence and can leave a month unscored."
            >
              <MonthlyTeamTrendChart data={chartData} teams={teams} />
            </ModernReportCard>
            <ComponentBreakdown rows={latestRows} labels={componentLabels} />
            {comparisonMode ? (
              <SixMonthComparison rows={rows} teams={teams} labels={componentLabels} />
            ) : null}
            <RawMetricsTable rows={rows} labels={componentLabels} />
          </div>
        ) : null}
      </ReportPageFrame>
    </TeamReportLayout>
  );
}

function HealthSummaryMetrics({ data }: { data: AnalyticsReportResponse }) {
  return (
    <>
      <TeamMetricCard
        label="Average health"
        value={formatNullableScore(numberValue(data.summary.average_health_index))}
        detail="Across scored team-months"
      />
      <TeamMetricCard label="Worst drag" value={humanizeDrag(stringValue(data.summary.worst_drag))} detail="Most common negative driver" />
      <TeamMetricCard
        label="Coverage"
        value={formatPercent(numberValue(data.summary.data_coverage))}
        detail={`${numberValue(data.summary.scored_team_months) ?? 0} / ${numberValue(data.summary.total_team_months) ?? 0} scored months`}
      />
    </>
  );
}

function KpiExplanation({
  labels,
  weights,
  comparisonMode,
}: {
  labels: Record<ComponentKey, string>;
  weights: Record<ComponentKey, number>;
  comparisonMode: boolean;
}) {
  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <div className="mb-4 space-y-1">
        <h2 className="text-sm font-editorial font-semibold text-on-surface">
          {comparisonMode ? "How This Comparison Is Derived" : "How These KPIs Are Derived"}
        </h2>
        <p className="max-w-4xl text-xs text-on-surface-variant">
          The health index is a weighted average of available component scores. Each component is
          normalized to 0-100 before weighting. If less than 50% of the configured component weight
          has data, the health score stays empty and confidence shows the missing coverage.
          Workforce Strength is shown as capacity context and is not included in the score.
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <KpiExplanationCard
          title="Health index"
          source="Weighted component model"
          formula={COMPONENT_KEYS.map((key) => `${formatWeight(weights[key])} ${labels[key]}`).join(" + ")}
          notes="Biggest drag and second drag are the lowest available component scores for that team/month."
        />
        <KpiExplanationCard
          title="Confidence"
          source="Component data coverage"
          formula="available component weight / total configured weight"
          notes="A confidence of 60% means the score was calculated from components representing 60% of the model weight."
        />
        <KpiExplanationCard
          title="Workforce Strength"
          source="HRWorks planned hours and Jira booked hours"
          formula="Dev/QA planned HRWorks hours, with utilization = booked Jira hours / planned hours"
          notes="This is not weighted into the health score. It explains capacity context beside the delivery-health components."
        />
        {COMPONENT_KEYS.map((key) => (
          <KpiExplanationCard
            key={key}
            title={labels[key]}
            source={KPI_EXPLANATIONS[key].source}
            formula={KPI_EXPLANATIONS[key].formula}
            notes={`Weight: ${formatWeight(weights[key])}. ${KPI_EXPLANATIONS[key].notes}`}
          />
        ))}
      </div>
    </section>
  );
}

function KpiExplanationCard({
  title,
  source,
  formula,
  notes,
}: {
  title: string;
  source: string;
  formula: string;
  notes: string;
}) {
  return (
    <article className="rounded-lg border border-outline-variant/20 bg-surface-container-low p-3 text-xs">
      <h3 className="font-semibold text-on-surface">{title}</h3>
      <p className="mt-2 text-on-surface-variant">
        <span className="font-medium text-on-surface">Source: </span>
        {source}
      </p>
      <p className="mt-2 text-on-surface-variant">
        <span className="font-medium text-on-surface">Formula: </span>
        <code className="rounded bg-surface-container-high px-1 py-0.5 text-[11px] text-on-surface">
          {formula}
        </code>
      </p>
      <p className="mt-2 text-on-surface-variant">{notes}</p>
    </article>
  );
}

function TeamScoreCards({
  rows,
  deltas,
  comparisonMode,
}: {
  rows: HealthRow[];
  deltas: Record<string, number | null>;
  comparisonMode: boolean;
}) {
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {rows.map((row) => (
        <div key={row.team} className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-on-surface">{row.team}</h2>
              <p className="text-xs text-on-surface-variant">{row.month}</p>
            </div>
            <span className={`rounded-full px-2 py-1 text-xs font-medium ${scoreBandClass(row.health_index)}`}>
              {formatNullableScore(row.health_index)}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            <Metric label="Confidence" value={formatPercent(row.confidence)} />
            <Metric label={comparisonMode ? "6 mo delta" : "Trend delta"} value={formatDelta(deltas[row.team])} />
            <Metric label="Biggest drag" value={humanizeDrag(row.biggest_drag)} />
            <Metric label="Second drag" value={humanizeDrag(row.second_drag)} />
          </div>
        </div>
      ))}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-on-surface-variant">{label}</div>
      <div className="font-medium text-on-surface">{value}</div>
    </div>
  );
}

function ComponentBreakdown({ rows, labels }: { rows: HealthRow[]; labels: Record<ComponentKey, string> }) {
  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <h2 className="mb-3 text-sm font-editorial font-semibold text-on-surface">Latest Component Breakdown</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {rows.map((row) => (
          <div key={row.team} className="space-y-2">
            <h3 className="text-sm font-medium text-on-surface">{row.team}</h3>
            {COMPONENT_KEYS.map((key) => (
              <ComponentBar key={key} label={labels[key]} value={row[key]} />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function ComponentBar({ label, value }: { label: string; value: number | null }) {
  const width = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="grid grid-cols-[9rem_1fr_3rem] items-center gap-2 text-xs">
      <span className="truncate text-on-surface-variant">{label}</span>
      <div className="h-2 rounded-full bg-surface-container-high">
        <div className="h-2 rounded-full bg-primary" style={{ width: `${width}%` }} />
      </div>
      <span className="text-right tabular-nums text-on-surface">{formatNullableScore(value)}</span>
    </div>
  );
}

function WorkforceStrengthPanel({
  rows,
  teams,
  comparisonMode,
}: {
  rows: HealthRow[];
  teams: string[];
  comparisonMode: boolean;
}) {
  const latestRows = latestRowByTeam(rows, teams);
  const rangeRows = workforceRangeByTeam(rows, teams);
  const displayRows = comparisonMode ? rangeRows : latestRows;
  const subtitle = comparisonMode
    ? "Six-month Dev/QA capacity context. These values are summed across the selected comparison window and are not part of the score."
    : "Latest-month Dev/QA capacity context. These values are not part of the score.";

  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <div className="mb-3 space-y-1">
        <h2 className="text-sm font-editorial font-semibold text-on-surface">Workforce Strength</h2>
        <p className="max-w-4xl text-xs text-on-surface-variant">{subtitle}</p>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {displayRows.map((row) => (
          <article key={row.team} className="rounded-lg border border-outline-variant/20 bg-surface-container-low p-3">
            <div className="mb-3 flex items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold text-on-surface">{row.team}</h3>
              <span className="text-xs text-on-surface-variant">
                {comparisonMode ? "selected window" : row.month}
              </span>
            </div>
            <div className="grid gap-2 text-xs">
              <WorkforceMetric
                label="Dev"
                planned={row.dev_workforce_strength_hours}
                booked={row.dev_booked_hours}
                ratio={row.dev_utilization_ratio}
              />
              <WorkforceMetric
                label="QA"
                planned={row.qa_workforce_strength_hours}
                booked={row.qa_booked_hours}
                ratio={row.qa_utilization_ratio}
              />
              <WorkforceMetric
                label="Total"
                planned={row.workforce_strength_hours}
                booked={row.booked_hours}
                ratio={row.utilization_ratio}
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function WorkforceMetric({
  label,
  planned,
  booked,
  ratio,
}: {
  label: string;
  planned: number | null;
  booked: number | null;
  ratio: number | null;
}) {
  return (
    <div className="grid grid-cols-[4rem_1fr_1fr_4rem] gap-2">
      <span className="font-medium text-on-surface">{label}</span>
      <span className="text-right tabular-nums text-on-surface-variant">{formatHours(planned)} planned</span>
      <span className="text-right tabular-nums text-on-surface-variant">{formatHours(booked)} booked</span>
      <span className="text-right tabular-nums text-on-surface">{formatPercent(ratio)}</span>
    </div>
  );
}

function SixMonthComparison({
  rows,
  teams,
  labels,
}: {
  rows: HealthRow[];
  teams: string[];
  labels: Record<ComponentKey, string>;
}) {
  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <h2 className="mb-3 text-sm font-editorial font-semibold text-on-surface">Six-Month Team Comparison</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-max text-sm">
          <thead>
            <tr className="border-b border-outline-variant/20 text-on-surface-variant">
              <th className="px-3 py-2 text-left font-medium">Team</th>
              <th className="px-3 py-2 text-right font-medium">Start</th>
              <th className="px-3 py-2 text-right font-medium">Latest</th>
              <th className="px-3 py-2 text-right font-medium">Delta</th>
              <th className="px-3 py-2 text-left font-medium">Best dimension</th>
              <th className="px-3 py-2 text-left font-medium">Worst dimension</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => {
              const teamRows = rows
                .filter((row) => row.team === team)
                .sort((a, b) => a.month.localeCompare(b.month));
              const start = firstScoredRow(teamRows);
              const latest = [...teamRows].reverse().find((row) => row.health_index !== null) ?? null;
              const dimensions = latest ? rankedDimensions(latest) : [];
              const worstDimension = dimensions.length ? dimensions[dimensions.length - 1] : null;
              return (
                <tr key={team} className="border-b border-outline-variant/10">
                  <td className="px-3 py-2 font-medium text-on-surface">{team}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatNullableScore(start?.health_index ?? null)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatNullableScore(latest?.health_index ?? null)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatDelta(delta(start, latest))}</td>
                  <td className="px-3 py-2">{dimensions[0] ? labels[dimensions[0][0]] : "No data"}</td>
                  <td className="px-3 py-2">{worstDimension ? labels[worstDimension[0]] : "No data"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RawMetricsTable({ rows, labels }: { rows: HealthRow[]; labels: Record<ComponentKey, string> }) {
  const sortedRows = [...rows].sort(
    (a, b) => comparePeriodValuesDesc(a.month, b.month) || a.team.localeCompare(b.team),
  );

  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4">
      <h2 className="mb-3 text-sm font-editorial font-semibold text-on-surface">Raw Component Metrics</h2>
      <div className="max-h-[32rem] overflow-auto">
        <table className="w-full min-w-max text-sm">
          <thead className="sticky top-0 bg-surface-container-low">
            <tr className="border-b border-outline-variant/20 text-on-surface-variant">
              {[
                "Team",
                "Month",
                "Health",
                "Confidence",
                ...COMPONENT_KEYS.map((key) => labels[key]),
                "Roadmap h",
                "CI h",
                "Queue h",
                "Done/week",
                "Risk-adj h",
                "Avg risk",
                "Dev strength",
                "QA strength",
                "Booked h",
                "Utilization",
              ].map((column) => (
                <th key={column} className="px-3 py-2 text-right font-medium first:text-left">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => (
              <tr key={`${row.team}-${row.month}`} className="border-b border-outline-variant/10">
                <td className="px-3 py-2 font-medium text-on-surface">{row.team}</td>
                <td className="px-3 py-2 text-right tabular-nums">{row.month}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNullableScore(row.health_index)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatPercent(row.confidence)}</td>
                {COMPONENT_KEYS.map((key) => (
                  <td key={key} className="px-3 py-2 text-right tabular-nums">
                    {formatNullableScore(row[key])}
                  </td>
                ))}
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.roadmap_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.continuous_improvement_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.queue_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.avg_done_per_week)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.risk_adjusted_feature_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.avg_feature_risk)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatHours(row.dev_workforce_strength_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatHours(row.qa_workforce_strength_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatHours(row.booked_hours)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatPercent(row.utilization_ratio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function healthRows(value: unknown): HealthRow[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    const team = stringValue(row.team);
    const month = stringValue(row.month);
    if (!team || !month) return [];
    return [
      {
        team,
        month,
        health_index: numberValue(row.health_index),
        confidence: numberValue(row.confidence) ?? 0,
        biggest_drag: stringValue(row.biggest_drag),
        second_drag: stringValue(row.second_drag),
        flow_efficiency: numberValue(row.flow_efficiency),
        focus_health: numberValue(row.focus_health),
        interruption_health: numberValue(row.interruption_health),
        execution_predictability: numberValue(row.execution_predictability),
        work_shape_health: numberValue(row.work_shape_health),
        roadmap_hours: numberValue(row.roadmap_hours),
        continuous_improvement_hours: numberValue(row.continuous_improvement_hours),
        roadmap_focus: numberValue(row.roadmap_focus),
        interruption_ratio: numberValue(row.interruption_ratio),
        time_interruption_ratio: numberValue(row.time_interruption_ratio),
        active_work_hours: numberValue(row.active_work_hours),
        queue_hours: numberValue(row.queue_hours),
        avg_done_per_week: numberValue(row.avg_done_per_week),
        feature_hours: numberValue(row.feature_hours),
        risk_adjusted_feature_hours: numberValue(row.risk_adjusted_feature_hours),
        avg_feature_risk: numberValue(row.avg_feature_risk),
        dev_workforce_strength_hours: numberValue(row.dev_workforce_strength_hours),
        qa_workforce_strength_hours: numberValue(row.qa_workforce_strength_hours),
        workforce_strength_hours: numberValue(row.workforce_strength_hours),
        dev_booked_hours: numberValue(row.dev_booked_hours),
        qa_booked_hours: numberValue(row.qa_booked_hours),
        booked_hours: numberValue(row.booked_hours),
        dev_utilization_ratio: numberValue(row.dev_utilization_ratio),
        qa_utilization_ratio: numberValue(row.qa_utilization_ratio),
        utilization_ratio: numberValue(row.utilization_ratio),
      },
    ];
  });
}

function latestRowByTeam(rows: HealthRow[], teams: string[]): HealthRow[] {
  return teams.flatMap((team) => {
    const teamRows = rows.filter((row) => row.team === team).sort((a, b) => b.month.localeCompare(a.month));
    return teamRows[0] ? [teamRows[0]] : [];
  });
}

function scoreDeltaByTeam(rows: HealthRow[], teams: string[]): Record<string, number | null> {
  const result: Record<string, number | null> = {};
  for (const team of teams) {
    const teamRows = rows.filter((row) => row.team === team).sort((a, b) => a.month.localeCompare(b.month));
    result[team] = delta(firstScoredRow(teamRows), [...teamRows].reverse().find((row) => row.health_index !== null) ?? null);
  }
  return result;
}

function workforceRangeByTeam(rows: HealthRow[], teams: string[]): HealthRow[] {
  return teams.flatMap((team) => {
    const teamRows = rows.filter((row) => row.team === team);
    if (!teamRows.length) return [];
    const totals = teamRows.reduce(
      (acc, row) => {
        acc.devAvailable += row.dev_workforce_strength_hours ?? 0;
        acc.qaAvailable += row.qa_workforce_strength_hours ?? 0;
        acc.devBooked += row.dev_booked_hours ?? 0;
        acc.qaBooked += row.qa_booked_hours ?? 0;
        return acc;
      },
      { devAvailable: 0, qaAvailable: 0, devBooked: 0, qaBooked: 0 },
    );
    const totalAvailable = totals.devAvailable + totals.qaAvailable;
    const totalBooked = totals.devBooked + totals.qaBooked;
    return [
      {
        ...teamRows[teamRows.length - 1],
        dev_workforce_strength_hours: totals.devAvailable,
        qa_workforce_strength_hours: totals.qaAvailable,
        workforce_strength_hours: totalAvailable,
        dev_booked_hours: totals.devBooked,
        qa_booked_hours: totals.qaBooked,
        booked_hours: totalBooked,
        dev_utilization_ratio: ratioOrNull(totals.devBooked, totals.devAvailable),
        qa_utilization_ratio: ratioOrNull(totals.qaBooked, totals.qaAvailable),
        utilization_ratio: ratioOrNull(totalBooked, totalAvailable),
      },
    ];
  });
}

function firstScoredRow(rows: HealthRow[]): HealthRow | null {
  return rows.find((row) => row.health_index !== null) ?? null;
}

function delta(start: HealthRow | null | undefined, latest: HealthRow | null | undefined): number | null {
  if (start?.health_index === null || start?.health_index === undefined) return null;
  if (latest?.health_index === null || latest?.health_index === undefined) return null;
  return latest.health_index - start.health_index;
}

function rankedDimensions(row: HealthRow): [ComponentKey, number][] {
  return COMPONENT_KEYS.flatMap((key) => {
    const value = row[key];
    return value === null ? [] : ([[key, value]] as [ComponentKey, number][]);
  }).sort((a, b) => b[1] - a[1]);
}

function componentLabelMap(value: unknown): Record<ComponentKey, string> {
  if (!value || typeof value !== "object") return DEFAULT_COMPONENT_LABELS;
  const raw = value as Record<string, unknown>;
  return {
    flow_efficiency: stringValue(raw.flow_efficiency) ?? DEFAULT_COMPONENT_LABELS.flow_efficiency,
    focus_health: stringValue(raw.focus_health) ?? DEFAULT_COMPONENT_LABELS.focus_health,
    interruption_health: stringValue(raw.interruption_health) ?? DEFAULT_COMPONENT_LABELS.interruption_health,
    execution_predictability: stringValue(raw.execution_predictability) ?? DEFAULT_COMPONENT_LABELS.execution_predictability,
    work_shape_health: stringValue(raw.work_shape_health) ?? DEFAULT_COMPONENT_LABELS.work_shape_health,
  };
}

function weightMap(value: unknown): Record<ComponentKey, number> {
  if (!value || typeof value !== "object") return DEFAULT_WEIGHTS;
  const raw = value as Record<string, unknown>;
  return {
    flow_efficiency: numberValue(raw.flow_efficiency) ?? DEFAULT_WEIGHTS.flow_efficiency,
    focus_health: numberValue(raw.focus_health) ?? DEFAULT_WEIGHTS.focus_health,
    interruption_health: numberValue(raw.interruption_health) ?? DEFAULT_WEIGHTS.interruption_health,
    execution_predictability:
      numberValue(raw.execution_predictability) ?? DEFAULT_WEIGHTS.execution_predictability,
    work_shape_health: numberValue(raw.work_shape_health) ?? DEFAULT_WEIGHTS.work_shape_health,
  };
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function ratioOrNull(numerator: number, denominator: number): number | null {
  return denominator > 0 ? numerator / denominator : null;
}

function formatNullableScore(value: number | null): string {
  return value === null ? "No score" : value.toFixed(1);
}

function formatNumber(value: number | null): string {
  return value === null ? "No data" : value.toFixed(2);
}

function formatHours(value: number | null): string {
  return value === null ? "No data" : `${value.toFixed(1)}h`;
}

function formatPercent(value: number | null): string {
  return value === null ? "No data" : `${(value * 100).toFixed(0)}%`;
}

function formatWeight(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function formatDelta(value: number | null): string {
  if (value === null) return "No data";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}`;
}

function humanizeDrag(value: string | null): string {
  if (!value) return "No data";
  return DEFAULT_COMPONENT_LABELS[value as ComponentKey] ?? value.replaceAll("_", " ");
}

function scoreBandClass(value: number | null): string {
  if (value === null) return "bg-surface-container-high text-on-surface-variant";
  if (value >= 80) return "bg-primary-container text-on-primary-container";
  if (value >= 65) return "bg-tertiary-container text-on-tertiary-container";
  if (value >= 50) return "bg-surface-container-high text-on-surface";
  return "bg-error-container text-on-error-container";
}
