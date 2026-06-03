"use client";

import { useMemo, useState } from "react";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { TeamMetricCard, TeamReportLayout } from "@/app/components/jira-analytics/TeamReportLayout";
import { WorkAllocationHeatmapView } from "@/app/components/jira-analytics/WorkAllocationHeatmapView";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { lastTwelveMonths } from "@/lib/jira-analytics-dates";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { TEAM_PAGE_COPY } from "@/lib/jira-analytics-team-pages";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

const copy = TEAM_PAGE_COPY.heatmap;

export default function Page() {
  const defaultRange = useMemo(() => lastTwelveMonths(), []);
  const [params, setParams] = useState<ReportQueryParams>(defaultRange);
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [params],
    load: (signal) => fetchAnalyticsReport(reportPaths.heatmap, params, signal),
  });

  const teamCount = (data?.series ?? []).length;
  const topicCount = (data?.table ?? []).length;
  const totalHours = useMemo(() => sumHeatmapHours(data), [data]);
  const empty = Boolean(!loading && !refreshing && !error && data && !hasHeatmapContent(data));

  return (
    <JiraAnalyticsShell title="Work allocation heatmap" description="" hidePageHeader hideMethodology>
      <TeamReportLayout
        activeReport="heatmap"
        title={copy.heroTitle}
        description={copy.heroDescription}
        readingTip={copy.readingTip}
        metrics={
          <>
            <TeamMetricCard label="Teams" value={teamCount ? String(teamCount) : "Loading"} detail="Developer and QA rows" />
            <TeamMetricCard label="Topic rows" value={topicCount ? String(topicCount) : "Loading"} detail="Allocated topic slices" />
            <TeamMetricCard label="Allocated hours" value={formatCompactHours(totalHours)} detail="In selected period" />
          </>
        }
        controls={
          <AnalyticsFilterPanel
            title="Period"
            description="Includes developers and QA only; teams come from user assignments."
          >
            <FilterField label="From">
              <input
                type="date"
                value={params.from ?? ""}
                onChange={(event) => setParams((prev) => ({ ...prev, from: event.target.value || undefined }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="To">
              <input
                type="date"
                value={params.to ?? ""}
                onChange={(event) => setParams((prev) => ({ ...prev, to: event.target.value || undefined }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <div className="self-end">
              <button
                type="button"
                onClick={() => setParams(lastTwelveMonths())}
                className="h-11 rounded-xl border border-outline-variant/40 px-4 text-sm font-semibold text-on-surface hover:bg-surface-container-high"
              >
                Last 12 months
              </button>
            </div>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage="No allocation data for developers or QA in the selected period. Run a Jira analytics sync and allocation rebuild if needed."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
          {data ? (
            <ModernReportCard
              eyebrow="Allocation map"
              title="Team → topic → person"
              description="Allocated hours from the monthly rebuild, filtered to Developer and QA roles."
            >
              <WorkAllocationHeatmapView data={data} />
            </ModernReportCard>
          ) : null}
        </ReportPageFrame>
      </TeamReportLayout>
    </JiraAnalyticsShell>
  );
}

function hasHeatmapContent(data: AnalyticsReportResponse): boolean {
  if ((data.table?.length ?? 0) > 0) return true;
  return (data.series?.length ?? 0) > 0;
}

function sumHeatmapHours(data: AnalyticsReportResponse | null): number {
  return (data?.table ?? []).reduce((sum, row) => sum + numberValue(row.hours), 0);
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}
