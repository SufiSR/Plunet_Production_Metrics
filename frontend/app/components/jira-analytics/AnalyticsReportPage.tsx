"use client";

import { useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import { AnalyticsFilterPanel, FilterField, filterInputClassName } from "@/app/components/jira-analytics/AnalyticsReportControls";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { AnalyticsReportView } from "@/app/components/jira-analytics/AnalyticsReportView";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import type { TeamStatsConfig } from "@/app/components/jira-analytics/TeamStatsSection";
import { fetchAnalyticsReport } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

interface AnalyticsReportPageProps {
  title: string;
  description: string;
  apiPath: string;
  chartKeys?: string[];
  hiddenColumns?: string[];
  rowFilter?: (row: Record<string, unknown>) => boolean;
  defaultTableSort?: (a: Record<string, unknown>, b: Record<string, unknown>) => number;
  rowVisibilityToggle?: {
    showLabel: string;
    hideLabel: string;
    hiddenRowsLabel: string;
    shouldHideByDefault: (row: Record<string, unknown>) => boolean;
  };
  defaultParams?: ReportQueryParams;
  filters?: {
    timeframe?: boolean;
    team?: boolean;
    project?: boolean;
  };
  /** Shown when the API returns no rows (e.g. allocation not built yet). */
  emptyHint?: string;
  requiresAllocation?: boolean;
  teamStats?: TeamStatsConfig;
  trendEyebrow?: string;
  trendTitle?: string;
  trendDescription?: string;
  detailsEyebrow?: string;
  detailsTitle?: string;
  detailsDescription?: string;
  filterTitle?: string;
  filterDescription?: string;
  reportChrome?: (props: AnalyticsReportPageChromeProps) => ReactNode;
  hidePageHeader?: boolean;
  hideMethodology?: boolean;
}

interface AnalyticsReportPageChromeProps {
  controls: ReactNode;
  report: ReactNode;
  data: AnalyticsReportResponse | null;
  loading: boolean;
  error: string | null;
  empty: boolean;
  params: ReportQueryParams;
  setParams: Dispatch<SetStateAction<ReportQueryParams>>;
}

function hasReportContent(data: AnalyticsReportResponse): boolean {
  if ((data.table?.length ?? 0) > 0) return true;
  if ((data.series?.length ?? 0) > 0) {
    const first = data.series[0];
    if (first && "person" in first && "topics" in first) {
      const topics = first.topics as Record<string, number> | undefined;
      return Boolean(topics && Object.keys(topics).length > 0);
    }
    return true;
  }
  return Object.keys(data.summary ?? {}).length > 0;
}

export function AnalyticsReportPage({
  title,
  description,
  apiPath,
  chartKeys,
  hiddenColumns,
  rowFilter,
  defaultTableSort,
  rowVisibilityToggle,
  defaultParams,
  filters,
  emptyHint,
  requiresAllocation = false,
  teamStats,
  trendEyebrow,
  trendTitle,
  trendDescription,
  detailsEyebrow,
  detailsTitle,
  detailsDescription,
  filterTitle = "Filters",
  filterDescription = "Tune the allocation lens without leaving the report.",
  reportChrome,
  hidePageHeader = false,
  hideMethodology = false,
}: AnalyticsReportPageProps) {
  const [params, setParams] = useState<ReportQueryParams>(defaultParams ?? {});
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [apiPath, params],
    load: (signal) => fetchAnalyticsReport(apiPath, params, signal),
  });

  const empty = Boolean(!loading && !refreshing && !error && data && !hasReportContent(data));
  const emptyMessage =
    emptyHint ??
    (requiresAllocation
      ? "No allocation data yet. Run a Jira analytics sync (or POST /api/jira-analytics/allocation/rebuild) after worklogs and HR hours are loaded."
      : "No data for the selected filters.");
  const availableTeams = stringList(data?.filters?.available_teams);
  const availableProjects = projectList(data?.filters?.available_projects);
  const selectedProjectKeys =
    params.projectKeys ??
    (params.projectKey ? [params.projectKey] : availableProjects.map((project) => project.key));

  const controls = filters ? (
    <AnalyticsFilterPanel
      title={filterTitle}
      description={filterDescription}
    >
      {filters.timeframe ? (
        <>
          <FilterField label="From">
            <input
              type="date"
              value={params.from ?? ""}
              onChange={(event) =>
                setParams((prev) => ({ ...prev, from: event.target.value || undefined }))
              }
              className={filterInputClassName()}
            />
          </FilterField>
          <FilterField label="To">
            <input
              type="date"
              value={params.to ?? ""}
              onChange={(event) =>
                setParams((prev) => ({ ...prev, to: event.target.value || undefined }))
              }
              className={filterInputClassName()}
            />
          </FilterField>
        </>
      ) : null}
      {filters.project ? (
        <FilterField
          label="Jira projects"
          hint={
            selectedProjectKeys.length === availableProjects.length
              ? "All projects selected"
              : `${selectedProjectKeys.length} of ${availableProjects.length} selected`
          }
          className="min-w-[17rem]"
        >
          <select
            multiple
            size={Math.min(Math.max(availableProjects.length, 3), 6)}
            value={selectedProjectKeys}
            onChange={(event) => {
              const projectKeys = Array.from(event.target.selectedOptions, (option) => option.value);
              const nextProjectKeys =
                projectKeys.length === 0 || projectKeys.length === availableProjects.length
                  ? undefined
                  : projectKeys;
              setParams((prev) => ({
                ...prev,
                projectKey: undefined,
                projectKeys: nextProjectKeys,
              }));
            }}
            className={filterInputClassName("h-auto min-h-[7rem]")}
          >
            {availableProjects.map((project) => (
              <option key={project.key} value={project.key}>
                {project.name ? `${project.key} - ${project.name}` : project.key}
              </option>
            ))}
          </select>
        </FilterField>
      ) : null}
      {filters.team ? (
        <FilterField label="Team" className="min-w-[14rem]">
          <select
            value={params.team ?? ""}
            onChange={(event) =>
              setParams((prev) => ({ ...prev, team: event.target.value || undefined }))
            }
            className={filterInputClassName()}
          >
            <option value="">All teams</option>
            {availableTeams.map((team) => (
              <option key={team} value={team}>
                {team}
              </option>
            ))}
          </select>
        </FilterField>
      ) : null}
    </AnalyticsFilterPanel>
  ) : null;

  const report = (
    <ReportPageFrame
      loading={loading}
      refreshing={refreshing}
      error={error}
      empty={empty}
      emptyMessage={emptyMessage}
      slowLoading={slowLoading}
      elapsedSeconds={elapsedSeconds}
      onRetry={retry}
    >
      {data ? (
        <AnalyticsReportView
          data={data}
          chartKeys={chartKeys}
          hiddenColumns={hiddenColumns}
          rowFilter={rowFilter}
          defaultTableSort={defaultTableSort}
          rowVisibilityToggle={rowVisibilityToggle}
          teamStats={teamStats}
          trendEyebrow={trendEyebrow}
          trendTitle={trendTitle}
          trendDescription={trendDescription}
          detailsEyebrow={detailsEyebrow}
          detailsTitle={detailsTitle}
          detailsDescription={detailsDescription}
        />
      ) : null}
    </ReportPageFrame>
  );

  return (
    <JiraAnalyticsShell
      title={title}
      description={description}
      hidePageHeader={hidePageHeader}
      hideMethodology={hideMethodology}
    >
      {reportChrome
        ? reportChrome({ controls, report, data, loading, error, empty, params, setParams })
        : (
          <>
            {controls}
            {report}
          </>
        )}
    </JiraAnalyticsShell>
  );
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function projectList(value: unknown): { key: string; name?: string | null }[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const project = item as { key?: unknown; name?: unknown };
    if (typeof project.key !== "string" || !project.key) return [];
    return [{ key: project.key, name: typeof project.name === "string" ? project.name : null }];
  });
}
