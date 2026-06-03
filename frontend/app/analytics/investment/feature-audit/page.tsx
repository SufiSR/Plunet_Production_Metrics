"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnalyticsFilterPanel, FilterField, filterInputClassName } from "@/app/components/jira-analytics/AnalyticsReportControls";
import { InvestmentMetricCard, InvestmentReportLayout } from "@/app/components/jira-analytics/InvestmentReportLayout";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { ReportPageFrame } from "@/app/components/jira-analytics/ReportPageFrame";
import {
  downloadFeatureInvestmentAuditExport,
  fetchFeatureInvestmentAudit,
  fetchFeatureInvestmentAuditIssues,
  fetchFeatureInvestmentAuditWorklogs,
} from "@/lib/jira-analytics-api";
import { lastSixMonths, lastTwoYearsToDate, lastYear, thisYearToDate } from "@/lib/jira-analytics-dates";
import { compareSortableValues, nextSortState, normalizePeriods, SortState } from "@/lib/jira-analytics-sort";
import type {
  AnalyticsReportResponse,
  FeatureInvestmentAuditIssueRow,
  FeatureInvestmentAuditRow,
  FeatureInvestmentAuditWorklogRow,
  ReportQueryParams,
} from "@/types/jira-analytics";

type PresetId = "last-six-months" | "this-year" | "last-year" | "last-two-years";

const PRESETS: { id: PresetId; label: string; range: () => { from: string; to: string } }[] = [
  { id: "last-six-months", label: "6 months", range: lastSixMonths },
  { id: "this-year", label: "This year", range: thisYearToDate },
  { id: "last-year", label: "Last year", range: lastYear },
  { id: "last-two-years", label: "Last 2 years", range: lastTwoYearsToDate },
];

const OTHER_FAMILY_IDENTIFIER = "__other__";
const OTHER_FAMILY_NAME = "Other";
const GENERIC_FEATURE_LABELS: Record<string, string> = {
  "__other_bug__": "Other Bug",
  "__other_feature__": "Other Feature",
  "__other_misc__": "Other Technical Task",
};

