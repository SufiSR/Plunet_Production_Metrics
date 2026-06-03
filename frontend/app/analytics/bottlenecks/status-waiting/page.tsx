"use client";

import { useEffect, useMemo, useState } from "react";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
  SegmentToggle,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import {
  BottleneckMetricCard,
  BottleneckReportLayout,
} from "@/app/components/jira-analytics/BottleneckReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ProjectCheckboxDropdown } from "@/app/components/jira-analytics/ProjectCheckboxDropdown";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { StatusWaitingReportView } from "@/app/components/jira-analytics/StatusWaitingReportView";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { MAIN_DELIVERY_WORKFLOWS } from "@/lib/jira-analytics-workflows";
import { sortMainDeliveryWorkflowSections } from "@/lib/sort-main-delivery-workflows";
import type {
  AnalyticsReportResponse,
  ReportQueryParams,
  StatusWaitingDataPoint,
  StatusWaitingPriorityRow,
  StatusWaitingWorkflowSection,
} from "@/types/jira-analytics";

interface StatusWaitingFilters {
  from: string;
  to: string;
  projectKeys: string[] | null;
  includeOtherWorkflows: boolean;
}

type StatusWaitingStatistic = "median" | "average";

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

function toQueryParams(
  filters: StatusWaitingFilters,
  allProjectKeys: string[],
): ReportQueryParams {
  const projectKeys =
    filters.projectKeys === null
      ? allProjectKeys
      : filters.projectKeys.length > 0
        ? filters.projectKeys
        : [];
  return {
    from: filters.from,
    to: filters.to,
    projectKeys: projectKeys.length > 0 ? projectKeys : undefined,
    includeOtherWorkflows: filters.includeOtherWorkflows,
  };
}

