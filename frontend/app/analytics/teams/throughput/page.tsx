"use client";

import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { lastTwelveMonths } from "@/lib/jira-analytics-dates";
import { reportPaths } from "@/lib/jira-analytics-api";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

const copy = TEAM_PAGE_COPY.throughput;
const EXCLUDED_TEAMS = new Set(["unknown", "legacy"]);

function isExcludedThroughputTeam(row: Record<string, unknown>): boolean {
  return EXCLUDED_TEAMS.has(String(row.team ?? "").trim().toLowerCase());
}

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Throughput stability"
      description="Resolved issues per week and predictability score."
      apiPath={reportPaths.throughput}
      defaultParams={lastTwelveMonths()}
      rowFilter={(row) => !isExcludedThroughputTeam(row)}
      filters={{ timeframe: true, team: true }}
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <TeamReportLayout
          activeReport="throughput"
          title={copy.heroTitle}
          description={copy.heroDescription}
          readingTip={copy.readingTip}
          metrics={<ThroughputMetrics data={data} />}
          controls={controls}
        >
          {report}
        </TeamReportLayout>
      )}
    />
  );
}

function ThroughputMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const visibleRows = (data?.table ?? []).filter((row) => !isExcludedThroughputTeam(row));
  const rows = visibleRows.length;
  const avgPredictability = averageNumber(visibleRows, "predictability");
  const teams = new Set(visibleRows.map((row) => String(row.team ?? "")).filter(Boolean)).size;

  return (
    <>
      <TeamMetricCard label="Team rows" value={rows ? String(rows) : "Loading"} detail="In selected period" />
      <TeamMetricCard label="Avg predictability" value={formatPercent(avgPredictability)} detail="Across series periods" />
      <TeamMetricCard label="Teams" value={teams ? String(teams) : "Loading"} detail="With throughput data" />
    </>
  );
}

function averageNumber(rows: Record<string, unknown>[] | undefined, key: string): number | null {
  const values = (rows ?? [])
    .map((row) => (typeof row[key] === "number" && Number.isFinite(row[key]) ? row[key] : null))
    .filter((value): value is number => value !== null);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatPercent(value: number | null): string {
  if (value === null) return "Loading";
  return `${Math.round(value * 100)}%`;
}