export default function FeatureInvestmentAuditPage() {
  const initialRange = useMemo(() => lastSixMonths(), []);
  const [params, setParams] = useState<ReportQueryParams>(initialRange);
  const [data, setData] = useState<AnalyticsReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [selectedRow, setSelectedRow] = useState<FeatureInvestmentAuditRow | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(null);
  const [issues, setIssues] = useState<FeatureInvestmentAuditIssueRow[]>([]);
  const [worklogs, setWorklogs] = useState<FeatureInvestmentAuditWorklogRow[]>([]);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFeatureInvestmentAudit(params);
      setData(result);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Failed to load feature investment audit");
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    const parsed = (data?.table ?? []).map(toAuditRow).filter((row): row is FeatureInvestmentAuditRow => row !== null);
    return aggregateAuditRows(parsed);
  }, [data]);

  const periods = useMemo(() => {
    const value = data?.filters?.periods;
    return Array.isArray(value) ? normalizePeriods(value.filter((item): item is string => typeof item === "string")) : [];
  }, [data]);

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return rows;
    return rows.filter(
      (row) =>
        row.feature_identifier.toLowerCase().includes(normalized) ||
        row.feature_name.toLowerCase().includes(normalized) ||
        row.family_name.toLowerCase().includes(normalized),
    );
  }, [query, rows]);

  const loadIssues = async (row: FeatureInvestmentAuditRow, period?: string | null) => {
    setSelectedRow(row);
    setSelectedPeriod(period ?? null);
    setWorklogs([]);
    setDrilldownError(null);
    try {
      const result = await fetchFeatureInvestmentAuditIssues({
        ...params,
        featureKey: row.feature_identifier,
        familyId: isGenericFeature(row.feature_identifier) ? undefined : row.family_identifier,
        issueKey: undefined,
        mode: undefined,
        ...(period ? { from: period, to: period } : {}),
      });
      setIssues(
        (result.table ?? [])
          .map(toIssueRow)
          .filter((item): item is FeatureInvestmentAuditIssueRow => item !== null),
      );
    } catch (err) {
      setIssues([]);
      setDrilldownError(err instanceof Error ? err.message : "Failed to load issue drilldown");
    }
  };

  const loadWorklogs = async (issue: FeatureInvestmentAuditIssueRow) => {
    setDrilldownError(null);
    try {
      const result = await fetchFeatureInvestmentAuditWorklogs({
        ...params,
        issueKey: issue.issue_identifier,
        ...(selectedPeriod ? { from: selectedPeriod, to: selectedPeriod } : {}),
      });
      setWorklogs(
        (result.table ?? [])
          .map(toWorklogRow)
          .filter((item): item is FeatureInvestmentAuditWorklogRow => item !== null),
      );
    } catch (err) {
      setWorklogs([]);
      setDrilldownError(err instanceof Error ? err.message : "Failed to load worklog drilldown");
    }
  };

  const applyPreset = (preset: PresetId) => {
    const range = PRESETS.find((item) => item.id === preset)?.range();
    if (range) setParams((prev) => ({ ...prev, ...range }));
  };

  const exportWorkbook = async () => {
    setExporting(true);
    setDrilldownError(null);
    try {
      const blob = await downloadFeatureInvestmentAuditExport(params);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `feature-investment-audit-${params.from ?? "from"}-to-${params.to ?? "to"}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setDrilldownError(err instanceof Error ? err.message : "Failed to export workbook");
    } finally {
      setExporting(false);
    }
  };

  const empty = Boolean(!loading && !error && data && rows.length === 0);

  return (
    <JiraAnalyticsShell
      title="Feature investment audit"
      description="Booked and calculated feature investment by month with issue and worklog drilldown."
      hidePageHeader
      hideMethodology
    >
      <InvestmentReportLayout
        activeReport="feature-audit"
        title="Audit feature investment from capacity to clocked hours."
        description="A monthly leaderboard that connects feature families, features, issues, people, HRWorks hours, and calculated investment."
        metrics={<AuditMetrics rows={rows} visibleRows={filteredRows.length} />}
        controls={
          <AuditFilters
            params={params}
            data={data}
            query={query}
            exporting={exporting}
            onParamsChange={setParams}
            onQueryChange={setQuery}
            onPreset={applyPreset}
            onExport={exportWorkbook}
          />
        }
      >
        <ReportPageFrame loading={loading} error={error} empty={empty} emptyMessage="No feature investment data for the selected filters.">
          {data ? (
            <div className="space-y-6">
              {drilldownError ? (
                <div className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                  {drilldownError}
                </div>
              ) : null}
              <MethodologyCard />
              <Leaderboard rows={filteredRows} periods={periods} onSelect={loadIssues} />
              <IssueDrilldown
                row={selectedRow}
                period={selectedPeriod}
                issues={issues}
                worklogs={worklogs}
                onSelectIssue={loadWorklogs}
              />
            </div>
          ) : null}
        </ReportPageFrame>
      </InvestmentReportLayout>
    </JiraAnalyticsShell>
  );
}

function MethodologyCard() {
  return (
    <ModernReportCard
      eyebrow="Calculation guide"
      title="How this report turns time bookings into investment"
      description="This report answers where company capacity was invested, even when Jira bookings are incomplete."
    >
      <div className="grid gap-4 text-sm leading-6 text-on-surface-variant lg:grid-cols-2">
        <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <h3 className="font-semibold text-on-surface">1. Start with actual Jira bookings</h3>
          <p className="mt-2">
            Booked hours are the hours people explicitly logged in Jira. They are shown as-is so the report
            remains auditable against the original worklogs.
          </p>
        </section>
        <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <h3 className="font-semibold text-on-surface">2. Include all work in each person’s monthly denominator</h3>
          <p className="mt-2">
            For Dev and QA, the scaling factor uses all direct booked work in the month: feature work,
            generic improvements, bugs, technical/support work, and other unassigned work. This prevents a
            feature from receiving too much calculated capacity just because the person also worked outside
            feature tickets.
          </p>
        </section>
        <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <h3 className="font-semibold text-on-surface">3. Normalize Dev and QA to HRWorks availability</h3>
          <p className="mt-2">
            The calculated Dev/QA factor is: HRWorks planned hours × 80% divided by that person’s booked
            Jira hours for the month. If the factor would drop below 1, it is clamped to 1 so calculated
            hours never become lower than the actual booked hours.
          </p>
        </section>
        <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <h3 className="font-semibold text-on-surface">4. Keep UX and overhead separate</h3>
          <p className="mt-2">
            UX remains equal to booked Jira hours. Product, architecture, and other configured overhead are
            taken from the allocation model and added as overhead hours to the same feature or generic bucket
            that received the direct work. These overhead hours are not rescaled again.
          </p>
        </section>
        <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <h3 className="font-semibold text-on-surface">5. Roll everything into feature families and buckets</h3>
          <p className="mt-2">
            Feature tickets roll up into their parent feature family. Work without a feature is still visible
            through generic buckets: Other bug, Other feature, and Other technical task. Those buckets also receive their
            proportional overhead, so CEO totals reconcile across feature and non-feature investment.
          </p>
        </section>
        <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4">
          <h3 className="font-semibold text-on-surface">6. Use the Excel export to audit every number</h3>
          <p className="mt-2">
            The export starts with calculated and actual monthly summaries, then includes issue detail, feature
            and family rollups by month and role, plus an HRWorks audit sheet showing planned hours, the
            booked-hour denominator, the capacity target, and the scale factor used for each person and month.
          </p>
        </section>
      </div>
    </ModernReportCard>
  );
}

function AuditFilters({
  params,
  data,
  query,
  exporting,
  onParamsChange,
  onQueryChange,
  onPreset,
  onExport,
}: {
  params: ReportQueryParams;
  data: AnalyticsReportResponse | null;
  query: string;
  exporting: boolean;
  onParamsChange: (value: ReportQueryParams | ((prev: ReportQueryParams) => ReportQueryParams)) => void;
  onQueryChange: (value: string) => void;
  onPreset: (value: PresetId) => void;
  onExport: () => void;
}) {
  const teams = stringList(data?.filters?.available_teams);
  const roles = stringList(data?.filters?.available_roles);
  const families = familyList(data?.filters?.available_families);
  return (
    <AnalyticsFilterPanel title="Audit filters" description="Filter the leaderboard and export with the same scope.">
      <FilterField label="Preset">
        <select className={filterInputClassName()} defaultValue="last-six-months" onChange={(event) => onPreset(event.target.value as PresetId)}>
          {PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>{preset.label}</option>
          ))}
        </select>
      </FilterField>
      <FilterField label="From">
        <input type="date" className={filterInputClassName()} value={params.from ?? ""} onChange={(event) => onParamsChange((prev) => ({ ...prev, from: event.target.value }))} />
      </FilterField>
      <FilterField label="To">
        <input type="date" className={filterInputClassName()} value={params.to ?? ""} onChange={(event) => onParamsChange((prev) => ({ ...prev, to: event.target.value }))} />
      </FilterField>
      <FilterField label="Search" className="min-w-[16rem]">
        <input type="search" className={filterInputClassName()} value={query} placeholder="Feature, key, or family" onChange={(event) => onQueryChange(event.target.value)} />
      </FilterField>
      <FilterField label="Team">
        <select className={filterInputClassName()} value={params.team ?? ""} onChange={(event) => onParamsChange((prev) => ({ ...prev, team: event.target.value || undefined }))}>
          <option value="">All teams</option>
          {teams.map((team) => <option key={team} value={team}>{team}</option>)}
        </select>
      </FilterField>
      <FilterField label="Role">
        <select className={filterInputClassName()} value={params.role ?? ""} onChange={(event) => onParamsChange((prev) => ({ ...prev, role: event.target.value || undefined }))}>
          <option value="">All roles</option>
          {roles.map((role) => <option key={role} value={role}>{role}</option>)}
        </select>
      </FilterField>
      <FilterField label="Family">
        <select className={filterInputClassName()} value={params.familyId ?? ""} onChange={(event) => onParamsChange((prev) => ({ ...prev, familyId: event.target.value || undefined }))}>
          <option value="">All families</option>
          {families.map((family) => <option key={family.identifier} value={family.identifier}>{family.name}</option>)}
        </select>
      </FilterField>
      <button type="button" onClick={onExport} disabled={exporting} className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60">
        {exporting ? "Exporting..." : "Export XLSX"}
      </button>
    </AnalyticsFilterPanel>
  );
}

function Leaderboard({
  rows,
  periods,
  onSelect,
}: {
  rows: FeatureInvestmentAuditRow[];
  periods: string[];
  onSelect: (row: FeatureInvestmentAuditRow, period?: string | null) => void;
}) {
  const [sort, setSort] = useState<SortState<string> | null>({ key: "calculated_hours", direction: "desc" });
  const sortedRows = useMemo(() => {
    const baseRows = [...rows];
    if (!sort) return baseRows;
    return baseRows.sort((a, b) => {
      const value = (row: FeatureInvestmentAuditRow) => {
        if (sort.key.startsWith("period:")) return row.monthly[sort.key.slice("period:".length)]?.calculated ?? 0;
        if (sort.key === "feature") return featureLabel(row);
        return (row as unknown as Record<string, unknown>)[sort.key];
      };
      return (
        compareSortableValues(value(a), value(b), sort.direction) ||
        compareSortableValues(a.family_name, b.family_name, "asc") ||
        compareSortableValues(featureLabel(a), featureLabel(b), "asc")
      );
    });
  }, [rows, sort]);

  return (
    <ModernReportCard eyebrow="Leaderboard" title="Feature investment by month" description="Booked, calculated, and overhead hours. Click a feature or month to open issue detail.">
      <div className="max-h-[34rem] overflow-auto rounded-2xl elevated-panel">
        <table className="w-full min-w-[72rem] text-sm">
          <thead className="sticky top-0 z-10 bg-surface-container-low">
            <tr className="border-b border-outline-variant/20 text-left">
              <SortableHeader label="Family" sortKey="family_name" sort={sort} setSort={setSort} />
              <SortableHeader label="Feature" sortKey="feature" sort={sort} setSort={setSort} />
              <SortableHeader label="Booked" sortKey="booked_hours" sort={sort} setSort={setSort} numeric />
              <SortableHeader label="Calculated" sortKey="calculated_hours" sort={sort} setSort={setSort} numeric />
              <SortableHeader label="Overhead" sortKey="overhead_hours" sort={sort} setSort={setSort} numeric />
              {periods.map((period) => (
                <SortableHeader key={period} label={formatPeriod(period)} sortKey={`period:${period}`} sort={sort} setSort={setSort} numeric />
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => (
              <tr key={`${row.feature_identifier}-${row.team ?? ""}`} className="border-b border-outline-variant/10">
                <td className="px-3 py-2">{row.family_name}</td>
                <td className="px-3 py-2">
                  <button type="button" className="font-semibold text-primary hover:underline" onClick={() => onSelect(row)}>
                    {featureLabel(row)}
                  </button>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatHours(row.booked_hours, 0)}</td>
                <td className="px-3 py-2 text-right tabular-nums font-semibold">{formatHours(row.calculated_hours, 0)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatHours(row.overhead_hours, 0)}</td>
                {periods.map((period) => {
                  const month = row.monthly[period];
                  return (
                    <td key={period} className="px-3 py-2 text-right tabular-nums">
                      <button type="button" className="rounded px-1 text-primary hover:underline" onClick={() => onSelect(row, period)}>
                        {formatHours(month?.calculated ?? 0, 0)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ModernReportCard>
  );
}

function IssueDrilldown({
  row,
  period,
  issues,
  worklogs,
  onSelectIssue,
}: {
  row: FeatureInvestmentAuditRow | null;
  period: string | null;
  issues: FeatureInvestmentAuditIssueRow[];
  worklogs: FeatureInvestmentAuditWorklogRow[];
  onSelectIssue: (issue: FeatureInvestmentAuditIssueRow) => void;
}) {
  const groupedWorklogs = useMemo(() => groupWorklogRows(worklogs), [worklogs]);
  return (
    <ModernReportCard
      eyebrow="Drilldown"
      title={row ? `${featureLabel(row)} issue detail` : "Select a feature"}
      description={row ? `Showing ${period ? formatPeriod(period) : "all selected months"} for ${row.family_name}.` : "Open a feature or month to inspect issues and individual booked hours."}
    >
      {row ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <SimpleTable
            rows={issues}
            columns={[
              { key: "issue_identifier", label: "JIRA Key" },
              { key: "issue_name", label: "Title" },
              { key: "issue_type", label: "Issue Type" },
              { key: "booked_hours", label: "Booked", numeric: true, format: formatDrilldownHours },
              { key: "calculated_hours", label: "Calculated", numeric: true, format: formatDrilldownHours },
              { key: "overhead_hours", label: "Overhead", numeric: true, format: formatDrilldownHours },
            ]}
            onRowClick={onSelectIssue}
          />
          <SimpleTable
            rows={groupedWorklogs}
            columns={[
              { key: "period", label: "Period" },
              { key: "person", label: "Person" },
              { key: "role", label: "Role" },
              { key: "worklog_date", label: "Worklog Date" },
              { key: "source", label: "Source", format: formatSource },
              { key: "booked_hours", label: "Booked", numeric: true, format: formatDrilldownHours },
              { key: "calculated_hours", label: "Calculated", numeric: true, format: formatDrilldownHours },
              { key: "scale_factor", label: "Scale Factor", numeric: true, format: formatOneDecimal },
            ]}
          />
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-outline-variant/30 p-6 text-sm text-on-surface-variant">No feature selected.</p>
      )}
    </ModernReportCard>
  );
}

type SimpleColumn<T extends object> = {
  key: Extract<keyof T, string>;
  label: string;
  numeric?: boolean;
  format?: (value: unknown, row: T) => string;
  sortValue?: (row: T) => unknown;
};

function SimpleTable<T extends object>({
  rows,
  columns,
  onRowClick,
}: {
  rows: T[];
  columns: SimpleColumn<T>[];
  onRowClick?: (row: T) => void;
}) {
  const [sort, setSort] = useState<SortState<string> | null>(
    columns[0] ? { key: columns[0].key, direction: "asc" } : null,
  );
  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((item) => item.key === sort.key);
    return [...rows].sort((a, b) => {
      const aValue = column?.sortValue ? column.sortValue(a) : (a as Record<string, unknown>)[sort.key];
      const bValue = column?.sortValue ? column.sortValue(b) : (b as Record<string, unknown>)[sort.key];
      return compareSortableValues(aValue, bValue, sort.direction);
    });
  }, [columns, rows, sort]);

  return (
    <div className="max-h-[26rem] overflow-auto rounded-xl border border-outline-variant/20">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface-container-low">
          <tr>
            {columns.map((column) => (
              <SortableHeader
                key={column.key}
                label={column.label}
                sortKey={column.key}
                sort={sort}
                setSort={setSort}
                numeric={column.numeric}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, index) => (
            <tr key={index} className="border-t border-outline-variant/10">
              {columns.map((column, columnIndex) => (
                <td key={column.key} className={`px-3 py-2 ${column.numeric ? "text-right tabular-nums" : ""}`}>
                  {columnIndex === 0 && onRowClick ? (
                    <button type="button" className="font-semibold text-primary hover:underline" onClick={() => onRowClick(row)}>
                      {formatCellValue(row, column)}
                    </button>
                  ) : (
                    formatCellValue(row, column)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditMetrics({ rows, visibleRows }: { rows: FeatureInvestmentAuditRow[]; visibleRows: number }) {
  const booked = rows.reduce((sum, row) => sum + row.booked_hours, 0);
  const calculated = rows.reduce((sum, row) => sum + row.calculated_hours, 0);
  const overhead = rows.reduce((sum, row) => sum + row.overhead_hours, 0);
  return (
    <>
      <InvestmentMetricCard label="Features" value={rows.length ? String(rows.length) : "Loading"} detail={`${visibleRows} visible`} />
      <InvestmentMetricCard label="Calculated" value={formatHours(calculated, 0)} detail={`${formatHours(booked, 0)} booked`} />
      <InvestmentMetricCard label="Overhead" value={formatHours(overhead, 0)} detail="Allocated role overhead" />
    </>
  );
}

function toAuditRow(row: Record<string, unknown>): FeatureInvestmentAuditRow | null {
  if (typeof row.feature_identifier !== "string" || typeof row.feature_name !== "string") return null;
  return {
    rank: numberValue(row.rank),
    family_identifier: String(row.family_identifier ?? ""),
    family_name: String(row.family_name ?? ""),
    feature_identifier: row.feature_identifier,
    feature_name: row.feature_name,
    team: typeof row.team === "string" ? row.team : null,
    booked_hours: numberValue(row.booked_hours),
    calculated_hours: numberValue(row.calculated_hours),
    overhead_hours: numberValue(row.overhead_hours),
    monthly: isMonthly(row.monthly) ? row.monthly : {},
  };
}

function toIssueRow(row: Record<string, unknown>): FeatureInvestmentAuditIssueRow | null {
  if (typeof row.issue_identifier !== "string") return null;
  return {
    issue_identifier: row.issue_identifier,
    issue_name: typeof row.issue_name === "string" ? row.issue_name : null,
    issue_type: typeof row.issue_type === "string" ? row.issue_type : null,
    family_name: String(row.family_name ?? ""),
    feature_identifier: String(row.feature_identifier ?? ""),
    feature_name: String(row.feature_name ?? ""),
    booked_hours: numberValue(row.booked_hours),
    calculated_hours: numberValue(row.calculated_hours),
    overhead_hours: numberValue(row.overhead_hours),
  };
}

function toWorklogRow(row: Record<string, unknown>): FeatureInvestmentAuditWorklogRow | null {
  if (typeof row.issue_key !== "string") return null;
  return {
    period: String(row.period ?? ""),
    person: String(row.person ?? ""),
    role: typeof row.role === "string" ? row.role : null,
    issue_key: row.issue_key,
    worklog_id: typeof row.worklog_id === "string" ? row.worklog_id : null,
    worklog_date: typeof row.worklog_date === "string" ? row.worklog_date : null,
    source: String(row.source ?? ""),
    booked_hours: numberValue(row.booked_hours),
    calculated_hours: numberValue(row.calculated_hours),
    overhead_hours: numberValue(row.overhead_hours),
    scale_factor: numberValue(row.scale_factor),
    hrworks_planned_hours: numberValue(row.hrworks_planned_hours),
  };
}

function aggregateAuditRows(rows: FeatureInvestmentAuditRow[]): FeatureInvestmentAuditRow[] {
  const grouped = new Map<string, FeatureInvestmentAuditRow>();
  const result: FeatureInvestmentAuditRow[] = [];
  for (const row of rows) {
    if (!isGenericFeature(row.feature_identifier)) {
      result.push(row);
      continue;
    }
    const existing = grouped.get(row.feature_identifier);
    if (!existing) {
      const aggregate: FeatureInvestmentAuditRow = {
        ...row,
        family_identifier: OTHER_FAMILY_IDENTIFIER,
        family_name: OTHER_FAMILY_NAME,
        feature_name: GENERIC_FEATURE_LABELS[row.feature_identifier] ?? row.feature_name,
        team: null,
        monthly: cloneMonthly(row.monthly),
      };
      grouped.set(row.feature_identifier, aggregate);
      result.push(aggregate);
      continue;
    }
    existing.booked_hours += row.booked_hours;
    existing.calculated_hours += row.calculated_hours;
    existing.overhead_hours += row.overhead_hours;
    mergeMonthly(existing.monthly, row.monthly);
  }
  return result;
}

function groupWorklogRows(rows: FeatureInvestmentAuditWorklogRow[]): FeatureInvestmentAuditWorklogRow[] {
  const grouped = new Map<string, FeatureInvestmentAuditWorklogRow>();
  const result: FeatureInvestmentAuditWorklogRow[] = [];
  for (const row of rows) {
    if (row.overhead_hours <= 0) {
      result.push({ ...row, source: "JIRA" });
      continue;
    }
    const key = [row.period, row.person].join("::");
    const existing = grouped.get(key);
    if (!existing) {
      const aggregate: FeatureInvestmentAuditWorklogRow = {
        ...row,
        worklog_id: null,
        worklog_date: null,
        source: "Overhead",
      };
      grouped.set(key, aggregate);
      result.push(aggregate);
      continue;
    }
    existing.booked_hours += row.booked_hours;
    existing.calculated_hours += row.calculated_hours;
    existing.overhead_hours += row.overhead_hours;
  }
  return result;
}

function cloneMonthly(monthly: FeatureInvestmentAuditRow["monthly"]): FeatureInvestmentAuditRow["monthly"] {
  return Object.fromEntries(Object.entries(monthly).map(([period, values]) => [period, { ...values }]));
}

function mergeMonthly(target: FeatureInvestmentAuditRow["monthly"], source: FeatureInvestmentAuditRow["monthly"]) {
  for (const [period, values] of Object.entries(source)) {
    const existing = target[period] ?? { booked: 0, calculated: 0, overhead: 0 };
    existing.booked += values.booked ?? 0;
    existing.calculated += values.calculated ?? 0;
    existing.overhead += values.overhead ?? 0;
    target[period] = existing;
  }
}

function isGenericFeature(featureIdentifier: string): boolean {
  return featureIdentifier in GENERIC_FEATURE_LABELS;
}

function featureLabel(row: FeatureInvestmentAuditRow): string {
  if (isGenericFeature(row.feature_identifier)) return row.feature_name;
  return `${row.feature_identifier} · ${row.feature_name}`;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function familyList(value: unknown): { identifier: string; name: string }[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const record = item as Record<string, unknown>;
      return { identifier: String(record.identifier ?? ""), name: String(record.name ?? "") };
    })
    .filter((item): item is { identifier: string; name: string } => Boolean(item?.identifier));
}

function isMonthly(value: unknown): value is FeatureInvestmentAuditRow["monthly"] {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function SortableHeader({
  label,
  sortKey,
  sort,
  setSort,
  numeric = false,
}: {
  label: string;
  sortKey: string;
  sort: SortState<string> | null;
  setSort: (sort: SortState<string> | null) => void;
  numeric?: boolean;
}) {
  const direction = sort?.key === sortKey ? sort.direction : null;
  return (
    <th className={`px-3 py-2 font-medium text-on-surface-variant ${numeric ? "text-right" : "text-left"}`}>
      <button
        type="button"
        onClick={() => setSort(nextSortState(sort, sortKey))}
        className={`inline-flex items-center gap-1 hover:text-on-surface ${numeric ? "justify-end" : "justify-start"}`}
      >
        <span>{label}</span>
        <span className="text-[10px]">{direction === "asc" ? "▲" : direction === "desc" ? "▼" : "↕"}</span>
      </button>
    </th>
  );
}

function formatHours(value: number, maximumFractionDigits = 1): string {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value)} h`;
}

function formatPeriod(period: string): string {
  const [year, month] = period.split("-");
  return `${month}/${year.slice(2)}`;
}

function formatCell(value: unknown): string {
  if (typeof value === "number") return formatOneDecimal(value);
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function formatCellValue<T extends object>(row: T, column: SimpleColumn<T>): string {
  const value = (row as Record<string, unknown>)[column.key];
  return column.format ? column.format(value, row) : formatCell(value);
}

function formatDrilldownHours(value: unknown): string {
  return formatHours(numberValue(value), 1);
}

function formatOneDecimal(value: unknown): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(numberValue(value));
}

function formatSource(value: unknown): string {
  const source = String(value ?? "");
  return source.toLowerCase().includes("overhead") ? "Overhead" : "JIRA";
}
