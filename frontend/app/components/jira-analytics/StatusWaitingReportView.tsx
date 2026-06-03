"use client";

import { Fragment, useMemo, useState } from "react";
import { JiraIssueLink, jiraBrowseUrl } from "@/app/components/jira-analytics/JiraIssueLink";
import { useJiraBaseUrl } from "@/app/components/jira-analytics/JiraAnalyticsContext";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { aggregateStatusWaitingPoints } from "@/lib/status-waiting-aggregate";
import { buildStatusWaitingDrilldownByPriority } from "@/lib/status-waiting-drilldown";
import { STATUS_WAITING_PRIORITY_COLUMNS } from "@/lib/status-waiting-priorities";
import type { StatusWaitingDataPoint, StatusWaitingWorkflowSection } from "@/types/jira-analytics";

interface StatusWaitingReportViewProps {
  mainWorkflows: StatusWaitingWorkflowSection[];
  otherWorkflows: StatusWaitingWorkflowSection[];
  showOtherWorkflows: boolean;
  statistic: "median" | "average";
}

export function StatusWaitingReportView({
  mainWorkflows,
  otherWorkflows,
  showOtherWorkflows,
  statistic,
}: StatusWaitingReportViewProps) {
  const hasMain = mainWorkflows.some((workflow) => (workflow.data_points?.length ?? 0) > 0);
  const hasOther = showOtherWorkflows && otherWorkflows.some((workflow) => workflow.rows.length > 0);

  if (!hasMain && !hasOther) {
    return (
      <p className="text-sm text-on-surface-variant">
        No status waiting data for the selected filters. Widen the date range or include more projects.
      </p>
    );
  }

  return (
    <div className="space-y-12">
      <section className="space-y-8">
        {mainWorkflows.map((workflow) => (
          <MainWorkflowBlock key={workflow.catalog_key} workflow={workflow} statistic={statistic} />
        ))}
      </section>

      {showOtherWorkflows ? (
        <section className="space-y-8">
          {otherWorkflows.map((workflow) => (
            <ModernReportCard
              key={workflow.catalog_key}
              eyebrow="Specialist workflow"
              title={workflow.label}
              description="Specialist workflow wait time for the same global date range and project selection."
            >
              <WorkflowProjectScope projects={workflow.projects ?? []} workflowLabel={workflow.label} />
              <div className="mt-3">
                <WorkflowPriorityTable rows={workflow.rows} statistic={statistic} />
              </div>
            </ModernReportCard>
          ))}
        </section>
      ) : null}
    </div>
  );
}

function MainWorkflowBlock({
  workflow,
  statistic,
}: {
  workflow: StatusWaitingWorkflowSection;
  statistic: "median" | "average";
}) {
  const options = workflow.issue_type_options ?? [];
  const [selectedTypes, setSelectedTypes] = useState<string[] | null>(null);
  const effectiveSelected = selectedTypes ?? options;
  const dataPoints = workflow.data_points ?? [];

  const rows = useMemo(
    () =>
      aggregateStatusWaitingPoints(dataPoints, {
        selectedIssueTypes: effectiveSelected,
        statusOrder: workflow.status_order,
        catalogKey: workflow.catalog_key,
      }).rows,
    [dataPoints, workflow.status_order, workflow.catalog_key, effectiveSelected],
  );

  return (
    <ModernReportCard
      eyebrow="Main workflow"
      title={workflow.label}
      description="Issue-type pills filter instantly without reloading. Expand a status to see the longest-waiting issues by priority."
    >
      {options.length > 0 ? (
        <IssueTypePills
          options={options}
          selected={effectiveSelected}
          onChange={setSelectedTypes}
        />
      ) : (
        <p className="mt-2 text-sm text-on-surface-variant">
          No eligible issue types in the current data slice.
        </p>
      )}
      <div className="mt-4">
        <WorkflowPriorityTable
          rows={rows}
          statistic={statistic}
          dataPoints={dataPoints}
          catalogKey={workflow.catalog_key}
          selectedIssueTypes={effectiveSelected}
        />
      </div>
    </ModernReportCard>
  );
}

