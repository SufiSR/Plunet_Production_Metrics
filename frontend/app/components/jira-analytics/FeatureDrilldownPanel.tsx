"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import type {
  FeatureHoursDrilldownIssue,
  FeatureHoursDrilldownResponse,
  FeatureHoursDrilldownSection,
} from "@/types/jira-analytics";
import {
  JiraIssueLink,
  jiraBrowseUrl,
  normalizeJiraIssueUrl,
} from "@/app/components/jira-analytics/JiraIssueLink";
import {
  compareDrilldownIssues,
  compareSortableValues,
  hoursForPeriod,
  nextSortState,
  normalizePeriods,
  type SortState,
} from "@/lib/jira-analytics-sort";

function formatPeriod(period: string): string {
  const [year, month] = period.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function formatHours(value: number): string {
  if (value <= 0) return "—";
  return value.toFixed(1);
}

interface FeatureDrilldownPanelProps {
  data: FeatureHoursDrilldownResponse | null;
  jiraBaseUrl: string;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

interface SortedIssueRow {
  issue: FeatureHoursDrilldownIssue;
  section: FeatureHoursDrilldownSection;
}

interface SortedSectionRows {
  section: FeatureHoursDrilldownSection;
  issues: FeatureHoursDrilldownIssue[];
  hoursByPeriod: Record<string, number>;
}

type DrilldownSortKey = "issue" | "group" | "total" | `period:${string}`;

export function FeatureDrilldownPanel({
  data,
  jiraBaseUrl,
  loading,
  error,
  onClose,
}: FeatureDrilldownPanelProps) {
  const [sort, setSort] = useState<SortState<DrilldownSortKey> | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => new Set());
  const sortedPeriods = useMemo(
    () => normalizePeriods(data?.periods ?? []),
    [data?.periods],
  );
  const sortedSections = useMemo<SortedSectionRows[]>(() => {
    if (!data) return [];
    const sections = data.sections.map((section) => {
      const rows = section.issues
        .filter((issue) => issue.total_hours > 0)
        .sort((a, b) => compareDrilldownIssues(a, b, sortedPeriods));
      const issues = sort && sort.key !== "group"
        ? [...rows].sort((a, b) =>
            compareSortableValues(
              drilldownSortValue({ issue: a, section }, sort.key),
              drilldownSortValue({ issue: b, section }, sort.key),
              sort.direction,
            ),
          )
        : rows;
      return {
        section,
        issues,
        hoursByPeriod: aggregateSectionHours(rows, sortedPeriods),
      };
    }).filter((section) => section.issues.length > 0);

    if (sort?.key === "group") {
      return [...sections].sort((a, b) =>
        compareSortableValues(sectionSortLabel(a.section), sectionSortLabel(b.section), sort.direction),
      );
    }
    return sections;
  }, [data, sort, sortedPeriods]);
  const issueCount = sortedSections.reduce((count, section) => count + section.issues.length, 0);
  const title = data?.row_label ?? "Drill-down";

  useEffect(() => {
    setExpandedSections(new Set());
  }, [data?.row_id]);

  const toggleSection = (sectionKey: string) => {
    setExpandedSections((current) => {
      const next = new Set(current);
      if (next.has(sectionKey)) {
        next.delete(sectionKey);
      } else {
        next.add(sectionKey);
      }
      return next;
    });
  };

  if (!data && !loading && !error) {
    return (
      <div className="rounded-xl border border-dashed border-outline-variant/30 bg-surface-container-low p-8 text-center text-on-surface-variant text-sm">
        Select a feature or Other row to see contributing issues with monthly hours.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest flex flex-col max-h-[70vh]">
      <div className="flex items-start justify-between gap-4 px-4 py-3 border-b border-outline-variant/28">
        <div>
          <h3 className="text-base font-editorial font-bold text-on-surface">
            {data?.row_url && data.feature_root_key ? (
              <a
                href={normalizeJiraIssueUrl(data.row_url, data.feature_root_key, jiraBaseUrl)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {title}
              </a>
            ) : (
              title
            )}
          </h3>
          {data?.feature_summary ? (
            <p className="text-sm text-on-surface-variant mt-0.5">{data.feature_summary}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 hover:bg-surface-container-high text-on-surface-variant"
          aria-label="Close drill-down"
        >
          <span className="material-symbols-outlined text-[20px]">close</span>
        </button>
      </div>

      <div className="overflow-auto flex-1 p-4">
        {loading ? (
          <p className="text-sm text-on-surface-variant">Loading drill-down…</p>
        ) : null}
        {error ? <p className="text-sm text-error">{error}</p> : null}
        {data && !loading && !error ? (
          issueCount === 0 ? (
            <p className="text-sm text-on-surface-variant">No issues with logged hours in this period.</p>
          ) : (
            <div className="overflow-auto">
              <table className="min-w-full text-sm border-collapse">
                <thead>
                  <tr className="text-on-surface-variant">
                    <th className="text-left py-2 pr-4 font-label text-xs uppercase">
                      <SortButton
                        label="Issue"
                        sortKey="issue"
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                    </th>
                    <th className="text-left py-2 pr-4 font-label text-xs uppercase">
                      <SortButton
                        label="Group"
                        sortKey="group"
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                    </th>
                    {sortedPeriods.map((period) => (
                      <th key={period} className="text-right px-2 py-2 font-label text-xs uppercase">
                        <SortButton
                          label={formatPeriod(period)}
                          sortKey={`period:${period}`}
                          numeric
                          activeSort={sort}
                          onSort={(key) => setSort(nextSortState(sort, key))}
                        />
                      </th>
                    ))}
                    <th className="text-right px-2 py-2 font-label text-xs uppercase">
                      <SortButton
                        label="Total"
                        sortKey="total"
                        numeric
                        activeSort={sort}
                        onSort={(key) => setSort(nextSortState(sort, key))}
                      />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSections.map(({ section, issues, hoursByPeriod }) => {
                    const key = sectionKey(section);
                    const isExpanded = expandedSections.has(key);
                    return (
                    <Fragment key={`section-fragment-${key}`}>
                      <tr
                        key={`section-${key}`}
                        className="border-t border-outline-variant/20 bg-surface-container-low/70"
                      >
                        <td colSpan={2} className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => toggleSection(key)}
                            aria-expanded={isExpanded}
                            className="flex w-full items-center gap-2 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant hover:text-on-surface"
                          >
                            <span className="material-symbols-outlined text-[18px]">
                              {isExpanded ? "expand_more" : "chevron_right"}
                            </span>
                            <span>
                              {section.epic_key && section.epic_url ? (
                                <>
                                  Epic{" "}
                                  <JiraIssueLink
                                    issueKey={section.epic_key}
                                    issueUrl={section.epic_url}
                                    jiraBaseUrl={jiraBaseUrl}
                                    className="text-xs"
                                  />
                                  {section.epic_summary ? ` - ${section.epic_summary}` : ""}
                                </>
                              ) : (
                                (section.epic_summary ?? "Other issues")
                              )}
                            </span>
                            <span className="normal-case text-[11px] font-normal text-on-surface-variant">
                              {issues.length} issues
                            </span>
                          </button>
                        </td>
                        {sortedPeriods.map((period) => (
                          <td key={period} className="px-2 py-2 text-right tabular-nums font-semibold">
                            {formatHours(hoursForPeriod(hoursByPeriod, period))}
                          </td>
                        ))}
                        <td className="px-2 py-2 text-right tabular-nums font-semibold">
                          {formatHours(section.total_hours)}
                        </td>
                      </tr>
                      {isExpanded ? issues.map((issue) => (
                        <tr key={`${section.epic_key ?? section.epic_summary ?? "other"}-${issue.issue_key}`} className="border-t border-outline-variant/10">
                          <td className="py-2 pr-4">
                            <div>
                              <JiraIssueLink
                                issueKey={issue.issue_key}
                                issueUrl={issue.issue_url}
                                jiraBaseUrl={jiraBaseUrl}
                              />
                              <div className="text-xs text-on-surface-variant line-clamp-1">
                                {issue.summary ?? issue.issue_type_name ?? "—"}
                              </div>
                              {issue.multi_feature ? (
                                <div className="text-[10px] text-tertiary mt-0.5 flex flex-wrap items-center gap-1">
                                  <span className="material-symbols-outlined text-[14px]">link</span>
                                  <span>Also in:</span>
                                  {issue.other_feature_keys.map((key, index) => (
                                    <span key={key}>
                                      {index > 0 ? ", " : null}
                                      <JiraIssueLink
                                        issueKey={key}
                                        issueUrl={jiraBrowseUrl(jiraBaseUrl, key)}
                                        jiraBaseUrl={jiraBaseUrl}
                                        className="text-[10px] font-normal"
                                      />
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          </td>
                          <td className="py-2 pr-4 text-xs text-on-surface-variant">
                            {issue.issue_type_name ?? "Issue"}
                          </td>
                          {sortedPeriods.map((period) => (
                            <td key={period} className="px-2 py-2 text-right tabular-nums">
                              {formatHours(hoursForPeriod(issue.hours_by_period, period))}
                            </td>
                          ))}
                          <td className="px-2 py-2 text-right tabular-nums font-medium">
                            {formatHours(issue.total_hours)}
                          </td>
                        </tr>
                      )) : null}
                    </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : null}
      </div>
    </div>
  );
}

function drilldownSortValue(row: SortedIssueRow, key: DrilldownSortKey): string | number {
  if (key === "issue") return row.issue.issue_key;
  if (key === "group") return sectionSortLabel(row.section);
  if (key === "total") return row.issue.total_hours;
  return hoursForPeriod(row.issue.hours_by_period, key.slice("period:".length));
}

function sectionSortLabel(section: FeatureHoursDrilldownSection): string {
  return section.epic_key ?? section.epic_summary ?? "Other issues";
}

function sectionKey(section: FeatureHoursDrilldownSection): string {
  return section.epic_key ?? section.epic_summary ?? "other";
}

function aggregateSectionHours(
  issues: FeatureHoursDrilldownIssue[],
  periods: string[],
): Record<string, number> {
  const totals = Object.fromEntries(periods.map((period) => [period, 0]));
  for (const issue of issues) {
    for (const period of periods) {
      totals[period] = Number((totals[period] + hoursForPeriod(issue.hours_by_period, period)).toFixed(2));
    }
  }
  return totals;
}

function SortButton({
  label,
  sortKey,
  numeric = false,
  activeSort,
  onSort,
}: {
  label: string;
  sortKey: DrilldownSortKey;
  numeric?: boolean;
  activeSort: SortState<DrilldownSortKey> | null;
  onSort: (key: DrilldownSortKey) => void;
}) {
  const direction = activeSort?.key === sortKey ? activeSort.direction : null;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={`inline-flex items-center gap-1 hover:text-on-surface ${numeric ? "justify-end" : "justify-start"}`}
    >
      <span>{label}</span>
      <span className="text-[10px]">{direction === "asc" ? "▲" : direction === "desc" ? "▼" : "↕"}</span>
    </button>
  );
}
