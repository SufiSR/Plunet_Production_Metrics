"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { AnalyticsFilterPanel, FilterField, filterInputClassName } from "@/app/components/jira-analytics/AnalyticsReportControls";
import { FeatureMetricCard, FeatureReportLayout } from "@/app/components/jira-analytics/FeatureReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import { fetchAnalyticsReport, reportPaths } from "@/lib/jira-analytics-api";
import type { AnalyticsReportResponse } from "@/types/jira-analytics";

interface WithoutFeatureRow {
  issue_key: string;
  issue_title: string;
  project_key: string;
  project_name: string;
  type: string;
  team: string;
  hours: number;
  contributors: number;
  flags: string[];
}

interface ProjectAggregateRow {
  project_key: string;
  project_name: string;
  issue_count: number;
  hours: number;
  contributors: number;
  flags: string[];
  issues: WithoutFeatureRow[];
}

type SortKey = Exclude<keyof ProjectAggregateRow, "issues">;

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "project_key", label: "Project" },
  { key: "project_name", label: "Project Name" },
  { key: "issue_count", label: "Issues", numeric: true },
  { key: "hours", label: "Hours", numeric: true },
  { key: "contributors", label: "Contributors", numeric: true },
  { key: "flags", label: "Flags" },
];

const FLAG_LABELS: Record<string, string> = {
  missing_feature_high_effort: "High effort without feature",
  missing_feature_many_people: "Many contributors without feature",
};

const FLAG_STYLES: Record<string, string> = {
  missing_feature_high_effort: "bg-error/10 text-error",
  missing_feature_many_people: "bg-primary/10 text-primary",
};

