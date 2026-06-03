"use client";

import { useMemo } from "react";
import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import {
  BottleneckMetricCard,
  BottleneckReportLayout,
} from "@/app/components/jira-analytics/BottleneckReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

function defaultDateRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setFullYear(from.getFullYear() - 1);
  return { from: formatIsoDate(from), to: formatIsoDate(to) };
}

function formatIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function Page() {
  const defaultRange = useMemo(() => defaultDateRange(), []);

  return (
    <AnalyticsReportPage
      title="Workflow thrashing"
      description="Issues with excessive status changes and reopens."
      apiPath={reportPaths.thrashing}
      defaultParams={{
        minScore: 3,
        from: defaultRange.from,
        to: defaultRange.to,
      }}
      filters={{ timeframe: true }}
      filterTitle="Date filters"
      filterDescription="Choose the status-transition window used for churn, reopen, and ping-pong scoring."
      trendEyebrow="Churn trend"
      trendTitle="Workflow thrash over time"
      trendDescription="Status churn and reopen pressure over the selected period before opening the issue-level table."
      detailsEyebrow="Issue evidence"
      detailsTitle="Thrashing candidates"
      detailsDescription="Sortable issue rows showing status changes, reopens, ping-pong movement, and the combined thrash score."
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <BottleneckReportLayout
          activeReport="thrashing"
          title="Find tickets bouncing through the workflow."
          description="A status-churn report for issues with repeated transitions, reopens, and ping-pong movement that can hide rework or unclear ownership."
          metrics={<ThrashingMetrics data={data} />}
          controls={controls}
          readingTip="Start with high scores and reopens, then inspect ping-pong counts to separate ordinary long-running work from tickets that repeatedly move backward."
        >
          {report}
        </BottleneckReportLayout>
      )}
    />
  );
}

function ThrashingMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const rows = data?.table ?? [];
  const highThrashRows = rows.filter((row) => numberValue(row.thrash_score) >= 10);
  const scores = rows.map((row) => numberValue(row.thrash_score)).filter((value) => value > 0);
  const maxScore = scores.length ? Math.max(...scores) : null;
  const avgScore = scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null;

  return (
    <>
      <BottleneckMetricCard label="Issues" value={rows.length ? String(rows.length) : "Loading"} detail="Above the selected score threshold" />
      <BottleneckMetricCard label="High thrash" value={rows.length ? String(highThrashRows.length) : "Loading"} detail="Thrash score >= 10" />
      <BottleneckMetricCard label="Score range" value={maxScore === null ? "Loading" : maxScore.toFixed(0)} detail={avgScore === null ? "Max and average score" : `${avgScore.toFixed(1)} average`} />
    </>
  );
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
