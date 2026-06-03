"use client";

import { AnalyticsReportPage } from "@/app/components/jira-analytics/AnalyticsReportPage";
import { InvestmentMetricCard, InvestmentReportLayout } from "@/app/components/jira-analytics/InvestmentReportLayout";
import { reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

const CHART_KEYS = [
  "feature",
  "support",
  "bugs_without_feature",
  "small_improvements",
  "shared_overhead",
  "unclassified",
];

export default function Page() {
  return (
    <AnalyticsReportPage
      title="Investment categories"
      description="Monthly capacity split by investment category (feature, support, bugs, small improvements, overhead)."
      apiPath={reportPaths.investmentCategory}
      chartKeys={CHART_KEYS}
      defaultParams={pastThreeYearsRange()}
      filters={{ timeframe: true, team: true }}
      requiresAllocation
      hidePageHeader
      hideMethodology
      reportChrome={({ controls, report, data }) => (
        <InvestmentReportLayout
          activeReport="categories"
          title="See where capacity actually went."
          description="A portfolio mix view that turns allocation data into a clean monthly story across feature work, support, bugs, improvements, shared overhead, and unclassified effort."
          metrics={<CategoryMetrics data={data} />}
          controls={controls}
        >
          {report}
        </InvestmentReportLayout>
      )}
    />
  );
}

function CategoryMetrics({ data }: { data: AnalyticsReportResponse | null }) {
  const totalHours = totalSeriesHours(data, CHART_KEYS);
  const periods = new Set((data?.series ?? []).map((row) => String(row.period ?? "")).filter(Boolean)).size;
  const categories = CHART_KEYS.length;

  return (
    <>
      <InvestmentMetricCard label="Allocated hours" value={formatCompactHours(totalHours)} detail="Across selected filters" />
      <InvestmentMetricCard label="Periods" value={periods ? String(periods) : "Loading"} detail="Monthly buckets in view" />
      <InvestmentMetricCard label="Categories" value={String(categories)} detail="Portfolio slices compared" />
    </>
  );
}

function pastThreeYearsRange() {
  const today = new Date();
  const from = new Date(today);
  from.setFullYear(today.getFullYear() - 3);
  return {
    from: formatDateInput(from),
    to: formatDateInput(today),
  };
}

function formatDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function totalSeriesHours(data: AnalyticsReportResponse | null, keys: string[]): number {
  return (data?.series ?? []).reduce((sum, row) => {
    return sum + keys.reduce((innerSum, key) => innerSum + numberValue(row[key]), 0);
  }, 0);
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}
