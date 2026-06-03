"use client";

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
import { sortRecordsByPeriodAsc } from "@/lib/jira-analytics-sort";

interface MonthlyTeamTrendChartProps {
  data: Record<string, unknown>[];
  teams: string[];
  valueFormatter?: (value: number) => string;
}

export function MonthlyTeamTrendChart({
  data,
  teams,
  valueFormatter = (value) => value.toFixed(1),
}: MonthlyTeamTrendChartProps) {
  const chartTheme = useReportChartTheme();
  const chartData = sortRecordsByPeriodAsc(data);

  if (!data.length || !teams.length) {
    return null;
  }

  return (
    <div className="analytics-chart-plot h-80 w-full p-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid {...chartTheme.gridProps} />
          <XAxis dataKey="period" tick={chartTheme.axisTick} axisLine={chartTheme.axisLine} tickLine={chartTheme.tickLine} />
          <YAxis
            domain={[0, 100]}
            tick={chartTheme.axisTick}
            axisLine={chartTheme.axisLine}
            tickLine={chartTheme.tickLine}
          />
          <Tooltip
            formatter={(value, name) => [
              typeof value === "number" ? valueFormatter(value) : "No score",
              String(name),
            ]}
            contentStyle={{
              background: chartTheme.colors.tooltipBg,
              color: chartTheme.colors.tooltipText,
              border: "none",
              borderRadius: "0.5rem",
            }}
          />
          <Legend />
          {teams.map((team, index) => (
            <Line
              key={team}
              type="monotone"
              dataKey={team}
              connectNulls
              stroke={chartTheme.series[index % chartTheme.series.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
