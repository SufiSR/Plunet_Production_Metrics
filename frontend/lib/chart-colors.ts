"use client";

export interface ChartColors {
  primary: string;
  grid: string;
  axisLabel: string;
  tooltipBg: string;
  tooltipText: string;
}

const CHART_COLOR_FALLBACKS: ChartColors = {
  primary: "#4648d4",
  grid: "#edeeef",
  axisLabel: "#464554",
  tooltipBg: "#2e3132",
  tooltipText: "#f0f1f2",
};

/**
 * Reads the current resolved CSS custom property values so Recharts
 * (which doesn't understand CSS variables) gets the correct colors for
 * whichever theme is currently active.
 *
 * Safe during SSR/static export: returns theme-agnostic fallbacks when `document` is unavailable.
 */
export function getChartColors(): ChartColors {
  if (typeof document === "undefined") {
    return { ...CHART_COLOR_FALLBACKS };
  }
  const style = getComputedStyle(document.documentElement);
  const get = (name: string) => style.getPropertyValue(name).trim();

  return {
    primary: get("--color-primary") || CHART_COLOR_FALLBACKS.primary,
    grid: get("--color-surface-container") || CHART_COLOR_FALLBACKS.grid,
    axisLabel: get("--color-on-surface-variant") || CHART_COLOR_FALLBACKS.axisLabel,
    tooltipBg: get("--color-inverse-surface") || CHART_COLOR_FALLBACKS.tooltipBg,
    tooltipText:
      get("--color-inverse-on-surface") || CHART_COLOR_FALLBACKS.tooltipText,
  };
}
