"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface UseAnalyticsReportLoadOptions<T> {
  load: (signal: AbortSignal) => Promise<T>;
  /** Dependencies that trigger a reload when changed (serialized internally). */
  deps: unknown[];
  slowAfterMs?: number;
}

export interface UseAnalyticsReportLoadResult<T> {
  data: T | null;
  error: string | null;
  /** True only before the first successful payload (full-page load state). */
  loading: boolean;
  /** True when reloading after data was already shown (keeps prior content visible). */
  refreshing: boolean;
  slowLoading: boolean;
  elapsedSeconds: number;
  retry: () => void;
}

export function useAnalyticsReportLoad<T>({
  load,
  deps,
  slowAfterMs = 10_000,
}: UseAnalyticsReportLoadOptions<T>): UseAnalyticsReportLoadResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [slowLoading, setSlowLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [reloadToken, setReloadToken] = useState(0);
  const loadRef = useRef(load);
  const dataRef = useRef<T | null>(null);
  loadRef.current = load;
  dataRef.current = data;

  const depsKey = JSON.stringify(deps);

  const retry = useCallback(() => {
    setReloadToken((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    const startedAt = Date.now();
    const hasExistingData = dataRef.current !== null;

    if (hasExistingData) {
      setRefreshing(true);
      setLoading(false);
    } else {
      setLoading(true);
      setRefreshing(false);
    }
    setError(null);
    setSlowLoading(false);
    setElapsedSeconds(0);

    const tick = window.setInterval(() => {
      if (cancelled) return;
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setElapsedSeconds(elapsed);
      if (elapsed * 1000 >= slowAfterMs) {
        setSlowLoading(true);
      }
    }, 1000);

    void (async () => {
      try {
        const result = await loadRef.current(controller.signal);
        if (cancelled || controller.signal.aborted) return;
        setData(result);
        dataRef.current = result;
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        if (!hasExistingData) {
          setData(null);
          dataRef.current = null;
        }
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load report");
      } finally {
        if (!cancelled && !controller.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
          setSlowLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(tick);
    };
  }, [depsKey, reloadToken, slowAfterMs]);

  return { data, error, loading, refreshing, slowLoading, elapsedSeconds, retry };
}
