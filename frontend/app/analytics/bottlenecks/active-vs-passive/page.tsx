"use client";
import { Fragment, forwardRef, useEffect, useMemo, useRef, useState } from "react";
import { useAnalyticsReportLoad } from "@/hooks/useAnalyticsReportLoad";
import {
  AnalyticsFilterPanel,
  FilterField,
  filterInputClassName,
} from "@/app/components/jira-analytics/AnalyticsReportControls";
import {
  BottleneckMetricCard,
  BottleneckReportLayout,
} from "@/app/components/jira-analytics/BottleneckReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { lastFourQuartersRange } from "@/lib/jira-analytics-dates";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import { MAIN_DELIVERY_WORKFLOWS } from "@/lib/jira-analytics-workflows";
import { sortMainDeliveryWorkflowSections } from "@/lib/sort-main-delivery-workflows";
import {
  ELAPSED_TIME_NOTE,
  formatElapsedDays,
  formatElapsedTimeWithHours,
} from "@/lib/elapsed-time-format";
import type { AnalyticsReportResponse, ReportQueryParams } from "@/types/jira-analytics";

interface ActivePassiveFilters {
  from: string;
  to: string;
}

interface ActivePassivePoint {
  issue_id: number;
  issue_key: string;
  issue_type: string;
  team: string;
  confidence: string;
  attribution_detail: string;
  status_class: string;
  hours: number;
}

interface ActivePassiveTimelinePoint {
  issue_id: number;
  issue_key: string;
  issue_type: string;
  team: string;
  status: string;
  status_class: string | null;
  interval_start: string;
  interval_end: string | null;
  hours: number;
}

interface ActivePassiveWorkflowSection {
  catalog_key: string;
  label: string;
  workflow_id?: number | null;
  workflow_name?: string | null;
  issue_type_options: string[];
  data_points: ActivePassivePoint[];
  timeline_points: ActivePassiveTimelinePoint[];
}

interface ActivePassiveIssueRow {
  issue_id: number;
  issue_key: string;
  issue_type: string;
  classes: Record<string, number>;
  total_hours: number;
}

interface ActivePassiveTeamRow {
  team: string;
  classes: Record<string, number>;
  total_hours: number;
  issue_count: number;
  attribution_details: string[];
  issues: ActivePassiveIssueRow[];
}

interface ActivePassiveTeamAccumulator {
  classes: Record<string, number>;
  issues: Map<number, ActivePassiveIssueRow>;
  details: Set<string>;
}

interface SelectedIssue {
  issue_id: number;
  issue_key: string;
  issue_type: string;
  team: string;
}

