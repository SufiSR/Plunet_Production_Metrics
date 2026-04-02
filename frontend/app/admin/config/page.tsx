"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import type { AdminConfigResponse, AdminConfigPatch } from "@/types/admin";
import { GitLabConfigSection } from "@/app/components/admin/GitLabConfigSection";
import { JiraConfigSection } from "@/app/components/admin/JiraConfigSection";
import { SchedulerConfigSection } from "@/app/components/admin/SchedulerConfigSection";
import { WebhookConfigSection } from "@/app/components/admin/WebhookConfigSection";
import { UnsavedToast } from "@/app/components/admin/UnsavedToast";

type SaveState = "idle" | "saving" | "success" | "error";

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