export default function StatusWaitingPage() {
  const initialRange = useMemo(() => defaultDateRange(), []);
  const [draftFilters, setDraftFilters] = useState<StatusWaitingFilters>({
    from: initialRange.from,
    to: initialRange.to,
    projectKeys: null,
    includeOtherWorkflows: false,
  });
  const [statistic, setStatistic] = useState<StatusWaitingStatistic>("median");
  const [queryParams, setQueryParams] = useState<ReportQueryParams>({
    from: initialRange.from,
    to: initialRange.to,
    includeOtherWorkflows: false,
  });
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [queryParams],
    load: (signal) => fetchAnalyticsReport(reportPaths.statusWaiting, queryParams, signal),
  });

  const availableProjects = projectList(data?.filters?.available_projects);
  const mainWorkflows = sortMainDeliveryWorkflowSections(
    parseWorkflowSections(data?.filters?.main_workflows, true),
  );
  const otherWorkflows = parseWorkflowSections(data?.filters?.other_workflows, false);

  useEffect(() => {
    if (availableProjects.length === 0) return;
    if (queryParams.projectKeys !== undefined) return;
    setQueryParams(
      toQueryParams(
        {
          ...draftFilters,
          from: String(queryParams.from ?? draftFilters.from),
          to: String(queryParams.to ?? draftFilters.to),
          projectKeys: null,
        },
        availableProjects.map((project) => project.key),
      ),
    );
  }, [availableProjects, draftFilters, queryParams]);

  const showOtherWorkflows = draftFilters.includeOtherWorkflows;
  const hasRows =
    mainWorkflows.some((workflow) => (workflow.data_points?.length ?? 0) > 0) ||
    (showOtherWorkflows && otherWorkflows.some((workflow) => workflow.rows.length > 0));
  const empty = !loading && !refreshing && !error && !hasRows;
  const workflowsSynced = data?.filters?.workflows_synced === true;
  const emptyMessage = !workflowsSynced
    ? "Jira workflow definitions are not loaded yet. Run workflow sync to import workflows."
    : "No status waiting data for the selected filters.";

  const applyFilters = () => {
    setQueryParams(
      toQueryParams(
        draftFilters,
        availableProjects.map((project) => project.key),
      ),
    );
  };

  return (
    <JiraAnalyticsShell
      title="Status waiting time"
      description="Days in each workflow status, broken down by issue priority."
      hidePageHeader
      hideMethodology
    >
      <BottleneckReportLayout
        activeReport="status-waiting"
        title="Find the workflow statuses where work waits."
        description="A priority-aware view of status dwell time across the delivery workflows, so queues and blocked states stand out before they become delivery commitments."
        mainWorkflowLineage={MAIN_DELIVERY_WORKFLOWS.map((workflow) => ({
          label: workflow.label,
          purpose: workflow.purpose,
          issueTypes: workflow.issueTypes,
        }))}
        metrics={
          <StatusWaitingMetrics
            mainWorkflows={mainWorkflows}
            otherWorkflows={otherWorkflows}
            showOtherWorkflows={showOtherWorkflows}
            statistic={statistic}
            from={String(queryParams.from ?? draftFilters.from)}
            to={String(queryParams.to ?? draftFilters.to)}
          />
        }
        controls={
          <AnalyticsFilterPanel title="Global filters" description="Choose the status interval window, project scope, workflow set, and statistic shown in priority columns.">
            <FilterField label="From">
              <input
                type="date"
                value={draftFilters.from}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, from: event.target.value }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="To">
              <input
                type="date"
                value={draftFilters.to}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, to: event.target.value }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <ProjectCheckboxDropdown
              projects={availableProjects}
              selectedKeys={draftFilters.projectKeys}
              onChange={(projectKeys) => setDraftFilters((prev) => ({ ...prev, projectKeys }))}
              disabled={loading && !availableProjects.length}
            />
            <label className="flex h-11 cursor-pointer items-center gap-2 self-end rounded-xl border border-outline-variant/30 bg-surface px-3 text-sm font-medium text-on-surface shadow-sm">
              <input
                type="checkbox"
                checked={draftFilters.includeOtherWorkflows}
                onChange={(event) =>
                  setDraftFilters((prev) => ({
                    ...prev,
                    includeOtherWorkflows: event.target.checked,
                  }))
                }
                className="size-4 rounded border-outline-variant/50"
              />
              Other workflows
            </label>
            <div className="self-end">
              <SegmentToggle
                value={statistic}
                options={[
                  { value: "median", label: "Median" },
                  { value: "average", label: "Average" },
                ]}
                onChange={setStatistic}
              />
            </div>
            <div className="flex gap-2 self-end">
              <button
                type="button"
                onClick={applyFilters}
                disabled={loading}
                className="h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={() => {
                  const range = defaultDateRange();
                  setDraftFilters({
                    from: range.from,
                    to: range.to,
                    projectKeys: null,
                    includeOtherWorkflows: false,
                  });
                }}
                className="h-11 rounded-xl border border-outline-variant/40 px-4 text-sm font-semibold text-on-surface hover:bg-surface-container-high"
              >
                Last 12 months
              </button>
            </div>
          </AnalyticsFilterPanel>
        }
        readingTip="Start with the longest median waits in main workflows, then switch to average when you want outliers to influence the signal. Add other workflows only when diagnosing specialist queues."
      >
        <ReportPageFrame
          loading={loading}
          refreshing={refreshing}
          error={error}
          empty={empty}
          emptyMessage={emptyMessage}
          loadingTitle="Building status waiting report"
          loadingHint="Computing median and average dwell times from Jira status history."
          slowLoading={slowLoading}
          elapsedSeconds={elapsedSeconds}
          onRetry={retry}
        >
          <StatusWaitingReportView
            mainWorkflows={mainWorkflows}
            otherWorkflows={otherWorkflows}
            showOtherWorkflows={showOtherWorkflows}
            statistic={statistic}
          />
        </ReportPageFrame>
      </BottleneckReportLayout>
    </JiraAnalyticsShell>
  );
}

