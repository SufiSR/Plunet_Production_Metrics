"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { adminApiClient } from "@/lib/admin-api-client";
import type { PipelineRuntimeBlock, SyncStatusResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

const PIPELINE_PHASES: Array<{ key: string; label: string }> = [
  { key: "gitlab", label: "GitLab" },
  { key: "jira", label: "Jira" },
  { key: "derivations", label: "Derivations" },
  { key: "snapshots", label: "Snapshots" },
  { key: "complete", label: "Complete" },
];

type PipelinePollState = {
  inProgress: boolean;
  startedAt: string | null;
  trigger: string | null;
  runtime: PipelineRuntimeBlock | null;
};

async function fetchPipelineSyncStatus(): Promise<PipelinePollState> {
  const res = await fetch(`${API_BASE}/sync/status`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Sync status HTTP ${res.status}`);
  const body = (await res.json()) as Partial<SyncStatusResponse>;
  return {
    inProgress: Boolean(body.pipeline_in_progress),
    startedAt: body.pipeline_run_started_at ?? null,
    trigger: body.pipeline_run_trigger ?? null,
    runtime: body.pipeline_runtime ?? null,
  };
}

function phaseIcon(status?: string): string {
  if (status === "running") return "sync";
  if (status === "success") return "check_circle";
  if (status === "failed") return "error";
  if (status === "skipped") return "skip_next";
  return "radio_button_unchecked";
}

function phaseTextClass(status?: string): string {
  if (status === "running") return "text-primary";
  if (status === "success") return "text-secondary";
  if (status === "failed") return "text-error";
  return "text-on-surface-variant";
}

export function DoraPipelineRunPanel() {
  const [syncState, setSyncState] = useState<"idle" | "triggering" | "triggered" | "error">("idle");
  const [syncError, setSyncError] = useState<string | null>(null);
  const [pipelineLive, setPipelineLive] = useState<PipelinePollState | null>(null);
  const [pipelinePhase, setPipelinePhase] = useState<
    "idle" | "waiting_for_start" | "running" | "completed" | "stale_poll"
  >("idle");
  const pollStopRef = useRef<(() => void) | null>(null);

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
          if (polls >= 900) {
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
    [],
  );

  return (
    <section className="elevated-panel p-8 rounded-2xl">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
        <div>
          <h2 className="text-xl font-editorial font-semibold text-on-surface mb-1">Run pipeline</h2>
          <p className="text-sm text-on-surface-variant max-w-xl">
            GitLab sync, Jira bug collection, cross-system linking, and DORA snapshot generation. Independent
            from Jira Analytics and HRWorks ingestion.
          </p>
        </div>
        <div className="flex flex-col items-stretch lg:items-end gap-3 shrink-0">
          <button
            type="button"
            onClick={() => void handleTriggerSync()}
            disabled={syncState === "triggering" || pipelinePhase === "running"}
            className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-primary text-on-primary text-sm font-editorial font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-50"
          >
            <span
              className={`material-symbols-outlined text-base ${syncState === "triggering" ? "animate-spin" : ""}`}
            >
              {syncState === "triggering" ? "autorenew" : "play_arrow"}
            </span>
            {syncState === "triggering" ? "Starting…" : "Run pipeline"}
          </button>
          {pipelinePhase === "running" && pipelineLive?.runtime ? (
            <div className="w-full max-w-sm rounded-xl border border-outline-variant/20 p-3 text-xs space-y-1.5">
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant">
                Phase: {pipelineLive.runtime.current_phase}
              </p>
              {PIPELINE_PHASES.map((phase) => {
                const phaseState = pipelineLive.runtime?.phases?.[phase.key];
                const status = phaseState?.status ?? "pending";
                return (
                  <div key={phase.key} className={`flex justify-between gap-2 ${phaseTextClass(status)}`}>
                    <span className="flex items-center gap-1">
                      <span
                        className={`material-symbols-outlined text-sm ${status === "running" ? "animate-spin" : ""}`}
                      >
                        {phaseIcon(status)}
                      </span>
                      {phase.label}
                    </span>
                    <span className="uppercase text-[10px]">{status}</span>
                  </div>
                );
              })}
            </div>
          ) : null}
          {syncError ? <p className="text-xs text-error">{syncError}</p> : null}
        </div>
      </div>
    </section>
  );
}
