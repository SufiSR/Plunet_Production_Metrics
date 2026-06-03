"use client";

import type { AdminPipelineSyncLatestResponse } from "@/lib/admin-api-client";

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function statusTone(status: string | null | undefined): string {
  const normalized = status?.toLowerCase();
  if (normalized === "success") return "text-secondary";
  if (normalized === "failed") return "text-error";
  if (normalized === "partial_failure") return "text-amber-700 dark:text-amber-400";
  return "text-on-surface-variant";
}

function triggerLabel(log: AdminPipelineSyncLatestResponse["sync_log"]): string {
  const trigger = log?.details_json?.trigger;
  if (typeof trigger !== "string") return "—";
  const normalized = trigger.trim().toLowerCase();
  if (!normalized) return "—";
  if (["scheduled", "nightly", "cron", "auto", "automatic"].includes(normalized)) {
    return "Automatic";
  }
  if (normalized === "manual" || normalized.startsWith("manual-")) {
    return "Manual";
  }
  return trigger;
}

interface SyncLogCardProps {
  title: string;
  data: AdminPipelineSyncLatestResponse | null;
  loading?: boolean;
  error?: string | null;
  emptyHint?: string;
}

function isRunningStatus(data: AdminPipelineSyncLatestResponse | null): boolean {
  const log = data?.sync_log;
  if (!log) return false;
  if (log.finished_at) return false;
  const status = (data?.status ?? "").toLowerCase();
  return status === "running" || status === "";
}

export function SyncLogCard({ title, data, loading, error, emptyHint }: SyncLogCardProps) {
  const log = data?.sync_log;
  const status = data?.status ?? null;
  const showLoading = Boolean(loading || isRunningStatus(data));

  return (
    <div className="elevated-panel rounded-2xl p-5 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-editorial font-semibold text-on-surface">{title}</h3>
        {showLoading ? (
          <span className="material-symbols-outlined text-primary text-lg animate-spin">progress_activity</span>
        ) : null}
      </div>
      {error ? <p className="text-xs text-error">{error}</p> : null}
      {!error && !showLoading && !log ? (
        <p className="text-xs text-on-surface-variant">{emptyHint ?? "No sync runs recorded yet."}</p>
      ) : null}
      {log ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <dt className="text-outline">Status</dt>
          <dd className={`font-medium uppercase tracking-wide ${statusTone(status)}`}>{status ?? "—"}</dd>
          <dt className="text-outline">Run</dt>
          <dd className="text-on-surface">{triggerLabel(log)}</dd>
          <dt className="text-outline">Started</dt>
          <dd className="text-on-surface">{formatWhen(log.started_at)}</dd>
          <dt className="text-outline">Finished</dt>
          <dd className="text-on-surface">{formatWhen(log.finished_at)}</dd>
          <dt className="text-outline">Records</dt>
          <dd className="text-on-surface">{log.records_processed ?? "—"}</dd>
          {log.error_message ? (
            <>
              <dt className="text-outline col-span-2">Error</dt>
              <dd className="text-error col-span-2 text-[11px] leading-relaxed">{log.error_message}</dd>
            </>
          ) : null}
        </dl>
      ) : null}
    </div>
  );
}
