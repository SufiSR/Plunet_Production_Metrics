"use client";

export type IngestionProgressSnapshot = {
  step?: string;
  message?: string;
  months_total?: number;
  months_completed?: number;
  current_month?: string;
  persons_in_month_total?: number;
  persons_in_month_done?: number;
  api_calls?: number;
  rows_upserted?: number;
  rows_skipped?: number;
  roster_persons?: number;
  roster_mapped_jira?: number;
};

function pct(done: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.round((done / total) * 100));
}

interface IngestionLiveProgressProps {
  progress: IngestionProgressSnapshot | null | undefined;
  isRunning: boolean;
}

export function IngestionLiveProgress({ progress, isRunning }: IngestionLiveProgressProps) {
  if (!isRunning && !progress) return null;

  const monthsTotal = progress?.months_total ?? 0;
  const monthsDone = progress?.months_completed ?? 0;
  const personsTotal = progress?.persons_in_month_total ?? 0;
  const personsDone = progress?.persons_in_month_done ?? 0;
  const monthLabel = progress?.current_month ?? "—";

  const overallPct =
    monthsTotal > 0
      ? pct(monthsDone + (personsTotal > 0 ? personsDone / personsTotal : 0), monthsTotal)
      : 0;

  return (
    <div
      className="rounded-xl border border-primary/25 bg-primary/5 p-4 space-y-3"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        {isRunning ? (
          <span className="material-symbols-outlined text-primary text-lg animate-spin">progress_activity</span>
        ) : (
          <span className="material-symbols-outlined text-secondary text-lg">check_circle</span>
        )}
        <span className="text-sm font-editorial font-semibold text-on-surface">
          {isRunning ? "Sync in progress" : "Last progress snapshot"}
        </span>
      </div>

      {progress?.message ? (
        <p className="text-sm text-on-surface-variant">{progress.message}</p>
      ) : null}

      {monthsTotal > 0 ? (
        <div className="space-y-1.5">
          <div className="flex justify-between text-[10px] uppercase tracking-wider text-outline">
            <span>
              Month {Math.min(monthsDone + 1, monthsTotal)} / {monthsTotal}
            </span>
            <span>{monthLabel}</span>
          </div>
          <div className="h-2 rounded-full bg-surface-container overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${overallPct}%` }}
            />
          </div>
          {personsTotal > 0 ? (
            <p className="text-xs text-on-surface-variant">
              People this month: {personsDone} / {personsTotal}
            </p>
          ) : null}
        </div>
      ) : null}

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div>
          <dt className="text-outline">API calls</dt>
          <dd className="font-medium text-on-surface">{progress?.api_calls ?? 0}</dd>
        </div>
        <div>
          <dt className="text-outline">Rows upserted</dt>
          <dd className="font-medium text-on-surface">{progress?.rows_upserted ?? 0}</dd>
        </div>
        <div>
          <dt className="text-outline">Roster mapped</dt>
          <dd className="font-medium text-on-surface">{progress?.roster_mapped_jira ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-outline">Step</dt>
          <dd className="font-medium text-on-surface uppercase">{progress?.step ?? "—"}</dd>
        </div>
      </dl>
    </div>
  );
}
