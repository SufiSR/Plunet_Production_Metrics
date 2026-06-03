import {
  compareFeatureHoursRowsByTotal,
  newestDateColumn,
  splitFeatureHoursChartRows,
  sortFeatureHoursRows,
  sortRecordsByPeriodDesc,
} from "@/lib/jira-analytics-sort";
import type { FeatureHoursMatrixRow, FeatureHoursRowType } from "@/types/jira-analytics";

function featureRow(
  rowId: string,
  hoursByPeriod: Record<string, number>,
  totalHours: number,
  rowType: FeatureHoursRowType = "feature",
): FeatureHoursMatrixRow {
  return {
    row_id: rowId,
    label: rowId,
    row_type: rowType,
    hours_by_period: hoursByPeriod,
    total_hours: totalHours,
  };
}

describe("jira analytics feature row sorting", () => {
  const periods = ["2026-05", "2026-04", "2025-12"];

  it("keeps the matrix default sorted by newest active period first", () => {
    const rows = [
      featureRow("high-2025-impact", { "2025-12": 80 }, 80),
      featureRow("recent-small", { "2026-05": 2 }, 2),
    ];

    expect(sortFeatureHoursRows(rows, periods).map((row) => row.row_id)).toEqual([
      "recent-small",
      "high-2025-impact",
    ]);
  });

  it("ranks chart series by total impact across the selected range", () => {
    const rows = [
      featureRow("recent-small", { "2026-05": 2 }, 2),
      featureRow("high-2025-impact", { "2025-12": 80 }, 80),
    ];

    const sorted = [...rows].sort((a, b) => compareFeatureHoursRowsByTotal(a, b, periods));

    expect(sorted.map((row) => row.row_id)).toEqual([
      "high-2025-impact",
      "recent-small",
    ]);
  });

  it("keeps every PMGT feature as its own chart series and only groups real other buckets", () => {
    const rows = [
      ...Array.from({ length: 10 }, (_, index) =>
        featureRow(`PMGT-${index + 1}`, { "2025-12": index + 1 }, index + 1),
      ),
      featureRow("__other_bug__", { "2025-12": 3 }, 3, "other_bug"),
      featureRow("__other_feature__", { "2025-12": 5 }, 5, "other_feature"),
    ];

    const { featureRows, otherRows } = splitFeatureHoursChartRows(rows, periods);

    expect(featureRows).toHaveLength(10);
    expect(featureRows.map((row) => row.row_id)).toEqual(
      expect.arrayContaining(["PMGT-1", "PMGT-10"]),
    );
    expect(otherRows.map((row) => row.row_id)).toEqual([
      "__other_feature__",
      "__other_bug__",
    ]);
  });
});

describe("jira analytics date ordering", () => {
  it("sorts report series with the newest period first", () => {
    const rows = [
      { period: "2026-04", value: 2 },
      { period: "2026-05", value: 1 },
      { period: "2025-12", value: 3 },
    ];

    expect(sortRecordsByPeriodDesc(rows).map((row) => row.period)).toEqual([
      "2026-05",
      "2026-04",
      "2025-12",
    ]);
  });

  it("prefers explicit date-like columns for default table ordering", () => {
    expect(newestDateColumn(["team", "month", "total_hours"])).toBe("month");
    expect(newestDateColumn(["feature", "active_start", "score"])).toBe("active_start");
    expect(newestDateColumn(["team", "total_hours"])).toBeNull();
  });
});
