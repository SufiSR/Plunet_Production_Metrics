"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import {
  fetchAllocationRebuildStatus,
  fetchDataQuality,
  fetchDataQualityUserDrilldown,
  ignoreDataQualityUser,
  rebuildAllocation,
  unignoreDataQualityUser,
} from "@/lib/jira-analytics-api";
import { compareSortableValues, nextSortState, type SortState } from "@/lib/jira-analytics-sort";
import type {
  DataQualityCheck,
  DataQualityResponse,
  DataQualityUserDrilldownResponse,
  DataQualityUserDrilldownRow,
} from "@/types/jira-analytics";

type WarningSortKey = "label" | "count" | "ignored_count" | "severity" | "affected_hours";

const USER_DRILLDOWN_CHECKS = [
  "worklog_users_without_assignment",
  "reporting_excluded_users_with_worklogs",
] as const;

const USER_CHECK_LABELS: Record<(typeof USER_DRILLDOWN_CHECKS)[number], string> = {
  worklog_users_without_assignment: "Worklog users without active role assignment",
  reporting_excluded_users_with_worklogs: "Reporting-excluded users have worklogs in scope",
};

function isUserDrilldownCheck(checkId: string): checkId is (typeof USER_DRILLDOWN_CHECKS)[number] {
  return USER_DRILLDOWN_CHECKS.includes(checkId as (typeof USER_DRILLDOWN_CHECKS)[number]);
}

function severityClass(severity: string): string {
  if (severity === "high") return "text-error font-medium";
  if (severity === "medium") return "text-amber-700 dark:text-amber-400";
  return "text-on-surface-variant";
}

