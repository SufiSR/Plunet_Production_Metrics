"use client";
import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { FlowMetricCard, FlowReportLayout } from "@/app/components/jira-analytics/FlowReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Feature lifecycle"
      description="Phase durations from idea to completion."
      apiPath={reportPaths.lifecycle}
      hiddenColumns={["date_source", "end_date_source"]}
      rowVisibilityToggle={{
        showLabel: "Show non-started projects",
        hideLabel: "Hide non-started projects",
        hiddenRowsLabel: "non-started projects",
        shouldHideByDefault: (row) => row.idea_to_start_days === null || row.idea_to_start_days === undefined,
      }}
      trendTitle="Lifecycle duration trend"
      trendDescription="Monthly flow timing so changes in idea, start, production, and completion spans stay visible before reviewing the table."
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <FlowReportLayout
          activeReport="lifecycle"
          title="Follow features from idea to done."
          description="A lifecycle funnel view that shows where features spend time before they reach completion, with non-started work hidden by default to keep the active flow readable."
          metrics={<LifecycleMetrics data={data} />}
          controls={controls}
          readingTip="Use this as the starting point for flow diagnosis: long idea-to-start times point to intake pressure, while long production or completion spans point to delivery execution."
        >
          {report}
        </FlowReportLayout>
      )}
    />
  );
}

function LifecycleMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const rows = data?.table ?? [];
  const completedRows = rows.filter((row) => hasNumber(row.idea_to_done_days) || hasNumber(row.lifecycle_duration_days));
  const avgLifecycle = average(rows, ["idea_to_done_days", "lifecycle_duration_days"]);
  const notStarted = rows.filter((row) => row.idea_to_start_days === null || row.idea_to_start_days === undefined).length;

  return (
    <>
      <FlowMetricCard label="Features" value={rows.length ? String(rows.length) : "Loading"} detail="Feature rows in scope" />
      <FlowMetricCard label="Avg lifecycle" value={formatDays(avgLifecycle)} detail="Idea to done where available" />
      <FlowMetricCard label="Not started" value={rows.length ? String(notStarted) : "Loading"} detail={`${completedRows.length} with completion timing`} />
    </>
  );
}

function average(rows: Record<string, unknown>[], keys: string[]): number | null {
  const values = rows.flatMap((row) => {
    const value = firstNumber(row, keys);
    return value === null ? [] : [value];
  });
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function firstNumber(row: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = row[key];
    if (hasNumber(value)) return value;
  }
  return null;
}

function hasNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatDays(value: number | null): string {
  return value === null ? "Loading" : `${value.toFixed(1)} d`;
}
