"use client";

import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { FlowMetricCard, FlowReportLayout } from "@/app/components/jira-analytics/FlowReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Roadmap reliability"
      description="On-time delivery rate for promised features."
      apiPath={reportPaths.roadmapReliability}
      teamStats={{
        metricKey: "reliability",
        yAxisLabel: "Reliability",
        yDomain: [0, 1],
        formatChartValue: (value) => `${(value * 100).toFixed(2)}%`,
        showSummaryYearNote: true,
      }}
      trendTitle="Roadmap reliability trend"
      trendDescription="On-time delivery rate over time so commitment health is visible before reviewing the detailed rows."
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <FlowReportLayout
          activeReport="roadmap-reliability"
          title="Measure whether roadmap commitments are dependable."
          description="A reliability view for promised features that separates the on-time delivery rate from individual misses, delays, and commitment patterns."
          metrics={<RoadmapReliabilityMetrics data={data} />}
          controls={controls}
          readingTip="Use the reliability percentage as the headline signal, then inspect delayed or missed rows to understand whether the issue is estimation, dependency risk, or priority change."
        >
          {report}
        </FlowReportLayout>
      )}
    />
  );
}

function RoadmapReliabilityMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const rows = data?.table ?? [];
  const reliability = summaryNumber(data, "reliability") ?? average(rows, "reliability");
  const promised = summaryNumber(data, "promised_count") ?? rows.length;
  const delayed = rows.filter((row) => numberValue(row.delay_days) > 0 || String(row.delivery_status ?? "").toLowerCase().includes("late")).length;

  return (
    <>
      <FlowMetricCard label="Reliability" value={formatPercent(reliability)} detail="On-time delivery rate" />
      <FlowMetricCard label="Promises" value={promised ? String(promised) : "Loading"} detail="Committed features measured" />
      <FlowMetricCard label="Delayed" value={rows.length ? String(delayed) : "Loading"} detail="Rows that need follow-up" />
    </>
  );
}

function summaryNumber(data: AnalyticsReportResponse | null, key: string): number | null {
  const value = data?.summary?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function average(rows: Record<string, unknown>[], key: string): number | null {
  const values = rows.map((row) => row[key]).filter(hasNumber);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function hasNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatPercent(value: number | null): string {
  return value === null ? "Loading" : `${(value * 100).toFixed(1)}%`;
}

