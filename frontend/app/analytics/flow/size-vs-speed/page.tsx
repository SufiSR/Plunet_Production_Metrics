"use client";
import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { FlowMetricCard, FlowReportLayout } from "@/app/components/jira-analytics/FlowReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Size vs speed"
      description="Feature effort size vs active delivery span (worklogs) and lifecycle duration, with hours-per-day intensity."
      apiPath={reportPaths.sizeVsSpeed}
      hiddenColumns={["duration_days"]}
      trendTitle="Size and speed trend"
      trendDescription="Feature effort and delivery speed over time, preserving the chart before the detailed feature comparison table."
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <FlowReportLayout
          activeReport="size-vs-speed"
          title="See whether bigger features slow delivery down."
          description="A size-versus-speed view that compares booked effort with delivery span and intensity, helping separate genuinely large work from slow-moving flow."
          metrics={<SizeVsSpeedMetrics data={data} />}
          controls={controls}
          readingTip="Look for features with high hours and low hours-per-day: they often indicate fragmentation, waiting, or scope that needs decomposition."
        >
          {report}
        </FlowReportLayout>
      )}
    />
  );
}

function SizeVsSpeedMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const rows = data?.table ?? [];
  const totalHours = sum(rows, ["hours", "total_hours"]);
  const avgSpan = average(rows, ["active_delivery_days", "duration_days", "lifecycle_duration_days"]);
  const avgIntensity = average(rows, ["hours_per_day", "intensity"]);

  return (
    <>
      <FlowMetricCard label="Features" value={rows.length ? String(rows.length) : "Loading"} detail="Compared by size and speed" />
      <FlowMetricCard label="Total effort" value={formatHours(totalHours)} detail="Booked feature hours" />
      <FlowMetricCard label="Avg speed" value={formatIntensity(avgIntensity)} detail={`Avg span ${formatDays(avgSpan)}`} />
    </>
  );
}

function sum(rows: Record<string, unknown>[], keys: string[]): number | null {
  let total = 0;
  let found = false;
  for (const row of rows) {
    const value = firstNumber(row, keys);
    if (value !== null) {
      total += value;
      found = true;
    }
  }
  return found ? total : null;
}

function average(rows: Record<string, unknown>[], keys: string[]): number | null {
  const values = rows.flatMap((row) => {
    const value = firstNumber(row, keys);
    return value === null ? [] : [value];
  });
  if (!values.length) return null;
  return values.reduce((sumValue, value) => sumValue + value, 0) / values.length;
}

function firstNumber(row: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function formatHours(value: number | null): string {
  if (value === null) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}

function formatDays(value: number | null): string {
  return value === null ? "Loading" : `${value.toFixed(1)} d`;
}

function formatIntensity(value: number | null): string {
  return value === null ? "Loading" : `${value.toFixed(1)} h/d`;
}