export default function Page() {
  const initialRange = useMemo(() => lastFourQuartersRange(), []);
  const [draftFilters, setDraftFilters] = useState<ActivePassiveFilters>({
    from: initialRange.from,
    to: initialRange.to,
  });
  const [queryParams, setQueryParams] = useState<ReportQueryParams>({
    from: initialRange.from,
    to: initialRange.to,
  });
  const [selectedTeam, setSelectedTeam] = useState<string>("");
  const { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry } = useAnalyticsReportLoad({
    deps: [queryParams],
    load: (signal) => fetchAnalyticsReport(reportPaths.activeVsPassive, queryParams, signal),
  });

  const workflows = sortMainDeliveryWorkflowSections(parseWorkflowSections(data?.filters?.main_workflows));
  const availableTeams = stringList(data?.filters?.available_teams);
  const hasRows = workflows.some((workflow) => workflow.data_points.length > 0);
  const workflowsSynced = data?.filters?.workflows_synced === true;
  const empty = !loading && !refreshing && !error && !hasRows;
  const emptyMessage = !workflowsSynced
    ? "Jira workflow definitions are not loaded yet. Run workflow sync to import workflows."
    : "No active/passive workflow data for the selected filters.";

  return (
    <JiraAnalyticsShell
      title="Active vs passive time"
      description="Active work vs Product, Dev, and QA queue elapsed time by attributed team."
      hidePageHeader
      hideMethodology
    >
      <BottleneckReportLayout
        activeReport="active-vs-passive"
        title="See whether flow time is active delivery or waiting."
        description="A workflow-efficiency view that separates hands-on execution from queues, reviews, QA, blocked states, and other passive elapsed time by attributed team."
        mainWorkflowLineage={MAIN_DELIVERY_WORKFLOWS.map((workflow) => ({
          label: workflow.label,
          purpose: workflow.purpose,
          issueTypes: workflow.issueTypes,
        }))}
        metrics={<ActivePassiveMetrics workflows={workflows} selectedTeam={selectedTeam} />}
        controls={
          <AnalyticsFilterPanel
            title="Cohort filter"
            description={`This report selects issues by created date, then summarizes their workflow elapsed time. ${ELAPSED_TIME_NOTE}`}
          >
            <FilterField label="Created from">
              <input
                type="date"
                value={draftFilters.from}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, from: event.target.value }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="Created to">
              <input
                type="date"
                value={draftFilters.to}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, to: event.target.value }))}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="Team" className="min-w-[14rem]">
              <select
                value={selectedTeam}
                onChange={(event) => setSelectedTeam(event.target.value)}
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
            <div className="flex gap-2 self-end">
              <button
                type="button"
                onClick={() => setQueryParams({ from: draftFilters.from, to: draftFilters.to })}
                disabled={loading}
                className="h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={() => {
                  const range = lastFourQuartersRange();
                  setDraftFilters(range);
                  setQueryParams(range);
                }}
                className="h-11 rounded-xl border border-outline-variant/40 px-4 text-sm font-semibold text-on-surface hover:bg-surface-container-high"
              >
                Last 4 quarters
              </button>
            </div>
          </AnalyticsFilterPanel>
        }
        readingTip="Use passive share to find whether a workflow needs more execution focus or queue cleanup. Expand a team row when you need the underlying issue timeline evidence."
      >
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
          <ActivePassiveReportView workflows={workflows} selectedTeam={selectedTeam} />
        </ReportPageFrame>
      </BottleneckReportLayout>
    </JiraAnalyticsShell>
  );
}

function ActivePassiveMetrics({
  workflows,
  selectedTeam,
}: {
  workflows: ActivePassiveWorkflowSection[];
  selectedTeam: string;
}) {
  const rows = workflows.flatMap((workflow) =>
    aggregateActivePassivePoints(workflow.data_points, workflow.issue_type_options, selectedTeam),
  );
  const totalHours = rows.reduce((sum, row) => sum + row.total_hours, 0);
  const passiveHours = rows.reduce((sum, row) => {
    return sum + Object.entries(row.classes).reduce((innerSum, [key, hours]) => {
      return key === "Active Work" || key === "Done" ? innerSum : innerSum + hours;
    }, 0);
  }, 0);
  const teams = new Set(rows.map((row) => row.team)).size;

  return (
    <>
      <BottleneckMetricCard label="Teams" value={rows.length ? String(teams) : "Loading"} detail={selectedTeam || "All attributed teams"} />
      <BottleneckMetricCard label="Elapsed workflow time" value={formatCompactElapsedDays(totalHours)} detail="Visible cohort, calendar days" />
      <BottleneckMetricCard label="Passive share" value={formatPercentShare(passiveHours, totalHours)} detail="Non-active and non-done time" />
    </>
  );
}

