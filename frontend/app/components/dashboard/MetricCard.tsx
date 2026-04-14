"use client";

import { DoraBadge } from "./DoraBadge";
import { useUIStore } from "@/lib/store";
import { formatDateTime } from "@/lib/date-utils";
import type { DoraLevel, MetricValue } from "@/types/api";

interface MetricCardProps {
  metricKey: string;
  label: string;
  icon: string;
  data: MetricValue | undefined;
  isLoading: boolean;
  isError: boolean;
  generatedAt?: string;
}

function formatValue(value: number | null, unit: string): {
  main: string;
  suffix: string;
} {
  if (value === null) return { main: "—", suffix: "" };

  if (unit === "deploys / week") {
    return { main: value.toFixed(1), suffix: "/wk" };
  }
  if (unit === "hours") {
    if (value < 1) {
      return { main: Math.round(value * 60).toString(), suffix: "m" };
    }
    return { main: value.toFixed(1), suffix: "h" };
  }
  if (unit === "%") {
    return { main: value.toFixed(1), suffix: "%" };
  }
  if (unit === "minutes") {
    if (value >= 60) {
      return { main: (value / 60).toFixed(1), suffix: "h" };
    }
    return { main: Math.round(value).toString(), suffix: "m" };
  }
  if (unit === "days") {
    return { main: value.toFixed(1), suffix: "d" };
  }
  return { main: value.toFixed(1), suffix: unit };
}

export function MetricCard({
  metricKey,
  label,
  icon,
  data,
  isLoading,
  isError,
  generatedAt,
}: MetricCardProps) {
  const openMetricModal = useUIStore((s: { openMetricModal: (key: string) => void }) => s.openMetricModal);
  const { main, suffix } = data
    ? formatValue(data.value, data.unit)
    : { main: "—", suffix: "" };

  const trendPct = data?.trend_pct;

  return (
    <button
      onClick={() => openMetricModal(metricKey)}
      className="w-full text-left bg-surface-container-lowest p-6 flex flex-col justify-between rounded-xl transition-all duration-300 hover:bg-surface-container dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)] shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] group focus-visible:outline-2 focus-visible:outline-primary"
      aria-label={`${label}: ${main}${suffix}. Open details.`}
    >
      {/* Top row: badge + icon */}
      <div className="flex justify-between items-start">
        {isLoading ? (
          <div className="h-5 w-14 bg-surface-container animate-pulse rounded-md" />
        ) : isError ? (
          <span className="text-[10px] px-2 py-0.5 rounded-md font-editorial font-bold uppercase tracking-widest bg-error-container text-on-error-container">
            ERROR
          </span>
        ) : (
          <DoraBadge level={(data?.dora_level ?? "UNKNOWN") as DoraLevel} />
        )}
        <span className="material-symbols-outlined text-outline-variant group-hover:text-on-surface-variant transition-colors">
          {icon}
        </span>
      </div>

      {/* Value */}
      <div className="mt-8">
        {isLoading ? (
          <div className="h-12 w-24 bg-surface-container animate-pulse rounded-md" />
        ) : (
          <div className="text-4xl md:text-5xl font-editorial font-bold tracking-tight text-on-surface">
            {main}
            {suffix && (
              <span className="text-xl ml-1 font-normal text-on-surface-variant italic tracking-normal">
                {suffix}
              </span>
            )}
          </div>
        )}

        {/* Secondary text */}
        {data?.secondary_text && !isLoading && !isError && (
          <p className="text-[10px] text-on-surface-variant italic mt-1">
            {data.secondary_text}
          </p>
        )}

        {/* Label row + trend */}
        <div className="flex justify-between items-baseline mt-2">
          <p className="text-xs font-editorial uppercase tracking-widest text-on-surface-variant font-medium">
            {label}
          </p>
          {!isLoading && !isError && trendPct !== null && trendPct !== undefined && (
            <span
              className={`text-[10px] font-bold ${
                trendPct < 0 ? "text-primary" : "text-error"
              }`}
              title="Change vs previous period"
            >
              {trendPct > 0 ? "+" : ""}
              {trendPct.toFixed(1)}%
            </span>
          )}
        </div>

        {/* Data freshness tooltip */}
        {generatedAt && (
          <p
            className="text-[9px] text-outline mt-1 truncate"
            title={`Snapshot: ${formatDateTime(generatedAt)}`}
          >
            as of {formatDateTime(generatedAt)}
          </p>
        )}
      </div>
    </button>
  );
}
