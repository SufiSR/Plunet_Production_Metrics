"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FeatureMetricCard, FeatureReportLayout } from "@/app/components/jira-analytics/FeatureReportLayout";
import { FeatureHoursFilters } from "@/app/components/jira-analytics/FeatureHoursFilters";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { JiraIssueLink, jiraBrowseUrl } from "@/app/components/jira-analytics/JiraIssueLink";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import {
  fetchFeatureFamilyHoursDrilldown,
  fetchFeatureFamilyHoursMatrix,
} from "@/lib/jira-analytics-api";
import { hoursForPeriod, normalizePeriods } from "@/lib/jira-analytics-sort";
import type {
  FeatureFamilyDrilldownFeature,
  FeatureFamilyHoursDrilldownResponse,
  FeatureFamilyHoursMatrixResponse,
  FeatureFamilyHoursMatrixRow,
} from "@/types/jira-analytics";

function formatPeriod(period: string): string {
  const [year, month] = period.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function formatHours(value: number): string {
  if (value <= 0) return "-";
  return value.toFixed(1);
}

function formatDate(value: string | null): string {
  return value ?? "-";
}

function aggregateIssueHours(
  issues: { hours_by_period: Record<string, number> }[],
  period: string,
): number {
  return issues.reduce((sum, issue) => sum + hoursForPeriod(issue.hours_by_period, period), 0);
}

export default function FeatureFamiliesPage() {
  const [months, setMonths] = useState(12);
  const [role, setRole] = useState("");
  const [team, setTeam] = useState("");
  const [matrix, setMatrix] = useState<FeatureFamilyHoursMatrixResponse | null>(null);
  const [matrixError, setMatrixError] = useState<string | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(true);
  const [selectedFamilyId, setSelectedFamilyId] = useState<number | null>(null);
  const [drilldown, setDrilldown] = useState<FeatureFamilyHoursDrilldownResponse | null>(null);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const drilldownRef = useRef<HTMLDivElement>(null);

  const loadMatrix = useCallback(async () => {
    setMatrixLoading(true);
    setMatrixError(null);
    try {
      const data = await fetchFeatureFamilyHoursMatrix({
        months,
        role: role || null,
        team: team || null,
      });
      setMatrix(data);
    } catch (err) {
      setMatrix(null);
      setMatrixError(err instanceof Error ? err.message : "Failed to load family report");
    } finally {
      setMatrixLoading(false);
    }
  }, [months, role, team]);

  const loadDrilldown = useCallback(async (familyId: number) => {
    setDrilldownLoading(true);
    setDrilldownError(null);
    try {
      const data = await fetchFeatureFamilyHoursDrilldown(familyId, {
        months,
        role: role || null,
        team: team || null,
      });
      setDrilldown(data);
    } catch (err) {
      setDrilldown(null);
      setDrilldownError(err instanceof Error ? err.message : "Failed to load drill-down");
    } finally {
      setDrilldownLoading(false);
    }
  }, [months, role, team]);

  useEffect(() => {
    void loadMatrix();
  }, [loadMatrix]);

  useEffect(() => {
    if (selectedFamilyId === null) {
      setDrilldown(null);
      return;
    }
    void loadDrilldown(selectedFamilyId);
  }, [loadDrilldown, selectedFamilyId]);

  useEffect(() => {
    if (selectedFamilyId === null || drilldownLoading) return;
    drilldownRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [drilldown, drilldownError, drilldownLoading, selectedFamilyId]);

  return (
    <JiraAnalyticsShell
      title="Feature family worklog hours"
      description="Managed feature-family rollups with feature-level drill-down."
      hidePageHeader
      hideMethodology
    >
      <FeatureReportLayout
        activeReport="families"
        title="See roadmap investment at the family level."
        description="A managed rollup above PMGT features that combines related features, dates, progress, teams, and monthly allocated hours."
        metrics={<FamilyMetrics matrix={matrix} />}
        controls={
          matrix ? (
            <FeatureHoursFilters
              months={months}
              role={role}
              team={team}
              availableRoles={matrix.available_roles}
              availableTeams={matrix.available_teams}
              onMonthsChange={setMonths}
              onRoleChange={setRole}
              onTeamChange={setTeam}
            />
          ) : null
        }
      >
        <ReportPageFrame loading={matrixLoading} error={matrixError} empty={!matrix && !matrixLoading}>
          {matrix ? (
            <div className="space-y-6">
              <FamilySummaryChart rows={matrix.rows} />
              <FamilyMatrixTable
                periods={matrix.periods}
                rows={matrix.rows}
                selectedFamilyId={selectedFamilyId}
                onSelectFamily={(familyId) =>
                  setSelectedFamilyId((prev) => (prev === familyId ? null : familyId))
                }
              />
              <div ref={drilldownRef}>
                <FamilyDrilldownPanel
                  data={drilldown}
                  jiraBaseUrl={matrix.jira_base_url}
                  loading={drilldownLoading}
                  error={drilldownError}
                  onClose={() => setSelectedFamilyId(null)}
                />
              </div>
            </div>
          ) : null}
        </ReportPageFrame>
      </FeatureReportLayout>
    </JiraAnalyticsShell>
  );
}

function FamilyMetrics({ matrix }: { matrix: FeatureFamilyHoursMatrixResponse | null }) {
  const rows = matrix?.rows ?? [];
  const totalHours = rows.reduce((sum, row) => sum + row.total_hours, 0);
  const featureCount = rows.reduce((sum, row) => sum + row.feature_count, 0);
  return (
    <>
      <FeatureMetricCard label="Families" value={rows.length ? String(rows.length) : "Loading"} detail="Managed groups with visible hours" />
      <FeatureMetricCard label="Features" value={featureCount ? String(featureCount) : "Loading"} detail="Assigned PMGT features" />
      <FeatureMetricCard label="Allocated hours" value={totalHours ? `${totalHours.toFixed(0)} h` : "Loading"} detail="Filtered family hours" />
    </>
  );
}

function FamilySummaryChart({ rows }: { rows: FeatureFamilyHoursMatrixRow[] }) {
  const topRows = [...rows].sort((a, b) => b.total_hours - a.total_hours).slice(0, 8);
  const max = Math.max(...topRows.map((row) => row.total_hours), 1);
  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-5">
      <h3 className="text-lg font-editorial font-bold text-on-surface">Largest feature families</h3>
      <div className="mt-4 space-y-3">
        {topRows.map((row) => (
          <div key={row.row_id} className="grid gap-2 md:grid-cols-[18rem_1fr_5rem] md:items-center">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-on-surface">{row.label}</div>
              <div className="text-xs text-on-surface-variant">{row.feature_count} features</div>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-surface-container-high">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.max(4, (row.total_hours / max) * 100)}%` }}
              />
            </div>
            <div className="text-right text-sm tabular-nums text-on-surface">
              {formatHours(row.total_hours)} h
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function FamilyMatrixTable({
  periods,
  rows,
  selectedFamilyId,
  onSelectFamily,
}: {
  periods: string[];
  rows: FeatureFamilyHoursMatrixRow[];
  selectedFamilyId: number | null;
  onSelectFamily: (familyId: number) => void;
}) {
  const sortedPeriods = useMemo(() => normalizePeriods(periods), [periods]);
  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => b.total_hours - a.total_hours || a.label.localeCompare(b.label)),
    [rows],
  );

  return (
    <div className="overflow-auto rounded-xl border border-outline-variant/20 bg-surface-container-lowest">
      <table className="w-full min-w-[1180px] text-sm">
        <thead className="bg-surface-container text-on-surface-variant">
          <tr>
            <th className="px-4 py-3 text-left font-label text-xs uppercase">Feature family</th>
            <th className="px-3 py-3 text-left font-label text-xs uppercase">Start</th>
            <th className="px-3 py-3 text-left font-label text-xs uppercase">Target</th>
            <th className="px-3 py-3 text-left font-label text-xs uppercase">Progress</th>
            <th className="px-3 py-3 text-left font-label text-xs uppercase">Teams</th>
            {sortedPeriods.map((period) => (
              <th key={period} className="px-3 py-3 text-right font-label text-xs uppercase">
                {formatPeriod(period)}
              </th>
            ))}
            <th className="px-4 py-3 text-right font-label text-xs uppercase">Total</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => {
            const selected = row.family_id === selectedFamilyId;
            return (
              <tr
                key={row.row_id}
                onClick={() => onSelectFamily(row.family_id)}
                className={`cursor-pointer border-t border-outline-variant/28 ${
                  selected ? "bg-primary-container/20" : "hover:bg-surface-container-low/60"
                }`}
              >
                <td className="px-4 py-3 align-top">
                  <div className="font-medium text-on-surface">{row.label}</div>
                  <div className="text-xs text-on-surface-variant">{row.feature_count} features</div>
                </td>
                <td className="px-3 py-3 text-on-surface-variant">{formatDate(row.start_date)}</td>
                <td className="px-3 py-3 text-on-surface-variant">{formatDate(row.target_end_date)}</td>
                <td className="px-3 py-3 text-on-surface-variant">{row.delivery_progress ?? "-"}</td>
                <td className="px-3 py-3 text-on-surface-variant">{row.team_names.join(", ") || "-"}</td>
                {sortedPeriods.map((period) => (
                  <td key={period} className="px-3 py-3 text-right tabular-nums">
                    {formatHours(hoursForPeriod(row.hours_by_period, period))}
                  </td>
                ))}
                <td className="px-4 py-3 text-right font-semibold tabular-nums">
                  {formatHours(row.total_hours)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FamilyDrilldownPanel({
  data,
  jiraBaseUrl,
  loading,
  error,
  onClose,
}: {
  data: FeatureFamilyHoursDrilldownResponse | null;
  jiraBaseUrl: string;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  if (!data && !loading && !error) {
    return (
      <div className="rounded-xl border border-dashed border-outline-variant/30 bg-surface-container-low p-8 text-center text-on-surface-variant text-sm">
        Select a feature family to see the participating features and issue drill-down.
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest">
      <div className="flex items-start justify-between gap-4 border-b border-outline-variant/28 px-4 py-3">
        <div>
          <h3 className="text-base font-editorial font-bold text-on-surface">
            {data?.row_label ?? "Feature family drill-down"}
          </h3>
          {data ? (
            <p className="text-sm text-on-surface-variant">
              {data.features.length} participating features.
            </p>
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
      <div className="space-y-4 p-4">
        {loading ? <p className="text-sm text-on-surface-variant">Loading drill-down...</p> : null}
        {error ? <p className="text-sm text-error">{error}</p> : null}
        {data && !loading && !error ? (
          data.features.length ? (
            data.features.map((feature) => (
              <FeatureDrilldownBlock
                key={feature.root_key}
                feature={feature}
                periods={data.periods}
                jiraBaseUrl={jiraBaseUrl}
              />
            ))
          ) : (
            <p className="text-sm text-on-surface-variant">No feature hours in this period.</p>
          )
        ) : null}
      </div>
    </section>
  );
}

function FeatureDrilldownBlock({
  feature,
  periods,
  jiraBaseUrl,
}: {
  feature: FeatureFamilyDrilldownFeature;
  periods: string[];
  jiraBaseUrl: string;
}) {
  const sortedPeriods = normalizePeriods(periods);
  return (
    <details className="rounded-xl border border-outline-variant/20 bg-surface-container-low" open>
      <summary className="cursor-pointer px-4 py-3">
        <span className="font-medium text-on-surface">{feature.feature_name}</span>{" "}
        <JiraIssueLink
          issueKey={feature.root_key}
          issueUrl={feature.row_url ?? jiraBrowseUrl(jiraBaseUrl, feature.root_key)}
          jiraBaseUrl={jiraBaseUrl}
          className="text-xs"
        />
        <span className="ml-2 text-xs text-on-surface-variant">
          {feature.delivery_progress ?? "Progress not set"}, team {feature.team_name ?? "not assigned"}
        </span>
      </summary>
      <div className="overflow-auto px-4 pb-4">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="text-on-surface-variant">
            <tr>
              <th className="py-2 pr-4 text-left font-label text-xs uppercase">Group / issue</th>
              {sortedPeriods.map((period) => (
                <th key={period} className="px-2 py-2 text-right font-label text-xs uppercase">
                  {formatPeriod(period)}
                </th>
              ))}
              <th className="px-2 py-2 text-right font-label text-xs uppercase">Total</th>
            </tr>
          </thead>
          <tbody>
            {feature.sections.map((section) => (
              <Fragment key={`section-${section.epic_key ?? section.epic_summary ?? "other"}`}>
                <tr className="border-t border-outline-variant/20">
                  <td className="py-2 pr-4 font-semibold text-on-surface">
                    {section.epic_key ? (
                      <JiraIssueLink
                        issueKey={section.epic_key}
                        issueUrl={section.epic_url ?? jiraBrowseUrl(jiraBaseUrl, section.epic_key)}
                        jiraBaseUrl={jiraBaseUrl}
                      />
                    ) : (
                      section.epic_summary ?? "Other linked issues"
                    )}
                  </td>
                  {sortedPeriods.map((period) => (
                    <td key={period} className="px-2 py-2 text-right tabular-nums font-semibold">
                      {formatHours(aggregateIssueHours(section.issues, period))}
                    </td>
                  ))}
                  <td className="px-2 py-2 text-right tabular-nums font-semibold">
                    {formatHours(section.total_hours)}
                  </td>
                </tr>
                {section.issues.map((issue) => (
                  <tr key={`${section.epic_key ?? "other"}-${issue.issue_key}`} className="border-t border-outline-variant/10">
                    <td className="py-2 pr-4">
                      <JiraIssueLink
                        issueKey={issue.issue_key}
                        issueUrl={issue.issue_url}
                        jiraBaseUrl={jiraBaseUrl}
                      />
                      <div className="line-clamp-1 text-xs text-on-surface-variant">
                        {issue.summary ?? issue.issue_type_name ?? "-"}
                      </div>
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
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

