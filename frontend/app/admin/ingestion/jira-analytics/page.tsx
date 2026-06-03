"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import { PipelineRuntimeTimeline } from "@/app/components/admin-new/PipelineRuntimeTimeline";
import { SyncLogCard } from "@/app/components/admin-new/SyncLogCard";
import {
  adminApiClient,
  type AdminPipelineSyncLatestResponse,
  type JiraAnalyticsAllocationRebuildResponse,
} from "@/lib/admin-api-client";
import { useAdminConfigForm } from "@/lib/hooks/use-admin-config-form";
import { useAdminSession } from "@/lib/hooks/use-admin-session";

const JA_PHASES = ["ingestion", "workflow_sync", "feature_membership", "allocation", "complete"];
const REBUILD_STATUS_POLL_MS = 2000;
const REBUILD_STATUS_MAX_POLLS = 300;

function rebuildSuccessMessage(result: JiraAnalyticsAllocationRebuildResponse) {
  const rows = result.allocation_rows ?? 0;
  const periods = result.periods?.length ?? 0;
  return (
    result.message ??
    `Rebuilt ${rows} allocation row${rows === 1 ? "" : "s"} across ${periods} month${periods === 1 ? "" : "s"}.`
  );
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function AdminNewJiraAnalyticsIngestionPage() {
  const { ready } = useAdminSession("/admin/ingestion/jira-analytics");
  const { config } = useAdminConfigForm();
  const [latest, setLatest] = useState<AdminPipelineSyncLatestResponse | null>(null);
  const [updatedAfterDays, setUpdatedAfterDays] = useState("");
  const [syncState, setSyncState] = useState<"idle" | "running" | "error">("idle");
  const [syncError, setSyncError] = useState<string | null>(null);
  const [rebuildState, setRebuildState] = useState<"idle" | "running" | "success" | "error">("idle");
  const [rebuildMessage, setRebuildMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const data = await adminApiClient.getLatestJiraAnalyticsSync();
    setLatest(data);
    return data;
  }, []);

  useEffect(() => {
    if (!ready) return;
    void refresh().catch(() => setLatest(null));
  }, [ready, refresh]);

  async function triggerSync() {
    setSyncState("running");
    setSyncError(null);
    const trimmed = updatedAfterDays.trim();
    let days: number | undefined;
    if (trimmed !== "") {
      days = Number(trimmed);
      if (!Number.isFinite(days) || days < 1 || days > 3650) {
        setSyncState("error");
        setSyncError("Updated-after days must be between 1 and 3650.");
        return;
      }
    }
    try {
      await adminApiClient.triggerJiraAnalyticsSync(days);
      window.setTimeout(() => void refresh(), 4000);
      setSyncState("idle");
    } catch (e) {
      setSyncState("error");
      setSyncError(e instanceof Error ? e.message : "Failed to trigger sync");
    }
  }

  async function rebuildAllocation() {
    setRebuildState("running");
    setRebuildMessage(null);
    try {
      let result: JiraAnalyticsAllocationRebuildResponse =
        await adminApiClient.rebuildJiraAnalyticsAllocation();
      setRebuildMessage(result.message ?? "Allocation rebuild started.");

      for (let attempt = 0; result.state === "running" && attempt < REBUILD_STATUS_MAX_POLLS; attempt += 1) {
        await delay(REBUILD_STATUS_POLL_MS);
        result = await adminApiClient.getJiraAnalyticsAllocationRebuildStatus();
        setRebuildMessage(result.message ?? "Allocation rebuild is still running.");
      }

      if (result.state === "running") {
        setRebuildMessage("Allocation rebuild is still running. You can refresh this page to check again.");
        return;
      }
      if (result.state === "failed") {
        throw new Error(result.error ?? result.message ?? "Allocation rebuild failed");
      }

      setRebuildState("success");
      setRebuildMessage(rebuildSuccessMessage(result));
      await refresh();
    } catch (e) {
      setRebuildState("error");
      setRebuildMessage(e instanceof Error ? e.message : "Rebuild failed");
    }
  }

  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="h-12 w-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  const runtime = latest?.sync_log?.details_json?.pipeline_runtime as
    | Record<string, unknown>
    | undefined;

  return (
    <div className="w-full pb-16 space-y-8">
      <AdminNewPageHeader
        eyebrow="Ingestion"
        title="Jira Analytics warehouse"
        description="Jira issue/worklog ingestion, workflow definitions, feature membership, and monthly allocation. Separate from the DORA nightly pipeline."
      />

      <p className="text-sm text-on-surface-variant -mt-4">
        Requires{" "}
        <Link href="/admin/secrets" className="text-primary hover:underline">
          Jira credentials
        </Link>
        ,{" "}
        <Link href="/admin/schedulers" className="text-primary hover:underline">
          scheduler defaults
        </Link>
        , and{" "}
        <Link href="/admin/jira-analytics/assignments" className="text-primary hover:underline">
          user assignments
        </Link>
        .
      </p>

      <section className="elevated-panel p-8 rounded-2xl space-y-4">
        <h2 className="text-xl font-editorial font-semibold">Run full sync</h2>
        <p className="text-sm text-on-surface-variant">
          Ingestion → workflow sync → feature membership → allocation (when ingestion succeeds). Only issues
          with <code className="text-xs">updated</code> in the lookback window are fetched.
        </p>
        <div className="flex flex-col sm:flex-row sm:items-end gap-4 max-w-md">
          <div className="space-y-2 flex-1">
            <label
              htmlFor="updated_after_days"
              className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
            >
              Updated in last N days
            </label>
            <input
              id="updated_after_days"
              type="number"
              min={1}
              max={3650}
              placeholder={
                config
                  ? String(config.jira_analytics_scheduled_lookback_days)
                  : "14"
              }
              value={updatedAfterDays}
              onChange={(e) => setUpdatedAfterDays(e.target.value)}
              className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:border-primary focus:outline-none font-editorial text-on-surface"
            />
            <p className="text-[10px] text-outline px-1">
              Leave empty to use scheduler default (
              {config?.jira_analytics_scheduled_lookback_days ?? "…"} days).
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void triggerSync()}
          disabled={syncState === "running"}
          className="px-5 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-editorial font-bold uppercase tracking-wider disabled:opacity-50"
        >
          {syncState === "running" ? "Triggered…" : "Run Jira Analytics sync"}
        </button>
        {syncError ? <p className="text-xs text-error">{syncError}</p> : null}
      </section>

      <section className="elevated-panel p-8 rounded-2xl space-y-4">
        <h2 className="text-xl font-editorial font-semibold">Rebuild allocation</h2>
        <p className="text-sm text-on-surface-variant">
          Recompute monthly allocated effort from worklogs and assignments without a full Jira re-ingest.
        </p>
        <button
          type="button"
          onClick={() => void rebuildAllocation()}
          disabled={rebuildState === "running"}
          className="px-5 py-2.5 rounded-xl border border-outline-variant text-sm font-editorial font-medium disabled:opacity-50"
        >
          {rebuildState === "running" ? "Rebuilding…" : "Rebuild all months"}
        </button>
        {rebuildMessage ? (
          <p className={`text-xs ${rebuildState === "error" ? "text-error" : "text-secondary"}`}>{rebuildMessage}</p>
        ) : null}
      </section>

      <SyncLogCard title="Last run" data={latest} />

      {runtime ? (
        <PipelineRuntimeTimeline
          runtime={runtime as Parameters<typeof PipelineRuntimeTimeline>[0]["runtime"]}
          phaseOrder={JA_PHASES}
        />
      ) : null}

      {latest?.sync_log?.details_json?.updated_after_days != null ? (
        <p className="text-xs text-on-surface-variant">
          Last run lookback: {String(latest.sync_log.details_json.updated_after_days)} days (
          <code className="text-[10px]">updated &gt;=</code> filter).
        </p>
      ) : null}
    </div>
  );
}
