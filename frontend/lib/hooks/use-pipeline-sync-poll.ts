"use client";

import { useEffect, useRef } from "react";
import type { AdminPipelineSyncLatestResponse } from "@/lib/admin-api-client";

export function usePipelineSyncPoll(
  active: boolean,
  refresh: () => Promise<AdminPipelineSyncLatestResponse>,
  onUpdate: (data: AdminPipelineSyncLatestResponse) => void,
  intervalMs = 2000,
) {
  const refreshRef = useRef(refresh);
  const onUpdateRef = useRef(onUpdate);
  refreshRef.current = refresh;
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    if (!active) return;

    let cancelled = false;

    const tick = async () => {
      try {
        const data = await refreshRef.current();
        if (!cancelled) onUpdateRef.current(data);
      } catch {
        // keep polling — transient errors during long runs
      }
    };

    void tick();
    const timer = window.setInterval(() => void tick(), intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active, intervalMs]);
}

export function isPipelineSyncRunning(data: AdminPipelineSyncLatestResponse | null): boolean {
  const log = data?.sync_log;
  if (!log) return false;
  if (log.finished_at) return false;
  const status = (data.status ?? "").toLowerCase();
  return status === "running" || status === "";
}
