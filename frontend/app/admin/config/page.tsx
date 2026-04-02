"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import type { AdminConfigResponse, AdminConfigPatch } from "@/types/admin";
import { GitLabConfigSection } from "@/app/components/admin/GitLabConfigSection";
import { JiraConfigSection } from "@/app/components/admin/JiraConfigSection";
import { SchedulerConfigSection } from "@/app/components/admin/SchedulerConfigSection";
import { WebhookConfigSection } from "@/app/components/admin/WebhookConfigSection";
import { UnsavedToast } from "@/app/components/admin/UnsavedToast";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

type SaveState = "idle" | "saving" | "success" | "error";
type SyncState = "idle" | "triggering" | "triggered" | "error";

type PipelinePollState = {
  inProgress: boolean;
  startedAt: string | null;
  trigger: string | null;
};

async function fetchPipelineSyncStatus(): Promise<PipelinePollState> {
  const res = await fetch(`${API_BASE}/sync/status`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Sync status HTTP ${res.status}`);
  }
  const body = (await res.json()) as {
    pipeline_in_progress?: boolean;
    pipeline_run_started_at?: string | null;
    pipeline_run_trigger?: string | null;
  };
  return {
    inProgress: Boolean(body.pipeline_in_progress),
    startedAt: body.pipeline_run_started_at ?? null,
    trigger: body.pipeline_run_trigger ?? null,
  };
}

function countDraftFields(patch: AdminConfigPatch): number {
  return Object.keys(patch).filter(
    (k) => patch[k as keyof AdminConfigPatch] !== undefined
  ).length;
}

export default function AdminConfigPage() {
  const router = useRouter();
  const [config, setConfig] = useState<AdminConfigResponse | null>(null);
  const [patch, setPatch] = useState<AdminConfigPatch>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncError, setSyncError] = useState<string | null>(null);
  const [pipelineLive, setPipelineLive] = useState<PipelinePollState | null>(null);
  const [pipelinePhase, setPipelinePhase] = useState<
    "idle" | "waiting_for_start" | "running" | "completed" | "stale_poll"
  >("idle");
  const pollStopRef = useRef<(() => void) | null>(null);

  // Auth guard + load config
  useEffect(() => {
    (async () => {
      try {
        const me = await adminApiClient.me();
        if (me.role !== "admin") {
          router.push("/admin/login");
          return;
        }
        const cfg = await adminApiClient.getConfig();
        setConfig(cfg);
      } catch {
        router.push("/admin/login");
      }
    })();
  }, [router]);

  const handlePatch = useCallback((updates: AdminConfigPatch) => {
    setPatch((prev) => ({ ...prev, ...updates }));
    setSaveState("idle");
    setSaveError(null);
  }, []);

  const handleSave = useCallback(async () => {
    if (!config) return;
    setSaveState("saving");
    setSaveError(null);
    try {
      const updated = await adminApiClient.patchConfig(patch);
      setConfig(updated);
      setPatch({});
      setSaveState("success");
      setTimeout(() => setSaveState("idle"), 3000);
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof Error ? err.message : "Save failed");
    }
  }, [config, patch]);

  const handleDiscard = useCallback(() => {
    setPatch({});
    setSaveState("idle");
    setSaveError(null);
  }, []);

  const handleTriggerSync = useCallback(async () => {
    setSyncState("triggering");
    setSyncError(null);
    setPipelinePhase("idle");
    setPipelineLive(null);
    pollStopRef.current?.();
    pollStopRef.current = null;
    try {
      await adminApiClient.triggerSync();
      setSyncState("triggered");
      setPipelinePhase("waiting_for_start");

      let sawRunning = false;
      let polls = 0;
      const maxPolls = 900;
      const t = window.setInterval(async () => {
        polls += 1;
        try {
          const s = await fetchPipelineSyncStatus();
          setPipelineLive(s);
          if (s.inProgress) {
            sawRunning = true;
            setPipelinePhase("running");
          } else if (sawRunning) {
            setPipelinePhase("completed");
            window.clearInterval(t);
            pollStopRef.current = null;
            setSyncState("idle");
            window.setTimeout(() => {
              setPipelinePhase("idle");
              setPipelineLive(null);
            }, 8000);
            return;
          }
          if (!sawRunning && polls >= 25) {
            setPipelinePhase("stale_poll");
            window.clearInterval(t);
            pollStopRef.current = null;
            setSyncState("idle");
          }
          if (polls >= maxPolls) {
            window.clearInterval(t);
            pollStopRef.current = null;
            setSyncState("idle");
          }
        } catch {
          if (polls >= 25 && !sawRunning) {
            setPipelinePhase("stale_poll");
            window.clearInterval(t);
            pollStopRef.current = null;
            setSyncState("idle");
          }
        }
      }, 2000);
      pollStopRef.current = () => {
        window.clearInterval(t);
        pollStopRef.current = null;
      };

      window.setTimeout(() => setSyncState("idle"), 4000);
    } catch (err) {
      setSyncState("error");
      setSyncError(err instanceof Error ? err.message : "Failed to trigger sync");
    }
  }, []);

  useEffect(
    () => () => {
      pollStopRef.current?.();
    },
    []
  );

  if (loadError) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-4">
          <span className="material-symbols-outlined text-4xl text-error">
            error
          </span>
          <p className="text-on-surface-variant font-editorial">{loadError}</p>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="space-y-3 w-full max-w-xl px-12">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-48 bg-surface-container animate-pulse rounded-2xl"
            />
          ))}
        </div>
      </div>
    );
  }

  const unsavedCount = countDraftFields(patch);

  return (
    <div className="px-12 py-10 max-w-5xl w-full mx-auto pb-32">
      {/* Editorial header */}
      <header className="mb-16">
        <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary mb-2">
          Configuration
        </p>
        <h1 className="text-5xl font-editorial font-bold tracking-tight text-on-surface mb-4">
          Integrations Pipeline
        </h1>
        <p className="text-on-surface-variant max-w-2xl leading-relaxed text-sm">
          Manage your external engineering toolchain. Securely connect your
          version control systems and issue trackers to the Editorial Engine.
        </p>
      </header>

      {/* Success banner */}
      {saveState === "success" && (
        <div
          role="status"
          className="flex items-center gap-3 px-4 py-3 rounded-xl bg-secondary-container text-on-secondary-container text-xs font-editorial mb-8"
        >
          <span className="material-symbols-outlined text-base shrink-0">
            check_circle
          </span>
          Configuration saved successfully.
        </div>
      )}

      {/* Error banner */}
      {saveState === "error" && saveError && (
        <div
          role="alert"
          className="flex items-center gap-3 px-4 py-3 rounded-xl bg-error-container text-on-error-container text-xs font-editorial mb-8"
        >
          <span className="material-symbols-outlined text-base shrink-0">
            error
          </span>
          {saveError}
        </div>
      )}

      {/* Manual sync trigger */}
      <section className="bg-surface-container-lowest p-10 rounded-2xl mb-12">
        <div className="flex items-start justify-between gap-8">
          <div>
            <h2 className="text-2xl font-editorial font-semibold tracking-tight text-on-surface mb-1">
              Data Pipeline
            </h2>
            <p className="text-sm text-on-surface-variant max-w-lg">
              Trigger a full retrieval run immediately — GitLab sync, Jira sync,
              cross-system linking, and snapshot generation. While a run is
              active, status is polled from the public sync API; backend logs
              print each phase (set <code className="text-xs">DORA_LOG_LEVEL=INFO</code>).
            </p>
          </div>

          <div className="flex flex-col items-end gap-3 shrink-0 max-w-md text-right">
            <button
              onClick={handleTriggerSync}
              disabled={syncState === "triggering" || pipelinePhase === "running"}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-on-primary text-sm font-editorial font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              <span
                className={`material-symbols-outlined text-base leading-none ${
                  syncState === "triggering" ? "animate-spin" : ""
                }`}
              >
                {syncState === "triggering" ? "autorenew" : "play_arrow"}
              </span>
              {syncState === "triggering" ? "Starting…" : "Run Now"}
            </button>

            {pipelinePhase === "waiting_for_start" && (
              <p className="flex items-center justify-end gap-1.5 text-xs text-on-surface-variant font-editorial">
                <span className="material-symbols-outlined text-sm leading-none animate-spin">
                  progress_activity
                </span>
                Waiting for pipeline to register (polling sync status)…
              </p>
            )}
            {pipelinePhase === "running" && pipelineLive?.inProgress && (
              <p className="flex flex-col items-end gap-1 text-xs text-primary font-editorial">
                <span className="flex items-center gap-1.5 font-bold uppercase tracking-wider">
                  <span className="material-symbols-outlined text-sm leading-none animate-spin">
                    sync
                  </span>
                  Pipeline running
                </span>
                {pipelineLive.trigger && (
                  <span className="text-on-surface-variant normal-case font-body">
                    Trigger: {pipelineLive.trigger}
                  </span>
                )}
                {pipelineLive.startedAt && (
                  <span className="text-on-surface-variant normal-case font-body">
                    Started {new Date(pipelineLive.startedAt).toLocaleString()}
                  </span>
                )}
              </p>
            )}
            {pipelinePhase === "completed" && (
              <p className="flex items-center justify-end gap-1.5 text-xs text-secondary font-editorial">
                <span className="material-symbols-outlined text-sm leading-none">
                  check_circle
                </span>
                Pipeline run finished (sync log closed).
              </p>
            )}
            {pipelinePhase === "stale_poll" && (
              <p className="flex items-start justify-end gap-1.5 text-xs text-amber-800 dark:text-amber-200 font-editorial text-left">
                <span className="material-symbols-outlined text-sm leading-none shrink-0 mt-0.5">
                  warning
                </span>
                No running pipeline appeared within ~50s. Check{" "}
                <code className="text-[10px]">docker logs</code> on the backend
                container — look for{" "}
                <code className="text-[10px]">sync_pipeline</code> or{" "}
                <code className="text-[10px]">admin requested manual</code>.
              </p>
            )}
            {syncState === "error" && syncError && (
              <p className="flex items-center justify-end gap-1.5 text-xs text-error font-editorial">
                <span className="material-symbols-outlined text-sm leading-none">
                  error
                </span>
                {syncError}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Form sections */}
      <div className="space-y-12">
        <GitLabConfigSection config={config} patch={patch} onPatch={handlePatch} />
        <JiraConfigSection config={config} patch={patch} onPatch={handlePatch} />
        <SchedulerConfigSection config={config} patch={patch} onPatch={handlePatch} />
        <WebhookConfigSection config={config} patch={patch} onPatch={handlePatch} />
      </div>

      {/* Unsaved toast */}
      <UnsavedToast
        count={unsavedCount}
        onDiscard={handleDiscard}
        onSave={handleSave}
        isSaving={saveState === "saving"}
      />
    </div>
  );
}
