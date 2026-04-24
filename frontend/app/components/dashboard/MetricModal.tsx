"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "next-themes";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useUIStore } from "@/lib/store";
import { useMetricsCurrent, useMetricsHistory } from "@/lib/hooks";
import { METRIC_EXPLANATIONS } from "@/lib/metric-explanations";
import { DoraBadge } from "./DoraBadge";
import { getChartColors } from "@/lib/chart-colors";
import type { DoraLevel, LeadTimeDiagnostics, MetricsCurrentResponse } from "@/types/api";

function formatLeadDiagLine(d: LeadTimeDiagnostics): string {
  const parts = [`n=${d.sample_count}`];
  const keys = Object.keys(d.match_counts ?? {}).sort();
  for (const k of keys) {
    const v = d.match_counts[k];
    if (typeof v === "number" && v > 0) parts.push(`${k}: ${v}`);
  }
  return parts.join(" · ");
}

export function MetricModal() {
  const { activeMetricModal, closeMetricModal } = useUIStore();
  const { data: current } = useMetricsCurrent();
  const { data: history } = useMetricsHistory();
  const { resolvedTheme } = useTheme();
  const overlayRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const isOpen = activeMetricModal !== null;
  const explanation = activeMetricModal
    ? METRIC_EXPLANATIONS[activeMetricModal]
    : null;
  type MetricSlice = { value: number | null; unit: string; dora_level: DoraLevel };
  const metricData: MetricSlice | undefined = activeMetricModal && current
    ? (current as unknown as Record<string, MetricSlice>)[activeMetricModal]
    : undefined;
  const leadTimeDiagnostics: LeadTimeDiagnostics | null =
    activeMetricModal === "lead_time_for_changes"
      ? ((current as MetricsCurrentResponse | undefined)?.lead_time_diagnostics ?? null)
      : null;

  const sparklineData =
    history?.data_points?.map((p) => ({
      date: p.date,
      value: activeMetricModal
        ? (p as unknown as Record<string, number | null>)[activeMetricModal]
        : null,
    })) ?? [];

  const colors = getChartColors();

  // Focus trap + Escape key
  useEffect(() => {
    if (!isOpen) return;
    closeButtonRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMetricModal();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [isOpen, closeMetricModal]);

  if (!isOpen || !explanation) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="metric-modal-title"
      onClick={(e) => {
        if (e.target === overlayRef.current) closeMetricModal();
      }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-on-surface/20 dark:bg-black/50 backdrop-blur-sm" />

      {/* Panel */}
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-lg shadow-[0px_24px_64px_0px_rgba(25,28,29,0.12)] dark:shadow-[0px_24px_64px_0px_rgba(0,0,0,0.5)] overflow-hidden">
        {/* Close button */}
        <button
          ref={closeButtonRef}
          onClick={closeMetricModal}
          className="absolute top-4 right-4 p-2 rounded-full text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
          aria-label="Close"
        >
          <span className="material-symbols-outlined text-xl">close</span>
        </button>

        <div className="p-8">
          {/* Header */}
          <div className="flex items-start gap-4 mb-6">
            <span className="material-symbols-outlined text-2xl text-primary mt-0.5">
              {explanation.icon}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1">
                <h2
                  id="metric-modal-title"
                  className="text-xl font-editorial font-bold tracking-tight text-on-surface"
                >
                  {explanation.title}
                </h2>
                {metricData?.dora_level && (
                  <DoraBadge level={metricData.dora_level} />
                )}
              </div>
                {metricData?.value !== null && metricData?.value !== undefined && (
                <p className="text-3xl font-editorial font-bold text-on-surface">
                  {metricData.value.toFixed(2)}{" "}
                  <span className="text-base font-normal text-on-surface-variant italic">
                    {metricData.unit}
                  </span>
                </p>
              )}
              {activeMetricModal === "change_failure_rate" &&
                (metricData?.value === null || metricData?.value === undefined) && (
                  <p className="text-2xl font-editorial font-bold text-on-surface-variant">
                    No data
                  </p>
                )}
            </div>
          </div>

          {/* Description */}
          <p className="text-sm text-on-surface-variant leading-relaxed mb-6">
            {explanation.description}
          </p>
          {leadTimeDiagnostics && (
            <p
              className="text-xs text-on-surface-variant leading-relaxed mb-6"
              title={leadTimeDiagnostics.definition}
            >
              {formatLeadDiagLine(leadTimeDiagnostics)}
            </p>
          )}

          {/* DORA thresholds */}
          <div className="mb-6 space-y-1.5">
            <p className="text-[10px] font-editorial uppercase tracking-widest text-outline font-bold mb-2">
              DORA Thresholds
            </p>
            {(
              [
                ["ELITE",  explanation.doraThresholds.elite],
                ["HIGH",   explanation.doraThresholds.high],
                ["MEDIUM", explanation.doraThresholds.medium],
                ["LOW",    explanation.doraThresholds.low],
              ] as [DoraLevel, string][]
            ).map(([level, threshold]) => (
              <div key={level} className="flex items-center gap-3">
                <DoraBadge level={level} />
                <span className="text-xs text-on-surface-variant">{threshold}</span>
              </div>
            ))}
          </div>

          {/* Sparkline */}
          {sparklineData.length > 0 && (
            <div>
              <p className="text-[10px] font-editorial uppercase tracking-widest text-outline font-bold mb-3">
                Trend
              </p>
              <div className="h-[120px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={sparklineData} margin={{ top: 4, right: 4, left: -32, bottom: 0 }}>
                    <CartesianGrid stroke={colors.grid} strokeDasharray="0" vertical={false} />
                    <XAxis dataKey="date" hide />
                    <YAxis
                      tick={{ fontSize: 9, fill: colors.axisLabel, fontFamily: "Space Grotesk" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: colors.tooltipBg,
                        color: colors.tooltipText,
                        border: "none",
                        borderRadius: "0.5rem",
                        fontSize: "11px",
                        fontFamily: "Space Grotesk",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke={colors.primary}
                      strokeWidth={2}
                      dot={false}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
