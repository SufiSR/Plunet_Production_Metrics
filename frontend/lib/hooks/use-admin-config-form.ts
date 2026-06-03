"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApiClient } from "@/lib/admin-api-client";
import type { AdminConfigPatch, AdminConfigResponse } from "@/types/admin";

type SaveState = "idle" | "saving" | "success" | "error";

function countDraftFields(patch: AdminConfigPatch): number {
  return Object.keys(patch).filter((k) => patch[k as keyof AdminConfigPatch] !== undefined).length;
}

export function useAdminConfigForm() {
  const [config, setConfig] = useState<AdminConfigResponse | null>(null);
  const [patch, setPatch] = useState<AdminConfigPatch>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const cfg = await adminApiClient.getConfig();
      setConfig(cfg);
      return cfg;
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load configuration");
      return null;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handlePatch = useCallback((updates: AdminConfigPatch) => {
    setPatch((prev) => ({ ...prev, ...updates }));
    setSaveState("idle");
    setSaveError(null);
  }, []);

  const handleDiscard = useCallback(() => {
    setPatch({});
    setSaveState("idle");
    setSaveError(null);
  }, []);

  const handleSave = useCallback(async () => {
    if (!config) return false;
    setSaveState("saving");
    setSaveError(null);
    try {
      const updated = await adminApiClient.patchConfig(patch);
      setConfig(updated);
      setPatch({});
      setSaveState("success");
      window.setTimeout(() => setSaveState("idle"), 3000);
      return true;
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof Error ? err.message : "Save failed");
      return false;
    }
  }, [config, patch]);

  return {
    config,
    patch,
    loadError,
    saveState,
    saveError,
    unsavedCount: countDraftFields(patch),
    handlePatch,
    handleDiscard,
    handleSave,
    reload: load,
  };
}
