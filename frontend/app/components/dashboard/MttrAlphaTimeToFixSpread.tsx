"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMttrAlphaSummary } from "@/lib/hooks";
import { useChartColors } from "@/lib/chart-colors";
import { formatMttrMinutes, formatMttrMinutesDetail } from "@/lib/mttr-display";
import type { MttrAlphaSummaryResponse } from "@/types/api";

function formatPeriodHint(summary: MttrAlphaSummaryResponse): string {
  const a = new Date(summary.period_start);
  const b = new Date(summary.period_end);
  return `${a.toLocaleDateString(undefined, { dateStyle: "medium" })} – ${b.toLocaleDateString(undefined, { dateStyle: "medium" })}`;
}

function PercentileChips({ summary }: { summary: MttrAlphaSummaryResponse }) {
  const minV = summary.min_minutes;
  const maxV = summary.max_minutes;
  if (minV == null || maxV == null || summary.incident_count === 0) {
    return (
      <p className="text-sm text-on-surface-variant font-editorial">
        No resolved MTTR Alpha incidents in this period, so there is no spread to show.
      </p>
    );
  }

  type Chip = { key: string; label: string; value: string; title: string };
  const chips: Chip[] = [
    { key: "min", label: "Min", value: formatMttrMinutes(minV), title: formatMttrMinutesDetail(minV) },
  ];
  if (summary.p50_minutes != null) {
    chips.push({
      key: "p50",
      label: "P50",
      value: formatMttrMinutes(summary.p50_minutes),
      title: formatMttrMinutesDetail(summary.p50_minutes),
    });
  }
  if (summary.p75_minutes != null) {
    chips.push({
      key: "p75",
      label: "P75",
      value: formatMttrMinutes(summary.p75_minutes),
      title: formatMttrMinutesDetail(summary.p75_minutes),
    });
  }
  if (summary.p90_minutes != null) {
    chips.push({
      key: "p90",
      label: "P90",
      value: formatMttrMinutes(summary.p90_minutes),
      title: formatMttrMinutesDetail(summary.p90_minutes),
    });
  }
  if (summary.p95_minutes != null) {
    chips.push({
      key: "p95",
      label: "P95",
      value: formatMttrMinutes(summary.p95_minutes),
      title: formatMttrMinutesDetail(summary.p95_minutes),
    });
  }
  chips.push({
    key: "max",
    label: "Max",
    value: formatMttrMinutes(maxV),
    title: formatMttrMinutesDetail(maxV),
  });

  return (
    <ul className="flex flex-wrap gap-x-2 gap-y-2" aria-label="MTTR percentiles and range">
      {chips.map((m) => (
        <li
          key={m.key}
          className="inline-flex min-w-0 max-w-full flex-col rounded-md border border-outline-variant/50 bg-surface-container-lowest px-2.5 py-1.5"
          title={m.title}
        >
          <span className="text-[9px] font-editorial font-bold uppercase tracking-wider text-on-surface-variant">
            {m.label}
          </span>
          <span className="text-xs font-editorial font-bold tabular-nums text-on-surface">{m.value}</span>
        </li>
      ))}
    </ul>
  );
}

function SpreadHistogram({ summary }: { summary: MttrAlphaSummaryResponse }) {
  const colors = useChartColors();
  const data = useMemo(() => {
    const total = Math.max(1, summary.incident_count);
    return (summary.mttr_alpha_histogram ?? []).map((b) => ({
      label: b.label,
      count: b.count,
      pctLabel: `${((100 * b.count) / total).toFixed(1)}%`,
    }));
  }, [summary]);

  if (!summary.mttr_alpha_histogram?.length || summary.incident_count === 0) {
    return null;
  }

  return (
    <div className="mt-6">
      <p className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline mb-2">
        Distribution (resolved incidents)
      </p>
      <div className="h-56 w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 52 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={colors.grid}
              strokeOpacity={colors.gridOpacity}
              vertical={false}
            />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 9, fill: colors.axisLabel }}
              interval={0}
              angle={-30}
              textAnchor="end"
              height={48}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: colors.axisLabel }} width={36} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const row = payload[0]?.payload as { label?: string; count?: number; pctLabel?: string };
                return (
                  <div
                    className="rounded-md px-3 py-2 text-xs shadow-md"
                    style={{ backgroundColor: colors.tooltipBg, color: colors.tooltipText }}
                  >
                    <p className="font-bold">{row?.label}</p>
                    <p>
                      {row?.count ?? 0} incidents ({row?.pctLabel ?? "0%"} of resolved in period)
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="count" fill={colors.primary} radius={[4, 4, 0, 0]} name="Incidents" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/**
 * Stacked percentiles + histogram for the active MTTR Alpha window. Rendered between the
 * trend chart and “MTTR Alpha details” when MTTR Alpha is selected.
 */
export function MttrAlphaTimeToFixSpread() {
  const { data: summary, isLoading, isError } = useMttrAlphaSummary();

  return (
    <section className="bg-surface-container-lowest p-8 rounded-xl shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
      <h2 className="text-2xl font-editorial font-bold tracking-tight text-on-surface">Time to fix spread</h2>
      <p className="text-xs font-editorial text-on-surface-variant mt-1 max-w-3xl">
        Percentiles and bucket counts for the same incident population as the trend chart: healthy bugs with a
        resolved MTTR Alpha in the selected period. P75+ use linear interpolation (API definition).
      </p>
      {isLoading && (
        <div className="mt-6 space-y-3">
          <div className="h-16 bg-surface-container animate-pulse rounded-lg" />
          <div className="h-56 bg-surface-container animate-pulse rounded-lg" />
        </div>
      )}
      {isError && (
        <p className="mt-4 text-sm text-error font-editorial">Could not load MTTR Alpha summary for this period.</p>
      )}
      {!isLoading && !isError && summary && (
        <>
          <p className="text-[10px] font-editorial text-on-surface-variant uppercase tracking-widest mt-3">
            {formatPeriodHint(summary)}
          </p>
          <div className="mt-4 border border-outline-variant/30 rounded-lg bg-surface-container-low/40 px-3 py-3">
            <PercentileChips summary={summary} />
          </div>
          <SpreadHistogram summary={summary} />
        </>
      )}
    </section>
  );
}
