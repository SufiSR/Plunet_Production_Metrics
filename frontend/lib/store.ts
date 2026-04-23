"use client";

import { create } from "zustand";

import type { LeadTimeBreakdown } from "@/types/api";

export type PeriodType = "30d" | "quarterly" | "yearly";
export type ThemeMode = "light" | "dark" | "system";

/** Drives trend chart series + paired visualization (swimlane / drill-down). */
export type TrendOverviewMetric =
  | "deployment_frequency"
  | "lead_time_for_changes"
  | "change_failure_rate"
  | "mttr_alpha";

interface UIState {
  period: PeriodType;
  setPeriod: (p: PeriodType) => void;

  trendOverviewMetric: TrendOverviewMetric;
  setTrendOverviewMetric: (m: TrendOverviewMetric) => void;

  leadTimeBreakdown: LeadTimeBreakdown;
  setLeadTimeBreakdown: (b: LeadTimeBreakdown) => void;

  activeMetricModal: string | null;
  openMetricModal: (metricKey: string) => void;
  closeMetricModal: () => void;
}

export const useUIStore = create<UIState>()((set) => ({
  period: "30d",
  setPeriod: (p) => set({ period: p }),

  trendOverviewMetric: "deployment_frequency",
  setTrendOverviewMetric: (m) => set({ trendOverviewMetric: m }),

  leadTimeBreakdown: "none",
  setLeadTimeBreakdown: (b) => set({ leadTimeBreakdown: b }),

  activeMetricModal: null,
  openMetricModal: (metricKey) => set({ activeMetricModal: metricKey }),
  closeMetricModal: () => set({ activeMetricModal: null }),
}));
