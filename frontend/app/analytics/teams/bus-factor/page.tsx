"use client";

import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

const copy = TEAM_PAGE_COPY["bus-factor"];

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Bus factor"
      description="Single-contributor dependency risk (direct worklogs only)."
      apiPath={reportPaths.busFactor}
      filters={{ timeframe: true, team: true }}
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data, loading }) => (
        <TeamReportLayout
          activeReport="bus-factor"
          title={copy.heroTitle}
          description={copy.heroDescription}
          readingTip={copy.readingTip}
          metrics={<BusFactorMetrics data={data} loading={loading} />}
          controls={controls}
        >
          {report}
        </TeamReportLayout>
      )}
    />
  );
}

function BusFactorMetrics({
  data,
  loading,
}: {
  data: AnalyticsReportResponse | null;
  loading: boolean;
}) {
  const table = data?.table ?? [];
  const rows = table.length;
  const highRisk = table.filter((row) => Number(row.share ?? 0) >= 0.7).length;
  const features = new Set(
    table.map((row) => String(row.feature_key ?? "").trim()).filter(Boolean),
  ).size;
  const metricValue = (value: number) => (loading ? "Loading" : String(value));

  return (
    <>
      <TeamMetricCard label="Risk rows" value={metricValue(rows)} detail="Features in the table" />
      <TeamMetricCard label="High concentration" value={metricValue(highRisk)} detail="Share ≥ 70%" />
      <TeamMetricCard label="Features" value={metricValue(features)} detail="Distinct PMGT features" />
    </>
  );
}