function ActivePassiveReportView({
  workflows,
  selectedTeam,
}: {
  workflows: ActivePassiveWorkflowSection[];
  selectedTeam: string;
}) {
  if (!workflows.some((workflow) => workflow.data_points.length > 0)) {
    return (
      <p className="text-sm text-on-surface-variant">
        No active/passive data for the selected filters. Widen the date range or run workflow sync.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {workflows.map((workflow) => (
        <WorkflowBlock key={workflow.catalog_key} workflow={workflow} selectedTeam={selectedTeam} />
      ))}
    </div>
  );
}

function WorkflowBlock({
  workflow,
  selectedTeam,
}: {
  workflow: ActivePassiveWorkflowSection;
  selectedTeam: string;
}) {
  const options = workflow.issue_type_options;
  const [selectedTypes, setSelectedTypes] = useState<string[] | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<SelectedIssue | null>(null);
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const effectiveSelected = selectedTypes ?? options;
  const rows = useMemo(
    () => aggregateActivePassivePoints(workflow.data_points, effectiveSelected, selectedTeam),
    [workflow.data_points, effectiveSelected, selectedTeam],
  );
  const classKeys = useMemo(() => statusClassKeys(rows), [rows]);
  const selectedTimeline = useMemo(() => {
    if (!selectedIssue) return [];
    return workflow.timeline_points
      .filter((point) => {
        if (point.issue_id !== selectedIssue.issue_id) return false;
        if (point.team !== selectedIssue.team) return false;
        if (!effectiveSelected.includes(point.issue_type)) return false;
        if (selectedTeam && point.team !== selectedTeam) return false;
        return true;
      })
      .sort((a, b) => a.interval_start.localeCompare(b.interval_start));
  }, [effectiveSelected, selectedIssue, selectedTeam, workflow.timeline_points]);

  useEffect(() => {
    if (!selectedIssue) return;
    const issueStillVisible = rows.some((row) =>
      row.issues.some((issue) => issue.issue_id === selectedIssue.issue_id),
    );
    if (!issueStillVisible) setSelectedIssue(null);
  }, [rows, selectedIssue]);

  useEffect(() => {
    if (!selectedIssue) return;
    window.requestAnimationFrame(() => {
      timelineRef.current?.focus();
      timelineRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }, [selectedIssue]);

  return (
    <ModernReportCard
      eyebrow="Workflow"
      title={workflow.label}
      description={`${ELAPSED_TIME_NOTE} Issue-type pills filter instantly without reloading.`}
    >
      {options.length > 0 ? (
        <IssueTypePills options={options} selected={effectiveSelected} onChange={setSelectedTypes} />
      ) : (
        <p className="mt-2 text-sm text-on-surface-variant">
          No eligible issue types in the current data slice.
        </p>
      )}
      <div className="mt-4">
        <ActivePassiveTable
          rows={rows}
          classKeys={classKeys}
          selectedIssueId={selectedIssue?.issue_id ?? null}
          onSelectIssue={(issue, team) => setSelectedIssue({ ...issue, team })}
        />
      </div>
      {selectedIssue ? (
        <IssueTimelinePanel
          ref={timelineRef}
          issue={selectedIssue}
          points={selectedTimeline}
          onClose={() => setSelectedIssue(null)}
        />
      ) : null}
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
      onChange(next.length === 0 ? null : next.length === options.length ? null : next);
      return;
    }
    if (!allSelected && selected.length === 1) {
      onChange([option]);
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

function ActivePassiveTable({
  rows,
  classKeys,
  selectedIssueId,
  onSelectIssue,
}: {
  rows: ActivePassiveTeamRow[];
  classKeys: string[];
  selectedIssueId: number | null;
  onSelectIssue: (issue: ActivePassiveIssueRow, team: string) => void;
}) {
  const [expandedTeams, setExpandedTeams] = useState<Set<string>>(new Set());

  if (!rows.length) {
    return <p className="text-sm text-on-surface-variant">No data for the current filters.</p>;
  }

  const toggleTeam = (team: string) => {
    setExpandedTeams((prev) => {
      const next = new Set(prev);
      if (next.has(team)) {
        next.delete(team);
      } else {
        next.add(team);
      }
      return next;
    });
  };

  return (
    <div className="overflow-x-auto rounded-lg elevated-panel">
      <table className="w-full min-w-[34rem] text-sm">
        <thead>
          <tr className="border-b border-outline-variant/20 bg-surface-container-low/80 text-on-surface-variant">
            <th className="px-3 py-2 text-left font-medium">Team</th>
            {classKeys.map((key) => (
              <th key={key} className="px-3 py-2 text-right font-medium capitalize">
                {key.replaceAll("_", " ")}
              </th>
            ))}
            <th className="px-3 py-2 text-right font-medium">Total</th>
            <th className="px-3 py-2 text-right font-medium">Issues</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const expanded = expandedTeams.has(row.team);
            return (
              <Fragment key={row.team}>
                <tr className="border-b border-outline-variant/10">
                  <td className="px-3 py-2 font-medium text-on-surface" title={tooltipText(row)}>
                    <button
                      type="button"
                      onClick={() => toggleTeam(row.team)}
                      className="inline-flex items-center gap-2 text-left font-medium hover:text-primary"
                      aria-expanded={expanded}
                    >
                      <span className="inline-block w-4 text-xs text-on-surface-variant">
                        {expanded ? "▼" : "▶"}
                      </span>
                      {row.team}
                    </button>
                  </td>
                  {classKeys.map((key) => (
                    <td key={key} className="px-3 py-2 text-right tabular-nums text-on-surface">
                      {formatElapsedDays(numberValue(row.classes[key]))}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-right tabular-nums font-medium text-on-surface">
                    {formatElapsedDays(row.total_hours)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">
                    {row.issue_count}
                  </td>
                </tr>
                {expanded ? (
                  <tr className="border-b border-outline-variant/10 bg-surface-container-low/30">
                    <td colSpan={classKeys.length + 4} className="px-3 py-3">
                      <IssueBreakdownTable
                        issues={row.issues}
                        classKeys={classKeys}
                        team={row.team}
                        selectedIssueId={selectedIssueId}
                        onSelectIssue={onSelectIssue}
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
        Team attribution uses PMGT team metadata when available, then DEV/QA contributor teams from
        worklogs and user assignments.
      </p>
    </div>
  );
}

function IssueBreakdownTable({
  issues,
  classKeys,
  team,
  selectedIssueId,
  onSelectIssue,
}: {
  issues: ActivePassiveIssueRow[];
  classKeys: string[];
  team: string;
  selectedIssueId: number | null;
  onSelectIssue: (issue: ActivePassiveIssueRow, team: string) => void;
}) {
  if (!issues.length) {
    return <p className="text-xs text-on-surface-variant">No issues for this team.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-outline-variant/10 bg-surface">
      <table className="w-full min-w-[30rem] text-xs">
        <thead>
          <tr className="border-b border-outline-variant/10 text-on-surface-variant">
            <th className="px-3 py-2 text-left font-medium">Issue</th>
            <th className="px-3 py-2 text-left font-medium">Type</th>
            {classKeys.map((key) => (
              <th key={key} className="px-3 py-2 text-right font-medium">
                {key}
              </th>
            ))}
            <th className="px-3 py-2 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => {
            const selected = selectedIssueId === issue.issue_id;
            return (
              <tr
                key={issue.issue_id}
                role="button"
                tabIndex={0}
                onClick={() => onSelectIssue(issue, team)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectIssue(issue, team);
                  }
                }}
                className={`cursor-pointer border-b border-outline-variant/10 outline-none last:border-b-0 hover:bg-primary/5 focus:bg-primary/10 ${
                  selected ? "bg-primary/10" : ""
                }`}
              >
                <td className="px-3 py-2 font-medium">
                  <a
                    href={jiraIssueUrl(issue.issue_key)}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(event) => event.stopPropagation()}
                    className="text-primary underline-offset-2 hover:underline"
                  >
                    {issue.issue_key}
                  </a>
                </td>
                <td className="px-3 py-2 text-on-surface-variant">{issue.issue_type}</td>
                {classKeys.map((key) => (
                  <td key={key} className="px-3 py-2 text-right tabular-nums text-on-surface">
                    {formatElapsedDays(numberValue(issue.classes[key]))}
                  </td>
                ))}
                <td className="px-3 py-2 text-right tabular-nums font-medium text-on-surface">
                  {formatElapsedDays(issue.total_hours)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const IssueTimelinePanel = forwardRef<
  HTMLDivElement,
  {
    issue: SelectedIssue;
    points: ActivePassiveTimelinePoint[];
    onClose: () => void;
  }
>(function IssueTimelinePanel({ issue, points, onClose }, ref) {
  const totalHours = points.reduce((sum, point) => sum + point.hours, 0);

  return (
    <section
      ref={ref}
      tabIndex={-1}
      className="mt-5 rounded-2xl border border-primary/30 bg-primary/5 p-4 outline-none ring-primary/30 focus:ring-2"
      aria-label={`Status timeline for ${issue.issue_key}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-label uppercase tracking-[0.18em] text-primary">Issue timeline</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <a
              href={jiraIssueUrl(issue.issue_key)}
              target="_blank"
              rel="noreferrer"
              className="text-lg font-bold text-primary underline-offset-2 hover:underline"
            >
              {issue.issue_key}
            </a>
            <span className="text-sm text-on-surface-variant">{issue.issue_type}</span>
            <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-on-surface-variant">
              {issue.team}
            </span>
          </div>
          <p className="mt-1 text-sm text-on-surface-variant">
            {ELAPSED_TIME_NOTE} Total visible timeline:{" "}
            <span className="font-medium text-on-surface">{formatElapsedTimeWithHours(totalHours)}</span>.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-outline-variant/40 px-3 py-1 text-xs font-semibold text-on-surface-variant hover:bg-surface-container-high"
        >
          Close
        </button>
      </div>

      {points.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-xl border border-outline-variant/20 bg-surface">
          <table className="w-full min-w-[52rem] text-xs">
            <thead>
              <tr className="border-b border-outline-variant/10 bg-surface-container-low text-on-surface-variant">
                <th className="px-3 py-2 text-left font-medium">From</th>
                <th className="px-3 py-2 text-left font-medium">To</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-left font-medium">Bucket</th>
                <th className="px-3 py-2 text-right font-medium">Elapsed</th>
                <th className="px-3 py-2 text-right font-medium">Hours</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point, index) => (
                <tr
                  key={`${point.issue_id}-${point.interval_start}-${point.status}-${index}`}
                  className="border-b border-outline-variant/10 last:border-b-0"
                >
                  <td className="px-3 py-2 tabular-nums text-on-surface">
                    {formatDateTime(point.interval_start)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-on-surface">
                    {point.interval_end ? formatDateTime(point.interval_end) : "Open"}
                  </td>
                  <td className="px-3 py-2 font-medium text-on-surface">{point.status}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${bucketClassName(point.status_class)}`}>
                      {point.status_class ?? "Excluded"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface">
                    {formatElapsedDays(point.hours, 2)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-on-surface-variant">
                    {formatHours(point.hours)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 rounded-xl border border-dashed border-outline-variant/30 bg-surface p-4 text-sm text-on-surface-variant">
          No timeline intervals are available for this issue in the current filters.
        </p>
      )}
    </section>
  );
});

function aggregateActivePassivePoints(
  points: ActivePassivePoint[],
  selectedIssueTypes: string[],
  selectedTeam: string,
): ActivePassiveTeamRow[] {
  const selected = new Set(selectedIssueTypes);
  const byTeam = new Map<string, ActivePassiveTeamAccumulator>();
  for (const point of points) {
    if (!selected.has(point.issue_type)) continue;
    if (selectedTeam && point.team !== selectedTeam) continue;
    const row =
      byTeam.get(point.team) ??
      ({
        classes: {},
        issues: new Map<number, ActivePassiveIssueRow>(),
        details: new Set<string>(),
      } satisfies ActivePassiveTeamAccumulator);
    row.classes[point.status_class] = (row.classes[point.status_class] ?? 0) + point.hours;
    const issue =
      row.issues.get(point.issue_id) ?? {
        issue_id: point.issue_id,
        issue_key: point.issue_key,
        issue_type: point.issue_type,
        classes: {},
        total_hours: 0,
      };
    issue.classes[point.status_class] = (issue.classes[point.status_class] ?? 0) + point.hours;
    issue.total_hours += point.hours;
    row.issues.set(point.issue_id, issue);
    if (point.attribution_detail) row.details.add(point.attribution_detail);
    byTeam.set(point.team, row);
  }
  return Array.from(byTeam.entries())
    .map(([team, value]) => {
      const classHours = Object.fromEntries(
        Object.entries(value.classes).map(([key, hours]) => [key, roundHours(hours)]),
      );
      const totalHours = Object.values(value.classes).reduce((sum, hours) => sum + hours, 0);
      return {
        team,
        classes: classHours,
        total_hours: roundHours(totalHours),
        issue_count: value.issues.size,
        attribution_details: Array.from(value.details).sort(),
        issues: Array.from(value.issues.values())
          .map((issue) => ({
            ...issue,
            classes: Object.fromEntries(
              Object.entries(issue.classes).map(([key, hours]) => [key, roundHours(hours)]),
            ),
            total_hours: roundHours(issue.total_hours),
          }))
          .sort((a, b) => b.total_hours - a.total_hours || a.issue_key.localeCompare(b.issue_key)),
      };
    })
    .sort((a, b) => a.team.localeCompare(b.team));
}

function statusClassKeys(rows: ActivePassiveTeamRow[]): string[] {
  const keys = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row.classes)) {
      keys.add(key);
    }
  }
  return Array.from(keys).sort();
}

function parseWorkflowSections(value: unknown): ActivePassiveWorkflowSection[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const catalogKey = typeof record.catalog_key === "string" ? record.catalog_key : "";
    const label = typeof record.label === "string" ? record.label : catalogKey;
    if (!catalogKey || !label) return [];
    return [
      {
        catalog_key: catalogKey,
        label,
        workflow_id: typeof record.workflow_id === "number" ? record.workflow_id : null,
        workflow_name: typeof record.workflow_name === "string" ? record.workflow_name : label,
        issue_type_options: stringList(record.issue_type_options),
        data_points: parsePoints(record.data_points),
        timeline_points: parseTimelinePoints(record.timeline_points),
      },
    ];
  });
}

function parsePoints(value: unknown): ActivePassivePoint[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const issueId = typeof record.issue_id === "number" ? record.issue_id : null;
    const issueKey = typeof record.issue_key === "string" ? record.issue_key : "";
    const issueType = typeof record.issue_type === "string" ? record.issue_type : "";
    const team = typeof record.team === "string" ? record.team : "Unknown";
    const confidence = typeof record.confidence === "string" ? record.confidence : "unknown";
    const attributionDetail =
      typeof record.attribution_detail === "string" ? record.attribution_detail : "";
    const statusClass = typeof record.status_class === "string" ? record.status_class : "";
    const hours = typeof record.hours === "number" ? record.hours : null;
    if (issueId == null || !issueType || !statusClass || hours == null) return [];
    return [
      {
        issue_id: issueId,
        issue_key: issueKey,
        issue_type: issueType,
        team,
        confidence,
        attribution_detail: attributionDetail,
        status_class: statusClass,
        hours,
      },
    ];
  });
}

function parseTimelinePoints(value: unknown): ActivePassiveTimelinePoint[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const issueId = typeof record.issue_id === "number" ? record.issue_id : null;
    const issueKey = typeof record.issue_key === "string" ? record.issue_key : "";
    const issueType = typeof record.issue_type === "string" ? record.issue_type : "";
    const team = typeof record.team === "string" ? record.team : "Unknown";
    const status = typeof record.status === "string" ? record.status : "";
    const statusClass =
      typeof record.status_class === "string" ? record.status_class : null;
    const intervalStart =
      typeof record.interval_start === "string" ? record.interval_start : "";
    const intervalEnd =
      typeof record.interval_end === "string" ? record.interval_end : null;
    const hours = typeof record.hours === "number" ? record.hours : null;
    if (issueId == null || !issueKey || !issueType || !status || !intervalStart || hours == null) {
      return [];
    }
    return [
      {
        issue_id: issueId,
        issue_key: issueKey,
        issue_type: issueType,
        team,
        status,
        status_class: statusClass,
        interval_start: intervalStart,
        interval_end: intervalEnd,
        hours,
      },
    ];
  });
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function roundHours(value: number): number {
  return Math.round(value * 100) / 100;
}

function formatHours(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "0.00";
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatCompactElapsedDays(value: number): string {
  if (!value) return "Loading";
  return formatElapsedDays(value, 0);
}

function formatPercentShare(numerator: number, denominator: number): string {
  if (!denominator) return "Loading";
  return `${Math.round((numerator / denominator) * 100)}%`;
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function tooltipText(row: ActivePassiveTeamRow): string | undefined {
  if (row.attribution_details.length === 0) return undefined;
  return row.attribution_details.join("\n");
}

function jiraIssueUrl(issueKey: string): string {
  return `https://plunet.atlassian.net/browse/${encodeURIComponent(issueKey)}`;
}

function bucketClassName(bucket: string | null): string {
  switch (bucket) {
    case "Active Work":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "Dev Queue":
      return "bg-sky-500/10 text-sky-700 dark:text-sky-300";
    case "Product Queue":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "QA Queue":
      return "bg-violet-500/10 text-violet-700 dark:text-violet-300";
    default:
      return "bg-surface-container-high text-on-surface-variant";
  }
}
