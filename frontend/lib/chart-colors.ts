"use client";

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";

export interface ChartColors {
  primary: string;
  grid: string;
  gridOpacity: number;
  axisLabel: string;
  tooltipBg: string;
  tooltipText: string;
  plotBackground: string;
}

const CHART_COLOR_FALLBACKS: ChartColors = {
  primary: "#4648d4",
  grid: "#d5d7d9",
  gridOpacity: 1,
  axisLabel: "#464554",
  tooltipBg: "#2e3132",
  tooltipText: "#f0f1f2",
  plotBackground: "#ffffff",
};

const CHART_COLOR_FALLBACKS_DARK: ChartColors = {
  primary: "#c0c1ff",
  grid: "#8b95a3",
  gridOpacity: 0.65,
  axisLabel: "#e8e6f5",
  tooltipBg: "#49525a",
  tooltipText: "#f3f4f5",
  plotBackground: "#343b42",
};

/** Saturated series colors readable on light chart backgrounds. */
export const CHART_SERIES_LIGHT = [
  "#4648d4",
  "#0d9488",
  "#c2410c",
  "#7c3aed",
  "#b45309",
  "#0891b2",
  "#be123c",
  "#64748b",
] as const;

/** Brighter series colors for dark chart plots. */
export const CHART_SERIES_DARK = [
  "#a5b4fc",
  "#2dd4bf",
  "#fb923c",
  "#c4b5fd",
  "#fbbf24",
  "#38bdf8",
  "#f472b6",
  "#94a3b8",
] as const;

function readCssVar(name: string): string {
  if (typeof document === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function isDarkMode(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

/**
 * Reads resolved chart tokens so Recharts gets correct hex values per theme.
 */
export function getChartColors(): ChartColors {
  const fallbacks = isDarkMode() ? CHART_COLOR_FALLBACKS_DARK : CHART_COLOR_FALLBACKS;

  if (typeof document === "undefined") {
    return { ...fallbacks };
  }

  return {
    primary: readCssVar("--color-primary") || fallbacks.primary,
    grid: readCssVar("--color-chart-grid") || fallbacks.grid,
    gridOpacity: fallbacks.gridOpacity,
    axisLabel: readCssVar("--color-chart-axis") || fallbacks.axisLabel,
    tooltipBg: readCssVar("--color-chart-tooltip-bg") || fallbacks.tooltipBg,
    tooltipText: readCssVar("--color-chart-tooltip-text") || fallbacks.tooltipText,
    plotBackground: readCssVar("--color-chart-plot") || fallbacks.plotBackground,
  };
}

export function getChartSeriesColors(): readonly string[] {
  return isDarkMode() ? CHART_SERIES_DARK : CHART_SERIES_LIGHT;
}

/** Re-reads chart colors when the theme changes (for client chart components). */
export function useChartColors(): ChartColors {
  const { resolvedTheme } = useTheme();
  const [colors, setColors] = useState<ChartColors>(() => getChartColors());

  useEffect(() => {
    setColors(getChartColors());
  }, [resolvedTheme]);

  return colors;
}

export function useChartSeriesColors(): readonly string[] {
  const { resolvedTheme } = useTheme();
  const [series, setSeries] = useState<readonly string[]>(() => getChartSeriesColors());

  useEffect(() => {
    setSeries(getChartSeriesColors());
  }, [resolvedTheme]);

  return series;
}

export interface ReportChartTheme {
  colors: ChartColors;
  series: readonly string[];
  gridProps: {
    stroke: string;
    strokeDasharray: string;
    strokeOpacity: number;
  };
  axisTick: { fontSize: number; fill: string };
  axisLine: boolean;
  tickLine: boolean;
}

export function useReportChartTheme(): ReportChartTheme {
  const colors = useChartColors();
  const series = useChartSeriesColors();

  return useMemo(
    () => ({
      colors,
      series,
      gridProps: {
        stroke: colors.grid,
        strokeDasharray: "3 3",
        strokeOpacity: colors.gridOpacity,
      },
      axisTick: { fontSize: 11, fill: colors.axisLabel },
      axisLine: false,
      tickLine: false,
    }),
    [colors, series],
  );
}
