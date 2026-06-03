"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useReportChartTheme } from "@/lib/chart-colors";

interface YearlyTeamTrendChartProps {
  rows: Record<string, unknown>[];
  metricKey: string;
  yAxisLabel: string;
  formatValue?: (value: number) => string;
  yDomain?: [number | "auto", number | "auto"];
}

export function YearlyTeamTrendChart({
  rows,
  metricKey,
  yAxisLabel,
  formatValue = (value) => value.toFixed(2),
  yDomain,
}: YearlyTeamTrendChartProps) {
  const chartTheme = useReportChartTheme();
  const { chartData, teamKeys } = useMemo(
    () => buildYearlyTeamTrendChart(rows, metricKey),
    [rows, metricKey],
  );

  if (chartData.length === 0 || teamKeys.length === 0) {
    return null;
  }

  return (
    <div className="analytics-chart-plot h-80 w-full p-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid {...chartTheme.gridProps} />
          <XAxis
            dataKey="year"
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
            allowDecimals={false}
            label={{ value: "Year", position: "insideBottom", offset: -4, fontSize: 11, fill: chartTheme.colors.axisLabel }}
          />
          <YAxis
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
            domain={yDomain}
            tickFormatter={(value) => formatValue(Number(value))}
            label={{
              value: yAxisLabel,
              angle: -90,
              position: "insideLeft",
              fontSize: 11,
              fill: chartTheme.colors.axisLabel,
              style: { textAnchor: "middle" },
            }}
          />
          <Tooltip
            formatter={(value, name) => [
              typeof value === "number" ? formatValue(value) : String(value),
              String(name),
            ]}
            labelFormatter={(label) => `Year ${label}`}
            contentStyle={{
              background: chartTheme.colors.tooltipBg,
              color: chartTheme.colors.tooltipText,
              border: "none",
              borderRadius: "0.5rem",
            }}
          />
          <Legend />
          {teamKeys.map((team, index) => (
            <Line
              key={team}
              type="monotone"
              dataKey={team}
              name={team}
              stroke={chartTheme.series[index % chartTheme.series.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function buildYearlyTeamTrendChart(
  rows: Record<string, unknown>[],
  metricKey: string,
): {
  chartData: Record<string, number | string>[];
  teamKeys: string[];
} {
  const metricRows = rows.filter(
    (row) =>
      typeof row[metricKey] === "number" &&
      row.team !== null &&
      row.team !== undefined &&
      row.year !== null &&
      row.year !== undefined,
  );
  if (!metricRows.length) {
    return { chartData: [], teamKeys: [] };
  }

  const teamOrder: string[] = [];
  const teamSeen = new Set<string>();
  for (const row of metricRows) {
    const team = String(row.team);
    if (!teamSeen.has(team)) {
      teamSeen.add(team);
      teamOrder.push(team);
    }
  }

  const years = [...new Set(metricRows.map((row) => Number(row.year)))].sort((a, b) => a - b);
  const valueByTeamYear = new Map<string, number>();
  for (const row of metricRows) {
    valueByTeamYear.set(`${String(row.team)}:${Number(row.year)}`, Number(row[metricKey]));
  }

  const chartData = years.map((year) => {
    const point: Record<string, number | string> = { year };
    for (const team of teamOrder) {
      const value = valueByTeamYear.get(`${team}:${year}`);
      if (value !== undefined) {
        point[team] = value;
      }
    }
    return point;
  });

  return { chartData, teamKeys: teamOrder };
}