export default function Page() {
  const defaultRange = useMemo(() => lastTwelveMonths(), []);
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const [sortKey, setSortKey] = useState<SortKey>("hours");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [expandedProjectKeys, setExpandedProjectKeys] = useState<Set<string>>(new Set());
  const [data, setData] = useState<AnalyticsReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAnalyticsReport(reportPaths.withoutFeature, {
        from: dateFrom,
        to: dateTo,
        minHours: 1,
      });
      setData(result);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    const parsed = (data?.table ?? []).map(toRow).filter((row): row is WithoutFeatureRow => row !== null);
    return aggregateByProject(parsed).sort((a, b) => compareRows(a, b, sortKey, sortDirection));
  }, [data, sortKey, sortDirection]);

  const empty = Boolean(!loading && !error && data && rows.length === 0);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "hours" || key === "contributors" || key === "issue_count" ? "desc" : "asc");
  };

  const toggleProjectExpanded = (projectKey: string) => {
    setExpandedProjectKeys((prev) => {
      const next = new Set(prev);
      if (next.has(projectKey)) {
        next.delete(projectKey);
      } else {
        next.add(projectKey);
      }
      return next;
    });
  };

  return (
    <JiraAnalyticsShell
      title="Issues without feature"
      description="Worklogged issues not in a PMGT feature family."
      hidePageHeader
      hideMethodology
    >
      <FeatureReportLayout
        activeReport="without-feature"
        title="Find work that escaped feature classification."
        description="A hygiene and capacity view for worklogged issues that consume time but are not connected to a PMGT feature family."
        metrics={<WithoutFeatureMetrics rows={rows} />}
        controls={
          <AnalyticsFilterPanel title="Filters" description="Choose the worklog window for unclassified feature-family analysis.">
            <FilterField label="From">
              <input
                type="date"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                className={filterInputClassName()}
              />
            </FilterField>
            <FilterField label="To">
              <input
                type="date"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                className={filterInputClassName()}
              />
            </FilterField>
          </AnalyticsFilterPanel>
        }
      >
        <ReportPageFrame loading={loading} error={error} empty={empty} emptyMessage="No issues without feature for the selected filters.">
          <ModernReportCard
            eyebrow="Project rollup"
            title="Issues without feature"
            description="Projects with worklogged issues outside PMGT feature families. Expand a project to inspect individual issues."
          >
            <div className="max-h-[32rem] overflow-auto rounded-2xl elevated-panel">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-surface-container-low">
                  <tr className="border-b border-outline-variant/20">
                    {COLUMNS.map((column) => (
                      <th
                        key={column.key}
                        className={`px-3 py-2 font-medium text-on-surface-variant ${
                          column.numeric ? "text-right" : "text-left"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSort(column.key)}
                          className={`inline-flex items-center gap-1 hover:text-primary ${
                            column.numeric ? "justify-end" : "justify-start"
                          }`}
                        >
                          {column.label}
                          <span className="text-[10px]">
                            {sortKey === column.key ? (sortDirection === "asc" ? "▲" : "▼") : "↕"}
                          </span>
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const expanded = expandedProjectKeys.has(row.project_key);
                    return (
                      <Fragment key={row.project_key}>
                        <tr className="border-b border-outline-variant/10 odd:bg-surface-container-lowest even:bg-surface-container-low/35 hover:bg-primary/5">
                          <td className="px-3 py-2 text-on-surface">
                            <button
                              type="button"
                              onClick={() => toggleProjectExpanded(row.project_key)}
                              className="inline-flex items-center gap-2 font-semibold hover:text-primary"
                              aria-expanded={expanded}
                            >
                              <span className="text-[10px]">{expanded ? "▼" : "▶"}</span>
                              <span>{row.project_key || "Unknown"}</span>
                            </button>
                          </td>
                          <td className="px-3 py-2 text-on-surface min-w-64">{row.project_name || "Unknown project"}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.issue_count}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.hours.toFixed(1)}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-on-surface">{row.contributors}</td>
                          <td className="px-3 py-2 text-on-surface">{renderFlags(row.flags)}</td>
                        </tr>
                        {expanded ? (
                          <tr className="border-b border-outline-variant/10 bg-surface-container-low/40">
                            <td colSpan={COLUMNS.length} className="px-3 py-3">
                              <div className="overflow-x-auto rounded-xl border border-outline-variant/20 bg-surface">
                                <table className="w-full text-xs">
                                  <thead className="bg-surface-container-low text-on-surface-variant">
                                    <tr>
                                      <th className="px-3 py-2 text-left font-medium">Issue</th>
                                      <th className="px-3 py-2 text-left font-medium">Issue Title</th>
                                      <th className="px-3 py-2 text-left font-medium">Type</th>
                                      <th className="px-3 py-2 text-left font-medium">Team</th>
                                      <th className="px-3 py-2 text-right font-medium">Hours</th>
                                      <th className="px-3 py-2 text-right font-medium">Contributors</th>
                                      <th className="px-3 py-2 text-left font-medium">Flags</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {row.issues.map((issue) => (
                                      <tr key={issue.issue_key} className="border-t border-outline-variant/10">
                                        <td className="px-3 py-2 font-medium text-on-surface">{issue.issue_key}</td>
                                        <td className="px-3 py-2 text-on-surface min-w-80">{issue.issue_title || "Untitled issue"}</td>
                                        <td className="px-3 py-2 text-on-surface">{issue.type || "Unknown"}</td>
                                        <td className="px-3 py-2 text-on-surface">{issue.team || "Unassigned"}</td>
                                        <td className="px-3 py-2 text-right tabular-nums text-on-surface">{issue.hours.toFixed(1)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums text-on-surface">{issue.contributors}</td>
                                        <td className="px-3 py-2 text-on-surface">{renderFlags(issue.flags)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </ModernReportCard>
        </ReportPageFrame>
      </FeatureReportLayout>
    </JiraAnalyticsShell>
  );
}

function WithoutFeatureMetrics({ rows }: { rows: ProjectAggregateRow[] }) {
  const issueCount = rows.reduce((sum, row) => sum + row.issue_count, 0);
  const totalHours = rows.reduce((sum, row) => sum + row.hours, 0);
  const flaggedProjects = rows.filter((row) => row.flags.length > 0).length;

  return (
    <>
      <FeatureMetricCard label="Projects" value={rows.length ? String(rows.length) : "Loading"} detail="With unclassified issues" />
      <FeatureMetricCard label="Issues" value={issueCount ? String(issueCount) : "Loading"} detail="Missing feature family" />
      <FeatureMetricCard label="Hours" value={formatCompactHours(totalHours)} detail={`${flaggedProjects} flagged project${flaggedProjects === 1 ? "" : "s"}`} />
    </>
  );
}

function lastTwelveMonths(): { from: string; to: string } {
  const today = new Date();
  const from = new Date(today.getFullYear(), today.getMonth() - 11, 1);
  return { from: formatDate(from), to: formatDate(today) };
}

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatCompactHours(value: number): string {
  if (!value) return "Loading";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} h`;
}

function toRow(row: Record<string, unknown>): WithoutFeatureRow | null {
  const issueKey = stringValue(row.issue_key);
  if (!issueKey) return null;
  return {
    issue_key: issueKey,
    issue_title: stringValue(row.issue_title),
    project_key: stringValue(row.project_key),
    project_name: stringValue(row.project_name),
    type: stringValue(row.type),
    team: stringValue(row.team),
    hours: numberValue(row.hours),
    contributors: numberValue(row.contributors),
    flags: Array.isArray(row.flags) ? row.flags.filter((flag): flag is string => typeof flag === "string") : [],
  };
}

function aggregateByProject(rows: WithoutFeatureRow[]): ProjectAggregateRow[] {
  const groups = new Map<string, ProjectAggregateRow>();
  for (const row of rows) {
    const key = row.project_key || "Unknown";
    const existing = groups.get(key);
    if (existing) {
      existing.issue_count += 1;
      existing.hours += row.hours;
      existing.contributors += row.contributors;
      existing.flags = uniqueStrings([...existing.flags, ...row.flags]);
      existing.issues.push(row);
      continue;
    }
    groups.set(key, {
      project_key: key,
      project_name: row.project_name,
      issue_count: 1,
      hours: row.hours,
      contributors: row.contributors,
      flags: uniqueStrings(row.flags),
      issues: [row],
    });
  }
  return Array.from(groups.values()).map((group) => ({
    ...group,
    issues: group.issues.sort((a, b) => b.hours - a.hours),
  }));
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values));
}

function compareRows(
  a: ProjectAggregateRow,
  b: ProjectAggregateRow,
  sortKey: SortKey,
  direction: "asc" | "desc",
): number {
  const factor = direction === "asc" ? 1 : -1;
  const aValue = sortValue(a, sortKey);
  const bValue = sortValue(b, sortKey);
  if (typeof aValue === "number" && typeof bValue === "number") {
    return (aValue - bValue) * factor;
  }
  return String(aValue).localeCompare(String(bValue), undefined, { numeric: true }) * factor;
}

function sortValue(row: ProjectAggregateRow, sortKey: SortKey): string | number {
  if (sortKey === "flags") return row.flags.map((flag) => FLAG_LABELS[flag] ?? flag).join(", ");
  return row[sortKey] as string | number;
}

function renderFlags(flags: string[]) {
  if (flags.length === 0) return <span className="text-on-surface-variant">No flags</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {flags.map((flag) => (
        <span
          key={flag}
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            FLAG_STYLES[flag] ?? "bg-surface-container-low text-on-surface-variant"
          }`}
        >
          {FLAG_LABELS[flag] ?? humanizeFlag(flag)}
        </span>
      ))}
    </div>
  );
}

function humanizeFlag(flag: string): string {
  return flag.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
