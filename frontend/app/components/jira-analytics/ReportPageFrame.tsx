"use client";

import type { ReactNode } from "react";

interface ReportPageFrameProps {
  loading?: boolean;
  /** Reloading while keeping the previous report content visible. */
  refreshing?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyMessage?: string;
  /** Shown under the spinner while the first load is in progress. */
  loadingTitle?: string;
  loadingHint?: string;
  /** When true, shows a “still computing” note (heavy analytics queries). */
  slowLoading?: boolean;
  elapsedSeconds?: number;
  onRetry?: () => void;
  children: ReactNode;
}

export function ReportPageFrame({
  loading,
  refreshing = false,
  error,
  empty,
  emptyMessage = "No data for the selected filters.",
  loadingTitle = "Loading report",
  loadingHint = "Aggregating Jira workflow data for the selected filters.",
  slowLoading = false,
  elapsedSeconds = 0,
  onRetry,
  children,
}: ReportPageFrameProps) {
  if (loading && !refreshing) {
    return (
      <div
        className="rounded-2xl border border-outline-variant/25 bg-surface-container-low p-6 shadow-sm"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex items-start gap-4">
          <div
            className="mt-0.5 h-10 w-10 shrink-0 rounded-full border-4 border-primary/25 border-t-primary animate-spin"
            aria-hidden
          />
          <div className="min-w-0 space-y-2">
            <p className="text-sm font-semibold text-on-surface">{loadingTitle}</p>
            <p className="text-sm text-on-surface-variant">{loadingHint}</p>
            {elapsedSeconds > 0 ? (
              <p className="text-xs text-on-surface-variant">
                Elapsed: {elapsedSeconds}s
                {slowLoading
                  ? " — still computing. Large date ranges can take up to a minute."
                  : ""}
              </p>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="rounded-2xl border border-error/30 bg-error-container/20 p-6"
        role="alert"
      >
        <p className="text-sm font-semibold text-error">Could not load report</p>
        <p className="mt-2 text-sm text-on-surface">{error}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 h-10 rounded-xl border border-outline-variant/40 bg-surface px-4 text-sm font-semibold text-on-surface shadow-sm hover:bg-surface-container-high"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  if (empty) {
    return <p className="text-sm text-on-surface-variant">{emptyMessage}</p>;
  }

  return (
    <div className="relative">
      {refreshing ? (
        <div
          className="absolute inset-0 z-10 flex items-start justify-center rounded-2xl bg-surface/70 p-6 backdrop-blur-[2px]"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <div className="flex max-w-md items-start gap-3 rounded-xl border border-outline-variant/25 bg-surface-container-lowest px-4 py-3 shadow-sm">
            <div
              className="mt-0.5 h-8 w-8 shrink-0 rounded-full border-4 border-primary/25 border-t-primary animate-spin"
              aria-hidden
            />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-on-surface">Updating filters…</p>
              <p className="text-xs text-on-surface-variant">
                {slowLoading
                  ? `Still computing (${elapsedSeconds}s). Previous results stay visible below.`
                  : "Refreshing with your new filter selection."}
              </p>
            </div>
          </div>
        </div>
      ) : null}
      {children}
    </div>
  );
}
