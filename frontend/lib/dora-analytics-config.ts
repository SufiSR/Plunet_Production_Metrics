import type { TrendOverviewMetric } from "@/lib/store";

export type DoraReportId =
  | "overview"
  | "deployment-frequency"
  | "lead-time"
  | "change-failure-rate"
  | "mttr-alpha";

export interface DoraReportDefinition {
  id: DoraReportId;
  href: string;
  title: string;
  question: string;
  description: string;
  detail: string;
  metricKey: TrendOverviewMetric | null;
  icon: string;
}

export const DORA_REPORTS: DoraReportDefinition[] = [
  {
    id: "overview",
    href: "/analytics/dora",
    title: "DORA overview",
    question: "How are the four DORA metrics performing right now?",
    description:
      "Current deployment frequency, lead time, change failure rate, and MTTR Alpha — the same KPIs as the home dashboard, organized for analytics navigation.",
    detail: "Summary cards for all four core metrics with links to trend and drilldown views.",
    metricKey: null,
    icon: "dashboard",
  },
  {
    id: "deployment-frequency",
    href: "/analytics/dora/deployment-frequency",
    title: "Deployment frequency",
    question: "How often do customer releases ship?",
    description:
      "Weekly customer-release cadence with a deployment swimlane timeline showing release events by version lane.",
    detail: "Trend series plus release swimlane drilldown.",
    metricKey: "deployment_frequency",
    icon: "rocket_launch",
  },
  {
    id: "lead-time",
    href: "/analytics/dora/lead-time",
    title: "Median lead time",
    question: "How long from commit to customer release?",
    description:
      "Median lead time with dev/review vs release-wait breakdown, branch/stream disaggregation, and per-release drilldown.",
    detail: "Stacked lead-time trend with release-level context.",
    metricKey: "lead_time_for_changes",
    icon: "schedule",
  },
  {
    id: "change-failure-rate",
    href: "/analytics/dora/change-failure-rate",
    title: "Change failure rate",
    question: "What share of releases introduced production issues?",
    description:
      "Percentage of customer releases linked to production bugs, with drilldown to failed releases and linked issues.",
    detail: "CFR trend plus failed-release drilldown.",
    metricKey: "change_failure_rate",
    icon: "emergency",
  },
  {
    id: "mttr-alpha",
    href: "/analytics/dora/mttr-alpha",
    title: "MTTR Alpha",
    question: "How fast do we restore service after production failures?",
    description:
      "Median time from bug creation to the first customer release containing the fix, with time-to-fix spread and incident drilldown.",
    detail: "Recovery trend plus incident and fix-release drilldown.",
    metricKey: "mttr_alpha",
    icon: "history",
  },
];

export const DORA_REPORTS_BY_ID = Object.fromEntries(
  DORA_REPORTS.map((report) => [report.id, report]),
) as Record<DoraReportId, DoraReportDefinition>;

export const DORA_METRIC_REPORTS = DORA_REPORTS.filter(
  (report): report is DoraReportDefinition & { metricKey: TrendOverviewMetric } =>
    report.metricKey !== null,
);

export function doraReportForPath(pathname: string): DoraReportDefinition | undefined {
  const normalized = pathname.replace(/\/$/, "") || "/";
  return DORA_REPORTS.find(
    (report) => normalized === report.href || normalized.startsWith(`${report.href}/`),
  );
}