function IssueTypePills({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (selected: string[] | null) => void;
}) {
  const allSelected = selected.length === options.length;

  const toggle = (option: string) => {
    const isOn = selected.includes(option);
    if (isOn) {
      const next = selected.filter((item) => item !== option);
      onChange(next.length === 0 ? [] : next.length === options.length ? null : next);
      return;
    }
    const next = [...selected, option].sort((a, b) => a.localeCompare(b));
    onChange(next.length === options.length ? null : next);
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => onChange(null)}
        className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
          allSelected
            ? "border-primary bg-primary text-on-primary"
            : "border-outline-variant/40 bg-surface text-on-surface-variant hover:bg-surface-container-high"
        }`}
      >
        All types
      </button>
      {options.map((option) => {
        const active = selected.includes(option);
        return (
          <button
            key={option}
            type="button"
            onClick={() => toggle(option)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              active
                ? "border-primary bg-primary/10 text-primary"
                : "border-outline-variant/40 bg-surface text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

function WorkflowProjectScope({
  projects,
  workflowLabel,
}: {
  projects: { key: string; name?: string | null }[];
  workflowLabel: string;
}) {
  if (!projects.length) {
    return (
      <p className="rounded-lg border border-dashed border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface-variant">
        No projects in the current filter use {workflowLabel}.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-outline-variant/28 bg-surface-container-low px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
        Projects in scope ({projects.length})
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {projects.map((project) => (
          <span
            key={project.key}
            className="inline-flex items-center gap-1.5 rounded-full border border-outline-variant/25 bg-surface px-2.5 py-1 text-xs text-on-surface"
            title={project.name ?? project.key}
          >
            <span className="font-semibold">{project.key}</span>
            {project.name ? (
              <span className="max-w-[12rem] truncate text-on-surface-variant">{project.name}</span>
            ) : null}
          </span>
        ))}
      </div>
    </div>
  );
}

function WorkflowPriorityTable({
  rows,
  statistic,
  dataPoints,
  catalogKey,
  selectedIssueTypes,
}: {
  rows: StatusWaitingWorkflowSection["rows"];
  statistic: "median" | "average";
  dataPoints?: StatusWaitingDataPoint[];
  catalogKey?: string;
  selectedIssueTypes?: string[];
}) {
  const [expandedStatuses, setExpandedStatuses] = useState<Set<string>>(new Set());
  const canDrilldown = Boolean(dataPoints?.length && selectedIssueTypes?.length && catalogKey);

  if (!rows.length) {
    return <p className="text-sm text-on-surface-variant">No data for the current filters.</p>;
  }

  const toggleStatus = (status: string) => {
    setExpandedStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(status)) {
        next.delete(status);
      } else {
        next.add(status);
      }
      return next;
    });
  };

  return (
    <div className="overflow-x-auto rounded-lg elevated-panel">
      <table className="w-full min-w-[40rem] text-sm">
        <thead>
          <tr className="border-b border-outline-variant/20 bg-surface-container-low/80 text-on-surface-variant">
            <th className="sticky left-0 z-10 bg-surface-container-low/95 px-3 py-2 text-left font-medium">
              Status
            </th>
            {STATUS_WAITING_PRIORITY_COLUMNS.map((priority) => (
              <th key={priority} className="px-3 py-2 text-right font-medium whitespace-nowrap">
                {priority}
              </th>
            ))}
            <th className="px-3 py-2 text-right font-medium whitespace-nowrap">Average</th>
            <th className="px-3 py-2 text-right font-medium whitespace-nowrap">Issue Count</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const expanded = expandedStatuses.has(row.status);
            return (
              <Fragment key={row.status}>
                <tr className="border-b border-outline-variant/10">
                  <td className="sticky left-0 z-10 bg-surface-container-lowest px-3 py-2 font-medium text-on-surface">
                    {canDrilldown ? (
                      <button
                        type="button"
                        onClick={() => toggleStatus(row.status)}
                        className="inline-flex items-center gap-2 text-left font-medium hover:text-primary"
                        aria-expanded={expanded}
                      >
                        <span className="inline-block w-4 text-xs text-on-surface-variant">
                          {expanded ? "▼" : "▶"}
                        </span>
                        {row.status}
                      </button>
                    ) : (
                      row.status
                    )}
                  </td>
                  {STATUS_WAITING_PRIORITY_COLUMNS.map((priority) => {
                    const valuesByPriority =
                      statistic === "average" ? row.average_by_priority : row.median_by_priority;
                    const value = valuesByPriority[priority];
                    return (
                      <td
                        key={priority}
                        className={`px-3 py-2 text-right tabular-nums ${
                          value == null ? "text-on-surface-variant/50" : cellTone(value)
                        }`}
                      >
                        {value == null ? "—" : value.toFixed(1)}
                      </td>
                    );
                  })}
                  <td
                    className={`px-3 py-2 text-right tabular-nums ${
                      row.average_days_all_priorities == null
                        ? "text-on-surface-variant/50"
                        : cellTone(row.average_days_all_priorities)
                    }`}
                  >
                    {row.average_days_all_priorities == null
                      ? "—"
                      : row.average_days_all_priorities.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">
                    {row.unique_issue_count}
                  </td>
                </tr>
                {expanded && canDrilldown ? (
                  <tr className="border-b border-outline-variant/10 bg-surface-container-low/30">
                    <td colSpan={STATUS_WAITING_PRIORITY_COLUMNS.length + 3} className="px-3 py-3">
                      <StatusWaitingDrilldownPanel
                        status={row.status}
                        dataPoints={dataPoints ?? []}
                        catalogKey={catalogKey ?? ""}
                        selectedIssueTypes={selectedIssueTypes ?? []}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <p className="border-t border-outline-variant/10 px-3 py-2 text-xs text-on-surface-variant">
        Priority columns = {statisticLabel(statistic).toLowerCase()} days in status per priority.
        Average = mean wait across all priorities. Issue Count = unique issues that entered the status.
        {canDrilldown ? " Expand a status to see the top 10 longest-waiting issues per priority." : ""}
      </p>
    </div>
  );
}

function StatusWaitingDrilldownPanel({
  status,
  dataPoints,
  catalogKey,
  selectedIssueTypes,
}: {
  status: string;
  dataPoints: StatusWaitingDataPoint[];
  catalogKey: string;
  selectedIssueTypes: string[];
}) {
  const jiraBaseUrl = useJiraBaseUrl();
  const byPriority = useMemo(
    () =>
      buildStatusWaitingDrilldownByPriority(dataPoints, status, {
        selectedIssueTypes,
        catalogKey,
      }),
    [dataPoints, status, selectedIssueTypes, catalogKey],
  );
  const priorities = Object.keys(byPriority);
  if (!priorities.length) {
    return <p className="text-xs text-on-surface-variant">No issues for this status in the current filters.</p>;
  }

  return (
    <div className="space-y-4">
      {priorities.map((priority) => {
        const issues = byPriority[priority] ?? [];
        return (
          <div key={priority} className="rounded-md border border-outline-variant/10 bg-surface">
            <p className="border-b border-outline-variant/10 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
              {priority} — top {issues.length} longest waits (days)
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[24rem] text-xs">
                <thead>
                  <tr className="border-b border-outline-variant/10 text-on-surface-variant">
                    <th className="px-3 py-2 text-left font-medium">Issue</th>
                    <th className="px-3 py-2 text-left font-medium">Type</th>
                    <th className="px-3 py-2 text-right font-medium">Days in status</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((issue) => (
                    <tr
                      key={issue.issue_id}
                      className="border-b border-outline-variant/10 last:border-b-0"
                    >
                      <td className="px-3 py-2 font-medium text-on-surface">
                        {jiraBaseUrl && issue.issue_key ? (
                          <JiraIssueLink
                            issueKey={issue.issue_key}
                            issueUrl={jiraBrowseUrl(jiraBaseUrl, issue.issue_key)}
                            jiraBaseUrl={jiraBaseUrl}
                          />
                        ) : (
                          issue.issue_key || `#${issue.issue_id}`
                        )}
                      </td>
                      <td className="px-3 py-2 text-on-surface-variant">{issue.issue_type}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-medium text-on-surface">
                        {issue.days.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function statisticLabel(statistic: "median" | "average"): string {
  return statistic === "average" ? "Average" : "Median";
}

function cellTone(days: number): string {
  if (days >= 14) return "font-medium text-error";
  if (days >= 7) return "text-on-surface";
  return "text-on-surface-variant";
}
