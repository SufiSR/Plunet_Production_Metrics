"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import {
  IngestionLiveProgress,
  type IngestionProgressSnapshot,
} from "@/app/components/admin-new/IngestionLiveProgress";
import { PipelineRuntimeTimeline } from "@/app/components/admin-new/PipelineRuntimeTimeline";
import { SyncLogCard } from "@/app/components/admin-new/SyncLogCard";
import {
  adminApiClient,
  type AdminPipelineSyncLatestResponse,
} from "@/lib/admin-api-client";
import { isPipelineSyncRunning, usePipelineSyncPoll } from "@/lib/hooks/use-pipeline-sync-poll";
import { useAdminSession } from "@/lib/hooks/use-admin-session";

export default function AdminNewHrworksIngestionPage() {
  const { ready } = useAdminSession("/admin/ingestion/hrworks");
  const [latest, setLatest] = useState<AdminPipelineSyncLatestResponse | null>(null);
  const [pollActive, setPollActive] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const data = await adminApiClient.getLatestHrworksSync();
    setLatest(data);
    return data;
  }, []);

  useEffect(() => {
    if (!ready) return;
    void refresh().catch(() => setLatest(null));
  }, [ready, refresh]);

  usePipelineSyncPoll(pollActive, refresh, (data) => {
    setLatest(data);
    if (!isPipelineSyncRunning(data)) {
      setPollActive(false);
    }
  });

  const syncRunning = pollActive || isPipelineSyncRunning(latest);
  const runtime = latest?.sync_log?.details_json?.pipeline_runtime as
    | Record<string, unknown>
    | undefined;
  const progress = useMemo(
    () => runtime?.progress as IngestionProgressSnapshot | undefined,
    [runtime],
  );

  async function trigger(incremental: boolean) {
    setRunError(null);
    try {
      await adminApiClient.triggerHrworksSync(incremental);
      setPollActive(true);
      window.setTimeout(() => void refresh(), 500);
    } catch (e) {
      setPollActive(false);
      setRunError(e instanceof Error ? e.message : "Sync trigger failed");
    }
  }

  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="h-12 w-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="w-full pb-16 space-y-8">
      <AdminNewPageHeader
        eyebrow="Ingestion"
        title="HRWorks capacity"
        description="Weekly scheduled sync of available hours for Developer and QA roles."
      />

      <p className="text-sm text-on-surface-variant -mt-4">
        Schedule:{" "}
        <Link href="/admin/schedulers" className="text-primary hover:underline">
          Schedulers
        </Link>
        . Credentials:{" "}
        <Link href="/admin/secrets" className="text-primary hover:underline">
          Secrets & credentials
        </Link>{" "}
        (environment variables today).
      </p>

      <section className="elevated-panel p-8 rounded-2xl space-y-4">
        <h2 className="text-xl font-editorial font-semibold">Run sync</h2>
        <p className="text-sm text-on-surface-variant">
          <strong>Incremental:</strong> past 3 months, current month, and next 6 forecast months
          (configurable via <code className="text-xs">hrworks.incremental_*</code> in configuration).
          <strong className="ml-2">Full:</strong> 2024–2025, year-to-date, and forecast backfill.
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => void trigger(false)}
            disabled={syncRunning}
            className="px-5 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-editorial font-bold uppercase tracking-wider disabled:opacity-50"
          >
            Full sync
          </button>
          <button
            type="button"
            onClick={() => void trigger(true)}
            disabled={syncRunning}
            className="px-5 py-2.5 rounded-xl border border-outline-variant text-sm font-editorial font-medium disabled:opacity-50"
          >
            Incremental sync
          </button>
        </div>
        {runError ? <p className="text-xs text-error">{runError}</p> : null}
        <IngestionLiveProgress progress={progress} isRunning={syncRunning} />
      </section>

      <SyncLogCard title="Last run" data={latest} loading={syncRunning} />

      {runtime ? (
        <PipelineRuntimeTimeline runtime={runtime as Parameters<typeof PipelineRuntimeTimeline>[0]["runtime"]} />
      ) : null}

      <section className="rounded-2xl border border-dashed border-outline-variant/30 p-6 text-sm text-on-surface-variant">
        <h3 className="font-editorial font-semibold text-on-surface mb-2">Ingestion rules (planned)</h3>
        <p>
          Backfill start date, incremental months, denied person IDs, and roster refresh will be editable here once
          exposed via <code>PATCH /admin/ingestion/hrworks</code>.
        </p>
      </section>
    </div>
  );
}
