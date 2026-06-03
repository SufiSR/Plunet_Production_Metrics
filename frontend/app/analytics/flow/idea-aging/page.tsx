"use client";
import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { FlowMetricCard, FlowReportLayout } from "@/app/components/jira-analytics/FlowReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

const EXCLUDED_STATUSES = new Set(["new", "planned", "rejected"]);
const NOT_STARTED_STATUSES = new Set([
  "backlog",
  "idea",
  "open",
  "ready",
  "ready for development",
  "selected for development",
  "to do",
  "todo",
]);

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Idea aging"
      description="Features waiting before implementation starts."
      apiPath={reportPaths.ideaAging}
      hiddenColumns={["date_source", "end_date_source"]}
      rowFilter={(row) => !EXCLUDED_STATUSES.has(statusValue(row))}
      defaultTableSort={compareIdeaAgingRows}
      rowVisibilityToggle={{
        showLabel: "Show not-started issues",
        hideLabel: "Hide not-started issues",
        hiddenRowsLabel: "not-started issues",
        shouldHideByDefault: isNotStartedIssue,
      }}
      teamStats={{
        metricKey: "avg_waiting_days",
        yAxisLabel: "Avg waiting (days)",
        formatChartValue: (value) => `${value.toFixed(2)} d`,
      }}
      trendTitle="Idea aging trend"
      trendDescription="Waiting time by period so intake aging is visible before drilling into individual features."
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <FlowReportLayout
          activeReport="idea-aging"
          title="Find ideas waiting too long before delivery starts."
          description="An intake aging view for spotting feature candidates that are still sitting before active implementation, with rejected and completed noise filtered out."
          metrics={<IdeaAgingMetrics data={data} />}
          controls={controls}
          readingTip="Start with the oldest waiting features, then compare the team trend chart to see whether the problem is broad intake pressure or isolated stuck work."
        >
          {report}
        </FlowReportLayout>
      )}
    />
  );
}

function IdeaAgingMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const rows = (data?.table ?? []).filter((row) => !EXCLUDED_STATUSES.has(statusValue(row)));
  const activeRows = rows.filter((row) => !isNotStartedIssue(row));
  const avgWaiting = average(rows, "waiting_days");
  const oldest = max(rows, "waiting_days");

  return (
    <>
      <FlowMetricCard label="Waiting ideas" value={rows.length ? String(rows.length) : "Loading"} detail="Filtered feature candidates" />
      <FlowMetricCard label="Avg wait" value={formatDays(avgWaiting)} detail="Days before start" />
      <FlowMetricCard label="Oldest wait" value={formatDays(oldest)} detail={`${activeRows.length} already started`} />
    </>
  );
}

function compareIdeaAgingRows(a: Record<string, unknown>, b: Record<string, unknown>): number {
  const statusDiff = statusSortRank(a) - statusSortRank(b);
  if (statusDiff !== 0) return statusDiff;

  const waitingDiff = numberValue(b.waiting_days) - numberValue(a.waiting_days);
  if (waitingDiff !== 0) return waitingDiff;

  return String(a.feature ?? "").localeCompare(String(b.feature ?? ""), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function statusSortRank(row: Record<string, unknown>): number {
  const status = statusValue(row);
  if (status === "done" || status === "closed" || status === "resolved") return 1;
  if (isNotStartedIssue(row)) return 2;
  return 0;
}

function isNotStartedIssue(row: Record<string, unknown>): boolean {
  const status = statusValue(row);
  if (status === "done" || status === "closed" || status === "resolved") return false;
  return String(row.date_source ?? "") === "created_only" || NOT_STARTED_STATUSES.has(status);
}

function statusValue(row: Record<string, unknown>): string {
  return String(row.status ?? "").trim().toLowerCase();
}

function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
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

function hasNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatDays(value: number | null): string {
  return value === null ? "Loading" : `${value.toFixed(1)} d`;
}
