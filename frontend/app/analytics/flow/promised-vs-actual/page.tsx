"use client";

import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { FlowMetricCard, FlowReportLayout } from "@/app/components/jira-analytics/FlowReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Promised vs actual delivery"
      description="Roadmap promise dates compared to actual delivery."
      apiPath={reportPaths.promisedVsActual}
      teamStats={{
        metricKey: "avg_delay_days",
        yAxisLabel: "Avg delay (days)",
        formatChartValue: (value) => `${value.toFixed(2)} d`,
      }}
      trendTitle="Delivery delay trend"
      trendDescription="Promised dates compared with actual delivery so slippage patterns are visible over time."
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <FlowReportLayout
          activeReport="promised-vs-actual"
          title="Compare roadmap promises with actual delivery."
          description="A commitment accuracy view that shows whether promised feature dates match the real delivery timeline and which items drove delays."
          metrics={<PromisedVsActualMetrics data={data} />}
          controls={controls}
          readingTip="Positive delay means delivery landed after the promise date. Use the chart for the direction of travel, then open the table rows with the largest delays."
        >
          {report}
        </FlowReportLayout>
      )}
    />
  );
}

function PromisedVsActualMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const rows = data?.table ?? [];
  const delayedRows = rows.filter((row) => numberValue(row.delay_days) > 0);
  const avgDelay = average(rows, "delay_days");
  const worstDelay = max(rows, "delay_days");

  return (
    <>
      <FlowMetricCard label="Promises" value={rows.length ? String(rows.length) : "Loading"} detail="Committed features in scope" />
      <FlowMetricCard label="Avg delay" value={formatDays(avgDelay)} detail="Actual minus promised" />
      <FlowMetricCard label="Delayed" value={rows.length ? String(delayedRows.length) : "Loading"} detail={`Worst delay ${formatDays(worstDelay)}`} />
    </>
  );
}

function average(rows: Record<string, unknown>[], key: string): number | null {
  const values = rows.map((row) => row[key]).filter(hasNumber);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function max(rows: Record<string, unknown>[], key: string): number | null {
  const values = rows.map((row) => row[key]).filter(hasNumber);
  return values.length ? Math.max(...values) : null;
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function hasNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatDays(value: number | null): string {
  return value === null ? "Loading" : `${value.toFixed(1)} d`;
}

