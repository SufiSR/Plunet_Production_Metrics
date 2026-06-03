"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EmptyCardMessage, ModernReportCard } from "@/app/components/jira-analytics/ModernReportCard";
import { useChartColors, useChartSeriesColors } from "@/lib/chart-colors";
import { hoursForPeriod, normalizePeriods, splitFeatureHoursChartRows } from "@/lib/jira-analytics-sort";
import type { FeatureHoursMatrixRow } from "@/types/jira-analytics";

function formatPeriod(period: string): string {
  const [year, month] = period.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

interface FeatureHoursChartProps {
  periods: string[];
  rows: FeatureHoursMatrixRow[];
}

interface TooltipItem {
  name?: unknown;
  value?: unknown;
  color?: string;
}

interface TooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: readonly TooltipItem[];
}

export function FeatureHoursChart({ periods, rows }: FeatureHoursChartProps) {
  useTheme();
  const colors = useChartColors();
  const seriesColors = useChartSeriesColors();
  const sortedPeriods = useMemo(() => normalizePeriods(periods), [periods]);

  const { chartData, seriesKeys } = useMemo(() => {
    const { featureRows, otherRows } = splitFeatureHoursChartRows(rows, sortedPeriods);

    const keys = [
      ...featureRows.map((row) => row.row_id),
      ...(otherRows.some((row) => row.total_hours > 0) ? ["__stacked_other__"] : []),
    ];

    const data = sortedPeriods.map((period) => {
      const point: Record<string, string | number> = {
        period: formatPeriod(period),
      };
      for (const row of featureRows) {
        point[row.row_id] = hoursForPeriod(row.hours_by_period, period);
      }
      if (keys.includes("__stacked_other__")) {
        point.__stacked_other__ = otherRows.reduce(
          (sum, row) => sum + hoursForPeriod(row.hours_by_period, period),
          0,
        );
      }
      return point;
    });

    return { chartData: data, seriesKeys: keys };
  }, [sortedPeriods, rows]);

  const labelById = useMemo(() => {
    const map: Record<string, string> = { __stacked_other__: "Other buckets" };
    for (const row of rows) {
      map[row.row_id] =
        row.row_type === "feature" ? row.feature_name ?? row.label : row.label;
    }
    return map;
  }, [rows]);

  if (!chartData.length || !seriesKeys.length) {
    return (
      <EmptyCardMessage>No worklog hours in the selected range.</EmptyCardMessage>
    );
  }

  return (
    <ModernReportCard
      eyebrow="Trend"
      title="Hours by month"
      description="Stacked feature cost for every PMGT feature with effort. Other only groups the non-PMGT buckets from the table."
    >
      <div className="analytics-chart-plot h-[360px] p-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid
              stroke={colors.grid}
              strokeDasharray="3 3"
              strokeOpacity={colors.gridOpacity}
              vertical={false}
            />
            <XAxis dataKey="period" tick={{ fill: colors.axisLabel, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fill: colors.axisLabel, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              label={{
                value: "Hours",
                angle: -90,
                position: "insideLeft",
                fill: colors.axisLabel,
                fontSize: 11,
              }}
            />
            <Tooltip content={(props) => <FeatureHoursTooltip {...props} labelById={labelById} colors={colors} />} />
            {seriesKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                stackId="hours"
                fill={seriesColors[index % seriesColors.length]}
                radius={index === seriesKeys.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ModernReportCard>
  );
}

function FeatureHoursTooltip({
  active,
  label,
  payload,
  labelById,
  colors,
}: TooltipProps & {
  labelById: Record<string, string>;
  colors: ReturnType<typeof useChartColors>;
}) {
  if (!active || !payload?.length) return null;
  const visible = payload.filter((item) => Number(item.value ?? 0) > 0);
  if (visible.length === 0) return null;

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs shadow"
      style={{ background: colors.tooltipBg, color: colors.tooltipText }}
    >
      <div className="font-medium mb-1">{label}</div>
      <div className="space-y-1">
        {visible.map((item) => {
          const key = String(item.name ?? "");
          return (
            <div key={key} className="flex items-center justify-between gap-4">
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: item.color ?? colors.axisLabel }}
                />
                {labelById[key] ?? key}
              </span>
              <span className="tabular-nums">{Number(item.value ?? 0).toFixed(1)} h</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