export default function DataQualityPage() {
  const [data, setData] = useState<DataQualityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<SortState<WarningSortKey> | null>(null);
  const [rebuildState, setRebuildState] = useState<"idle" | "running" | "success" | "error">("idle");
  const [rebuildMessage, setRebuildMessage] = useState<string | null>(null);
  const [selectedCheckId, setSelectedCheckId] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<DataQualityUserDrilldownResponse | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);
  const [actionUserId, setActionUserId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDataQuality());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const warnings = data?.data_quality?.warnings ?? [];
  const sortedWarnings = useMemo(() => {
    if (!sort) return warnings;
    return [...warnings].sort((a, b) =>
      compareSortableValues(warningSortValue(a, sort.key), warningSortValue(b, sort.key), sort.direction),
    );
  }, [sort, warnings]);

  async function handleRebuildAllocation() {
    setRebuildState("running");
    setRebuildMessage(null);
    try {
      const result = await rebuildAllocation();
      if (result.state === "running") {
        setRebuildState("running");
        setRebuildMessage("Full allocation rebuild started. This can take about a minute for all historical worklog months.");
        return;
      }
      setRebuildState("success");
      setRebuildMessage(
        `Rebuilt ${result.allocation_rows} allocation rows across ${result.periods.length} month${result.periods.length === 1 ? "" : "s"}.`,
      );
      await loadData();
    } catch (e) {
      setRebuildState("error");
      setRebuildMessage(e instanceof Error ? e.message : "Allocation rebuild failed");
    }
  }

  useEffect(() => {
    if (rebuildState !== "running") return;
    const timer = window.setInterval(() => {
      void fetchAllocationRebuildStatus()
        .then(async (status) => {
          if (status.state === "running") return;
          if (status.state === "succeeded") {
            setRebuildState("success");
            setRebuildMessage(
              `Rebuilt ${status.allocation_rows} allocation rows across ${status.periods.length} month${status.periods.length === 1 ? "" : "s"}.`,
            );
            await loadData();
            return;
          }
          if (status.state === "failed") {
            setRebuildState("error");
            setRebuildMessage(status.error ?? "Allocation rebuild failed");
          }
        })
        .catch((e) => {
          setRebuildState("error");
          setRebuildMessage(e instanceof Error ? e.message : "Failed to read rebuild status");
        });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [loadData, rebuildState]);

  async function loadUserDrilldown(checkId: string) {
    setSelectedCheckId(checkId);
    setDrilldownLoading(true);
    setDrilldownError(null);
    try {
      setDrilldown(await fetchDataQualityUserDrilldown(checkId));
    } catch (e) {
      setDrilldownError(e instanceof Error ? e.message : "Failed to load user drilldown");
      setDrilldown(null);
    } finally {
      setDrilldownLoading(false);
    }
  }

  async function handleIgnoreUser(row: DataQualityUserDrilldownRow) {
    if (row.user_id == null || !selectedCheckId) return;
    setActionUserId(row.user_id);
    setDrilldownError(null);
    try {
      setDrilldown(await ignoreDataQualityUser(selectedCheckId, row.user_id));
      await loadData();
    } catch (e) {
      setDrilldownError(e instanceof Error ? e.message : "Failed to ignore user");
    } finally {
      setActionUserId(null);
    }
  }

  async function handleUnignoreUser(row: DataQualityUserDrilldownRow) {
    if (row.user_id == null || !selectedCheckId) return;
    setActionUserId(row.user_id);
    setDrilldownError(null);
    try {
      setDrilldown(await unignoreDataQualityUser(selectedCheckId, row.user_id));
      await loadData();
    } catch (e) {
      setDrilldownError(e instanceof Error ? e.message : "Failed to unignore user");
    } finally {
      setActionUserId(null);
    }
  }

  return (
    <JiraAnalyticsShell
      title="Data quality"
      description="Missing mappings and suspicious data that affect report trust."
    >
      <section className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-on-surface">Rebuild time allocation</h2>
          <p className="text-xs text-on-surface-variant max-w-3xl">
            Recalculate monthly allocated effort after Jira worklogs, HR Works hours, user role assignments,
            or reporting exclusions change. This rebuilds all worklog months and updates the allocated-time
            reports that depend on
            <span className="font-mono"> monthly_allocated_effort</span>.
          </p>
          {rebuildMessage ? (
            <p className={`text-xs ${rebuildState === "error" ? "text-error" : "text-secondary"}`}>
              {rebuildMessage}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => void handleRebuildAllocation()}
          disabled={rebuildState === "running"}
          className="shrink-0 rounded-xl bg-primary px-4 py-2 text-xs font-label uppercase tracking-wide text-on-primary disabled:opacity-50"
        >
          {rebuildState === "running" ? "Rebuilding..." : "Rebuild allocation"}
        </button>
      </section>
      <section className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-4 space-y-3">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-on-surface">User health drilldowns</h2>
          <p className="text-xs text-on-surface-variant max-w-3xl">
            Inspect users behind assignment and reporting-exclusion warnings. Ignored users are
            suppressed from data-quality counts but remain visible here for audit and reversal.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {USER_DRILLDOWN_CHECKS.map((checkId) => (
            <button
              key={checkId}
              type="button"
              onClick={() => void loadUserDrilldown(checkId)}
              className={`rounded-xl border px-3 py-2 text-xs font-label uppercase tracking-wide ${
                selectedCheckId === checkId
                  ? "border-primary bg-primary-container text-on-primary-container"
                  : "border-outline-variant/40 bg-surface-container-lowest text-on-surface"
              }`}
            >
              {USER_CHECK_LABELS[checkId]}
            </button>
          ))}
        </div>
      </section>
      <ReportPageFrame loading={loading} error={error}>
        <div className="space-y-6">
          <div className="overflow-x-auto rounded-xl border border-outline-variant/20">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-outline-variant/20 bg-surface-container-low">
                  <SortableHeader
                    label="Check"
                    sortKey="label"
                    activeSort={sort}
                    onSort={(key) => setSort(nextSortState(sort, key))}
                  />
                  <SortableHeader
                    label="Count"
                    sortKey="count"
                    numeric
                    activeSort={sort}
                    onSort={(key) => setSort(nextSortState(sort, key))}
                  />
                  <SortableHeader
                    label="Ignored"
                    sortKey="ignored_count"
                    numeric
                    activeSort={sort}
                    onSort={(key) => setSort(nextSortState(sort, key))}
                  />
                  <SortableHeader
                    label="Severity"
                    sortKey="severity"
                    activeSort={sort}
                    onSort={(key) => setSort(nextSortState(sort, key))}
                  />
                  <SortableHeader
                    label="Affected hours"
                    sortKey="affected_hours"
                    numeric
                    activeSort={sort}
                    onSort={(key) => setSort(nextSortState(sort, key))}
                  />
                  <th className="px-3 py-2 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedWarnings.length === 0 ? (
                  <tr>
                    <td className="px-3 py-4 text-on-surface-variant" colSpan={6}>
                      No active data quality issues detected.
                    </td>
                  </tr>
                ) : (
                  sortedWarnings.map((w) => (
                    <tr key={w.check_id} className="border-b border-outline-variant/10">
                      <td className="px-3 py-2">{w.label}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{w.count}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{w.ignored_count ?? 0}</td>
                      <td className={`px-3 py-2 capitalize ${severityClass(w.severity)}`}>{w.severity}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{w.affected_hours ?? "—"}</td>
                      <td className="px-3 py-2">
                        {isUserDrilldownCheck(w.check_id) ? (
                          <button
                            type="button"
                            onClick={() => void loadUserDrilldown(w.check_id)}
                            className="rounded-lg border border-outline-variant/40 px-3 py-1 text-xs text-primary hover:bg-primary-container/20"
                          >
                            View users
                          </button>
                        ) : (
                          <span className="text-xs text-on-surface-variant">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <UserDrilldownPanel
            selectedCheckId={selectedCheckId}
            drilldown={drilldown}
            loading={drilldownLoading}
            error={drilldownError}
            actionUserId={actionUserId}
            onIgnore={handleIgnoreUser}
            onUnignore={handleUnignoreUser}
          />
        </div>
      </ReportPageFrame>
    </JiraAnalyticsShell>
  );
}

function warningSortValue(warning: DataQualityCheck, key: WarningSortKey): string | number | null {
  if (key === "affected_hours") return warning.affected_hours ?? null;
  if (key === "ignored_count") return warning.ignored_count ?? 0;
  if (key === "severity") return severityRank(warning.severity);
  return warning[key];
}

function severityRank(severity: DataQualityCheck["severity"]): number {
  if (severity === "high") return 3;
  if (severity === "medium") return 2;
  return 1;
}

function SortableHeader({
  label,
  sortKey,
  numeric = false,
  activeSort,
  onSort,
}: {
  label: string;
  sortKey: WarningSortKey;
  numeric?: boolean;
  activeSort: SortState<WarningSortKey> | null;
  onSort: (key: WarningSortKey) => void;
}) {
  const direction = activeSort?.key === sortKey ? activeSort.direction : null;
  return (
    <th className={`px-3 py-2 ${numeric ? "text-right" : "text-left"}`}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 hover:text-on-surface ${numeric ? "justify-end" : "justify-start"}`}
      >
        <span>{label}</span>
        <span className="text-[10px]">{direction === "asc" ? "▲" : direction === "desc" ? "▼" : "↕"}</span>
      </button>
    </th>
  );
}

function UserDrilldownPanel({
  selectedCheckId,
  drilldown,
  loading,
  error,
  actionUserId,
  onIgnore,
  onUnignore,
}: {
  selectedCheckId: string | null;
  drilldown: DataQualityUserDrilldownResponse | null;
  loading: boolean;
  error: string | null;
  actionUserId: number | null;
  onIgnore: (row: DataQualityUserDrilldownRow) => void;
  onUnignore: (row: DataQualityUserDrilldownRow) => void;
}) {
  if (!selectedCheckId) {
    return (
      <p className="text-xs text-on-surface-variant">
        Select a user health drilldown to inspect affected users.
      </p>
    );
  }
  if (loading) {
    return <p className="text-xs text-on-surface-variant">Loading users...</p>;
  }
  if (error) {
    return <p className="text-xs text-error">{error}</p>;
  }
  if (!drilldown) return null;

  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-on-surface">{drilldown.label}</h2>
          <p className="text-xs text-on-surface-variant">
            {drilldown.active_count} active user{drilldown.active_count === 1 ? "" : "s"};{" "}
            {drilldown.ignored_count} ignored user{drilldown.ignored_count === 1 ? "" : "s"}.
          </p>
        </div>
        <Link href="/admin/jira-analytics/assignments" className="text-xs font-medium text-primary hover:underline">
          Open user assignments
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-sm">
          <thead>
            <tr className="border-b border-outline-variant/20 text-left text-on-surface-variant">
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Role / team</th>
              <th className="px-3 py-2 text-right">Worklogs</th>
              <th className="px-3 py-2 text-right">Hours</th>
              <th className="px-3 py-2">Range</th>
              <th className="px-3 py-2">Reporting</th>
              <th className="px-3 py-2">Health state</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {drilldown.users.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-on-surface-variant" colSpan={8}>
                  No users found for this health check.
                </td>
              </tr>
            ) : (
              drilldown.users.map((row) => (
                <tr key={`${row.account_id}-${row.user_id ?? "missing"}`} className="border-b border-outline-variant/10">
                  <td className="px-3 py-2">
                    <div className="font-medium text-on-surface">{row.display_name ?? row.account_id}</div>
                    <div className="text-[11px] text-on-surface-variant">{row.email_address ?? row.account_id}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div>{row.role_name ?? "No active role"}</div>
                    <div className="text-[11px] text-on-surface-variant">{row.team_name ?? "No team"}</div>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.worklog_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.total_hours.toFixed(2)}</td>
                  <td className="px-3 py-2 text-xs text-on-surface-variant">
                    {formatDate(row.first_worklog_at)} - {formatDate(row.last_worklog_at)}
                  </td>
                  <td className="px-3 py-2">{row.reporting_excluded ? "Excluded" : "Active"}</td>
                  <td className="px-3 py-2">
                    {row.ignored ? (
                      <span className="text-secondary">Ignored</span>
                    ) : (
                      <span className="text-error">Active finding</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {row.ignored ? (
                      <button
                        type="button"
                        disabled={actionUserId === row.user_id}
                        onClick={() => onUnignore(row)}
                        className="rounded-lg border border-outline-variant/40 px-3 py-1 text-xs text-primary disabled:opacity-50"
                      >
                        {actionUserId === row.user_id ? "Saving..." : "Unignore"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={!row.can_ignore || actionUserId === row.user_id}
                        onClick={() => onIgnore(row)}
                        className="rounded-lg border border-outline-variant/40 px-3 py-1 text-xs text-primary disabled:opacity-50"
                      >
                        {actionUserId === row.user_id ? "Saving..." : "Ignore in health"}
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString();
}