function StatusWaitingMetrics({
  mainWorkflows,
  otherWorkflows,
  showOtherWorkflows,
  statistic,
  from,
  to,
}: {
  mainWorkflows: StatusWaitingWorkflowSection[];
  otherWorkflows: StatusWaitingWorkflowSection[];
  showOtherWorkflows: boolean;
  statistic: StatusWaitingStatistic;
  from: string;
  to: string;
}) {
  const visibleWorkflows = showOtherWorkflows ? [...mainWorkflows, ...otherWorkflows] : mainWorkflows;
  const statusCount = visibleWorkflows.reduce((sum, workflow) => sum + statusCountForWorkflow(workflow), 0);
  const issueCount = visibleWorkflows.reduce((sum, workflow) => sum + issueCountForWorkflow(workflow), 0);

  return (
    <>
      <BottleneckMetricCard label="Workflows" value={visibleWorkflows.length ? String(visibleWorkflows.length) : "Loading"} detail={showOtherWorkflows ? "Main + specialist workflows" : "Main delivery workflows"} />
      <BottleneckMetricCard label="Statuses" value={statusCount ? String(statusCount) : "Loading"} detail={`${issueCount || 0} status visits counted`} />
      <BottleneckMetricCard label="Statistic" value={statistic === "average" ? "Average" : "Median"} detail={`${from} to ${to}`} />
    </>
  );
}

function statusCountForWorkflow(workflow: StatusWaitingWorkflowSection): number {
  if (workflow.rows.length > 0) return workflow.rows.length;
  return new Set((workflow.data_points ?? []).map((point) => point.status)).size;
}

function issueCountForWorkflow(workflow: StatusWaitingWorkflowSection): number {
  if (workflow.data_points && workflow.data_points.length > 0) {
    return new Set(workflow.data_points.map((point) => point.issue_id)).size;
  }
  return workflow.rows.reduce((sum, row) => sum + row.unique_issue_count, 0);
}

function parseWorkflowSections(
  value: unknown,
  includeDataPoints: boolean,
): StatusWaitingWorkflowSection[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const label = typeof record.label === "string" ? record.label : "";
    const catalogKey = typeof record.catalog_key === "string" ? record.catalog_key : label;
    if (!label) return [];
    return [
      {
        catalog_key: catalogKey,
        label,
        workflow_id: typeof record.workflow_id === "number" ? record.workflow_id : null,
        workflow_name: typeof record.workflow_name === "string" ? record.workflow_name : label,
        issue_type_options: stringList(record.issue_type_options),
        status_order: stringList(record.status_order),
        data_points: includeDataPoints ? parseDataPoints(record.data_points) : [],
        priority_columns: stringList(record.priority_columns),
        projects: projectList(record.projects),
        rows: parseRows(record.rows),
      },
    ];
  });
}

function parseDataPoints(value: unknown): StatusWaitingDataPoint[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const issueType = typeof record.issue_type === "string" ? record.issue_type : "";
    const status = typeof record.status === "string" ? record.status : "";
    const priority = typeof record.priority === "string" ? record.priority : "Unknown";
    const issueId = typeof record.issue_id === "number" ? record.issue_id : null;
    const issueKey = typeof record.issue_key === "string" ? record.issue_key : "";
    const days = typeof record.days === "number" ? record.days : null;
    if (!issueType || !status || issueId == null || days == null) return [];
    return [{ issue_id: issueId, issue_key: issueKey, issue_type: issueType, status, priority, days }];
  });
}

function parseRows(value: unknown): StatusWaitingPriorityRow[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const status = typeof record.status === "string" ? record.status : "";
    if (!status) return [];
    return [
      {
        status,
        unique_issue_count:
          typeof record.unique_issue_count === "number" ? record.unique_issue_count : 0,
        average_days_all_priorities:
          typeof record.average_days_all_priorities === "number"
            ? record.average_days_all_priorities
            : null,
        median_by_priority:
          record.median_by_priority && typeof record.median_by_priority === "object"
            ? parseMedianByPriority(record.median_by_priority)
            : {},
        average_by_priority:
          record.average_by_priority && typeof record.average_by_priority === "object"
            ? parseMedianByPriority(record.average_by_priority)
            : {},
      },
    ];
  });
}

function parseMedianByPriority(value: object): Record<string, number | null> {
  const result: Record<string, number | null> = {};
  for (const [key, raw] of Object.entries(value)) {
    if (raw === null || raw === undefined) {
      result[key] = null;
      continue;
    }
    if (typeof raw === "number" && Number.isFinite(raw)) {
      result[key] = raw;
    }
  }
  return result;
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
