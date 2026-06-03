"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { FeatureHoursMatrixRow } from "@/types/jira-analytics";
import { FeatureRowLabel } from "@/app/components/jira-analytics/FeatureRowLabel";
import {
  compareSortableValues,
  hoursForPeriod,
  nextSortState,
  normalizePeriods,
  sortFeatureHoursRows,
  type SortState,
} from "@/lib/jira-analytics-sort";

const FEATURE_COL_WIDTH_PX = 300;
const PERIOD_COL_WIDTH_PX = 88;
const TOTAL_COL_WIDTH_PX = 80;
const BODY_MAX_HEIGHT = "min(50vh, 420px)";
type MatrixSortKey = "label" | "total" | `period:${string}`;

function formatPeriod(period: string): string {
  const [year, month] = period.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function formatHours(value: number): string {
  if (value <= 0) return "—";
  return value.toFixed(1);
}

function tableMinWidth(periodCount: number): number {
  return FEATURE_COL_WIDTH_PX + periodCount * PERIOD_COL_WIDTH_PX + TOTAL_COL_WIDTH_PX;
}

function MatrixColGroup({ periodCount }: { periodCount: number }) {
  return (
    <colgroup>
      <col style={{ width: FEATURE_COL_WIDTH_PX, minWidth: FEATURE_COL_WIDTH_PX }} />
      {Array.from({ length: periodCount }, (_, index) => (
        <col
          key={`period-col-${index}`}
          style={{ width: PERIOD_COL_WIDTH_PX, minWidth: PERIOD_COL_WIDTH_PX }}
        />
      ))}
      <col style={{ width: TOTAL_COL_WIDTH_PX, minWidth: TOTAL_COL_WIDTH_PX }} />
    </colgroup>
  );
}

interface FeatureHoursMatrixTableProps {
  periods: string[];
  rows: FeatureHoursMatrixRow[];
  jiraBaseUrl: string;
  selectedRowId: string | null;
  onSelectRow: (rowId: string) => void;
}

export function FeatureHoursMatrixTable({
  periods,
  rows,
  jiraBaseUrl,
  selectedRowId,
  onSelectRow,
}: FeatureHoursMatrixTableProps) {
  const headerScrollRef = useRef<HTMLDivElement>(null);
  const bodyScrollRef = useRef<HTMLDivElement>(null);
  const footerScrollRef = useRef<HTMLDivElement>(null);
  const [sort, setSort] = useState<SortState<MatrixSortKey> | null>(null);
  const sortedPeriods = useMemo(() => normalizePeriods(periods), [periods]);

  const syncScrollLeft = useCallback((source: HTMLDivElement) => {
    const { scrollLeft } = source;
    for (const ref of [headerScrollRef, bodyScrollRef, footerScrollRef]) {
      if (ref.current && ref.current !== source) {
        ref.current.scrollLeft = scrollLeft;
      }
    }
  }, []);

  const sortedRows = useMemo(
    () => {
      const baseRows = sortFeatureHoursRows(rows, sortedPeriods);
      if (!sort) return baseRows;
      return [...baseRows].sort((a, b) =>
        compareSortableValues(matrixSortValue(a, sort.key), matrixSortValue(b, sort.key), sort.direction),
      );
    },
    [rows, sort, sortedPeriods],
  );

  const columnTotals = sortedPeriods.map((period) =>
    sortedRows.reduce((sum, row) => sum + hoursForPeriod(row.hours_by_period, period), 0),
  );
  const grandTotal = sortedRows.reduce((sum, row) => sum + row.total_hours, 0);
  const minWidth = tableMinWidth(sortedPeriods.length);

  const headerCellClass =
    "px-3 py-3 text-right font-label text-xs uppercase tracking-wide whitespace-nowrap";
  const bodyCellClass = "px-3 py-2.5 text-right tabular-nums text-on-surface whitespace-nowrap";
  const footerCellClass = "px-3 py-3 text-right tabular-nums whitespace-nowrap";

  return (
    <div className="flex flex-col max-h-[min(70vh,640px)] rounded-xl border border-outline-variant/20 bg-surface-container-lowest">
      <div
        ref={headerScrollRef}
        className="overflow-x-auto flex-shrink-0 border-b border-outline-variant/28"
        onScroll={(event) => syncScrollLeft(event.currentTarget)}
      >
        <table
          className="text-sm border-collapse table-fixed"
          style={{ minWidth, width: minWidth }}
        >
          <MatrixColGroup periodCount={sortedPeriods.length} />
          <thead>
            <tr className="bg-surface-container text-on-surface-variant">
              <th className="sticky left-0 z-20 bg-surface-container px-4 py-3 text-left font-label text-xs uppercase tracking-wide">
                <SortButton
                  label="Feature / bucket"
                  sortKey="label"
                  activeSort={sort}
                  onSort={(key) => setSort(nextSortState(sort, key))}
                />
              </th>
              {sortedPeriods.map((period) => (
                <th key={period} className={headerCellClass}>
                  <SortButton
                    label={formatPeriod(period)}
                    sortKey={`period:${period}`}
                    numeric
                    activeSort={sort}
                    onSort={(key) => setSort(nextSortState(sort, key))}
                  />
                </th>
              ))}
              <th className={`${headerCellClass} px-4`}>
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
        </table>
      </div>

      <div
        ref={bodyScrollRef}
        className="overflow-y-auto overflow-x-auto flex-1 min-h-0"
        style={{ maxHeight: BODY_MAX_HEIGHT }}
        onScroll={(event) => syncScrollLeft(event.currentTarget)}
      >
        <table
          className="text-sm border-collapse table-fixed"
          style={{ minWidth, width: minWidth }}
        >
          <MatrixColGroup periodCount={sortedPeriods.length} />
          <tbody>
            {sortedRows.map((row) => {
              const isSelected = row.row_id === selectedRowId;
              const rowClass = [
                "border-t border-outline-variant/10 cursor-pointer",
                row.row_type !== "feature" ? "bg-surface-container-low/40" : "",
                isSelected ? "bg-primary-container/20" : "hover:bg-surface-container-low/60",
              ].join(" ");

              return (
                <tr
                  key={row.row_id}
                  className={rowClass}
                  onClick={() => onSelectRow(row.row_id)}
                >
                  <td className="sticky left-0 z-10 bg-inherit px-4 py-2.5 font-medium text-on-surface align-top">
                    <div className="flex items-start gap-2 min-w-0">
                      {row.row_type === "feature" ? (
                        <span className="material-symbols-outlined text-[16px] text-primary shrink-0 mt-0.5">
                          account_tree
                        </span>
                      ) : null}
                      <div className="min-w-0 flex-1">
                        <FeatureRowLabel row={row} jiraBaseUrl={jiraBaseUrl} />
                        {row.row_type !== "feature" ? (
                          <span className="text-xs text-on-surface-variant">(drill-down)</span>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  {sortedPeriods.map((period) => (
                    <td key={period} className={bodyCellClass}>
                      {formatHours(hoursForPeriod(row.hours_by_period, period))}
                    </td>
                  ))}
                  <td className={`${bodyCellClass} px-4 font-semibold`}>
                    {formatHours(row.total_hours)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div
        ref={footerScrollRef}
        className="overflow-x-auto flex-shrink-0 border-t-2 border-outline-variant/30 bg-surface-container"
        onScroll={(event) => syncScrollLeft(event.currentTarget)}
      >
        <table
          className="text-sm border-collapse table-fixed font-semibold"
          style={{ minWidth, width: minWidth }}
        >
          <MatrixColGroup periodCount={sortedPeriods.length} />
          <tbody>
            <tr>
              <td className="sticky left-0 z-10 bg-surface-container px-4 py-3">
                Total (may overlap)
              </td>
              {columnTotals.map((total, index) => (
                <td key={sortedPeriods[index]} className={footerCellClass}>
                  {formatHours(total)}
                </td>
              ))}
              <td className={`${footerCellClass} px-4`}>{formatHours(grandTotal)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function matrixSortValue(row: FeatureHoursMatrixRow, key: MatrixSortKey): string | number {
  if (key === "label") return row.label;
  if (key === "total") return row.total_hours;
  return hoursForPeriod(row.hours_by_period, key.slice("period:".length));
}

function SortButton({
  label,
  sortKey,
  numeric = false,
  activeSort,
  onSort,
}: {
  label: string;
  sortKey: MatrixSortKey;
  numeric?: boolean;
  activeSort: SortState<MatrixSortKey> | null;
  onSort: (key: MatrixSortKey) => void;
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
