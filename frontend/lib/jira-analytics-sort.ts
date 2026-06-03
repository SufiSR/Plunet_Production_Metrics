import type { FeatureHoursDrilldownIssue, FeatureHoursMatrixRow } from "@/types/jira-analytics";

export type SortDirection = "asc" | "desc";

export interface SortState<TKey extends string> {
  key: TKey;
  direction: SortDirection;
}

export function nextSortState<TKey extends string>(
  current: SortState<TKey> | null,
  key: TKey,
): SortState<TKey> {
  if (current?.key !== key) return { key, direction: "asc" };
  return { key, direction: current.direction === "asc" ? "desc" : "asc" };
}

export function compareSortableValues(
  a: unknown,
  b: unknown,
  direction: SortDirection,
): number {
  const modifier = direction === "asc" ? 1 : -1;
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * modifier;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" }) * modifier;
}

export function normalizePeriods(periods: string[]): string[] {
  return [...periods].sort((a, b) => b.localeCompare(a));
}

export function comparePeriodValuesDesc(a: unknown, b: unknown): number {
  return compareSortableValues(a, b, "desc");
}

export function comparePeriodValuesAsc(a: unknown, b: unknown): number {
  return compareSortableValues(a, b, "asc");
}

export function sortRecordsByPeriodDesc<T extends Record<string, unknown>>(
  rows: readonly T[],
  periodKey = "period",
): T[] {
  return [...rows].sort((a, b) => comparePeriodValuesDesc(a[periodKey], b[periodKey]));
}

export function sortRecordsByPeriodAsc<T extends Record<string, unknown>>(
  rows: readonly T[],
  periodKey = "period",
): T[] {
  return [...rows].sort((a, b) => comparePeriodValuesAsc(a[periodKey], b[periodKey]));
}

export function newestDateColumn(columns: readonly string[]): string | null {
  return (
    [
      "period",
      "month",
      "week",
      "date",
      "year",
      "quarter_start",
      "quarter",
      "promised",
      "promise_date",
      "promised_delivery_date",
      "active_start",
      "created_at",
      "committed_at",
      "merged_at",
      "first_fix_release_date",
      "last_updated_at",
    ].find((column) => columns.includes(column)) ?? null
  );
}

export function hoursForPeriod(
  hoursByPeriod: Record<string, number>,
  period: string,
): number {
  if (period in hoursByPeriod) {
    return hoursByPeriod[period] ?? 0;
  }
  const match = period.match(/^(\d{4})-(\d{1,2})$/);
  if (match) {
    const normalized = `${match[1]}-${String(Number(match[2])).padStart(2, "0")}`;
    return hoursByPeriod[normalized] ?? 0;
  }
  return 0;
}

export function compareHoursByPeriod(
  aHoursByPeriod: Record<string, number>,
  bHoursByPeriod: Record<string, number>,
  periods: string[],
): number {
  for (const period of normalizePeriods(periods)) {
    const diff =
      hoursForPeriod(bHoursByPeriod, period) - hoursForPeriod(aHoursByPeriod, period);
    if (diff !== 0) return diff;
  }
  return 0;
}

/** Sort rows by hours per period, newest month first, then each older month (descending). */
export function compareFeatureHoursRows(
  a: FeatureHoursMatrixRow,
  b: FeatureHoursMatrixRow,
  periods: string[],
): number {
  const typeRank = (row: FeatureHoursMatrixRow) => (row.row_type === "feature" ? 0 : 1);
  const typeDiff = typeRank(a) - typeRank(b);
  if (typeDiff !== 0) return typeDiff;

  const diff = compareHoursByPeriod(a.hours_by_period, b.hours_by_period, periods);
  if (diff !== 0) return diff;
  return a.label.localeCompare(b.label, undefined, { sensitivity: "base" });
}

export function compareFeatureHoursRowsByTotal(
  a: FeatureHoursMatrixRow,
  b: FeatureHoursMatrixRow,
  periods: string[],
): number {
  const totalDiff = b.total_hours - a.total_hours;
  if (totalDiff !== 0) return totalDiff;
  return compareFeatureHoursRows(a, b, periods);
}

export function splitFeatureHoursChartRows(
  rows: FeatureHoursMatrixRow[],
  periods: string[],
): { featureRows: FeatureHoursMatrixRow[]; otherRows: FeatureHoursMatrixRow[] } {
  return {
    featureRows: rows
      .filter((row) => row.row_type === "feature")
      .sort((a, b) => compareFeatureHoursRowsByTotal(a, b, periods)),
    otherRows: rows
      .filter((row) => row.row_type !== "feature")
      .sort((a, b) => compareFeatureHoursRowsByTotal(a, b, periods)),
  };
}

export function sortFeatureHoursRows(
  rows: FeatureHoursMatrixRow[],
  periods: string[],
): FeatureHoursMatrixRow[] {
  return [...rows].sort((a, b) => compareFeatureHoursRows(a, b, periods));
}

export function compareDrilldownIssues(
  a: FeatureHoursDrilldownIssue,
  b: FeatureHoursDrilldownIssue,
  periods: string[],
): number {
  const diff = compareHoursByPeriod(a.hours_by_period, b.hours_by_period, periods);
  if (diff !== 0) return diff;
  return a.issue_key.localeCompare(b.issue_key, undefined, { sensitivity: "base" });
}
