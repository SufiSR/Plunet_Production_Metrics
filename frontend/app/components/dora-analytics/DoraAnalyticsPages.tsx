"use client";

import { CfrReleaseDrilldownPanel } from "@/app/components/dashboard/CfrReleaseDrilldownPanel";
import { DeploymentSwimlaneTimeline } from "@/app/components/dashboard/DeploymentSwimlaneTimeline";
import { MetricModal } from "@/app/components/dashboard/MetricModal";
import { MttrAlphaDrilldownPanel } from "@/app/components/dashboard/MttrAlphaDrilldownPanel";
import { MttrAlphaTimeToFixSpread } from "@/app/components/dashboard/MttrAlphaTimeToFixSpread";
import { ReleaseDrilldownPanel } from "@/app/components/dashboard/ReleaseDrilldownPanel";
import { TrendChart } from "@/app/components/dashboard/TrendChart";
import { DoraReportLayout } from "@/app/components/dora-analytics/DoraReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { DORA_REPORTS_BY_ID, type DoraReportId } from "@/lib/dora-analytics-config";
import type { TrendOverviewMetric } from "@/lib/store";

function DoraDrilldownPanels({ metricKey }: { metricKey: TrendOverviewMetric }) {
  switch (metricKey) {
    case "deployment_frequency":
      return <DeploymentSwimlaneTimeline />;
    case "lead_time_for_changes":
      return <ReleaseDrilldownPanel />;
    case "change_failure_rate":
      return <CfrReleaseDrilldownPanel />;
    case "mttr_alpha":
      return (
        <>
          <MttrAlphaTimeToFixSpread />
          <MttrAlphaDrilldownPanel />
        </>
      );
    default:
      return null;
  }
}

export function DoraOverviewPage() {
  const report = DORA_REPORTS_BY_ID.overview;

  return (
    <JiraAnalyticsShell title={report.title} description={report.description} hidePageHeader hideMethodology>
      <DoraReportLayout activeReport="overview" title={report.title} description={report.description} />
      <MetricModal />
    </JiraAnalyticsShell>
  );
}

export function DoraMetricPage({ reportId }: { reportId: Exclude<DoraReportId, "overview"> }) {
  const report = DORA_REPORTS_BY_ID[reportId];
  const metricKey = report.metricKey!;

  return (
    <JiraAnalyticsShell title={report.title} description={report.description} hidePageHeader hideMethodology>
      <DoraReportLayout activeReport={reportId} title={report.title} description={report.description}>
        <TrendChart compact fixedMetric={metricKey} headingTitle="Trend" />
        <DoraDrilldownPanels metricKey={metricKey} />
      </DoraReportLayout>
      <MetricModal />
    </JiraAnalyticsShell>
  );
}
