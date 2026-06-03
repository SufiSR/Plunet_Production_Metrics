"use client";

import Link from "next/link";
import { DoraBadge } from "@/app/components/dashboard/DoraBadge";
import { DORA_METRIC_REPORTS, type DoraReportId } from "@/lib/dora-analytics-config";
import { useMetricsCurrent } from "@/lib/hooks";
import { useUIStore } from "@/lib/store";
import type { DoraLevel, MetricValue } from "@/types/api";

function formatValue(value: number | null, unit: string): { main: string; suffix: string } {
  if (value === null) return { main: "—", suffix: "" };
  if (unit === "deploys / week") return { main: value.toFixed(1), suffix: "/wk" };
  if (unit === "hours") {
    if (value < 1) return { main: String(Math.round(value * 60)), suffix: "m" };
    return { main: value.toFixed(1), suffix: "h" };
  }
  if (unit === "%") return { main: value.toFixed(1), suffix: "%" };
  if (unit === "minutes") {
    if (value >= 60) return { main: (value / 60).toFixed(1), suffix: "h" };
    return { main: String(Math.round(value)), suffix: "m" };
  }
  if (unit === "days") return { main: value.toFixed(1), suffix: "d" };
  return { main: value.toFixed(1), suffix: unit };
}

function KpiTile({
  href,
  label,
  metricKey,
  icon,
  data,
  isLoading,
  isError,
  active,
}: {
  href: string;
  label: string;
  metricKey: string;
  icon: string;
  data: MetricValue | undefined;
  isLoading: boolean;
  isError: boolean;
  active: boolean;
}) {
  const openMetricModal = useUIStore((s) => s.openMetricModal);
  const { main, suffix } = data ? formatValue(data.value, data.unit) : { main: "—", suffix: "" };
  const trendPct = data?.trend_pct;

  return (
    <div
      className={`relative rounded-xl border transition-colors ${
        active
          ? "border-primary/40 bg-primary/8 shadow-sm"
          : "border-outline-variant/20 bg-surface-container-lowest/90 hover:border-primary/30"
      }`}
    >
      <Link href={href} className="block p-3.5 pr-10 min-h-[5.5rem]">
        <div className="flex items-start justify-between gap-2">
          {isLoading ? (
            <div className="h-4 w-12 animate-pulse rounded bg-surface-container" />
          ) : isError ? (
            <span className="text-[9px] font-bold uppercase tracking-wider text-error">Error</span>
          ) : (
            <DoraBadge level={(data?.dora_level ?? "UNKNOWN") as DoraLevel} />
          )}
          <span className="material-symbols-outlined text-base text-outline-variant">{icon}</span>
        </div>
        <div className="mt-2">
          {isLoading ? (
            <div className="h-7 w-16 animate-pulse rounded bg-surface-container" />
          ) : (
            <p className="text-2xl font-editorial font-bold leading-none text-on-surface">
              {main}
              {suffix ? (
                <span className="ml-0.5 text-sm font-normal italic text-on-surface-variant">{suffix}</span>
              ) : null}
            </p>
          )}
          <div className="mt-1.5 flex items-center justify-between gap-2">
            <p className="text-[10px] font-label uppercase tracking-wide text-on-surface-variant line-clamp-1">
              {label}
            </p>
            {!isLoading && !isError && trendPct != null ? (
              <span
                className={`shrink-0 text-[10px] font-bold ${trendPct < 0 ? "text-primary" : "text-error"}`}
              >
                {trendPct > 0 ? "+" : ""}
                {trendPct.toFixed(1)}%
              </span>
            ) : null}
          </div>
        </div>
      </Link>
      <button
        type="button"
        onClick={() => openMetricModal(metricKey)}
        className="absolute right-2 top-2 rounded-md p-1 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
        aria-label={`${label} details`}
      >
        <span className="material-symbols-outlined text-base">info</span>
      </button>
    </div>
  );
}

export function DoraHeroKpiStrip({ activeReport }: { activeReport: DoraReportId }) {
  const { data, isLoading, isError } = useMetricsCurrent();

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {DORA_METRIC_REPORTS.map((report) => (
        <KpiTile
          key={report.id}
          href={report.href}
          label={report.title}
          metricKey={report.metricKey}
          icon={report.icon}
          data={data?.[report.metricKey]}
          isLoading={isLoading}
          isError={isError}
          active={activeReport === report.id}
        />
      ))}
    </div>
  );
}
