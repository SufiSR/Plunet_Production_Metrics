"use client";

import { useCallback, useEffect, useState } from "react";
import { peopleDataApiClient } from "@/lib/people-data-api-client";

export function usePeopleDataSession() {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const session = await peopleDataApiClient.me();
      setAuthenticated(session.authenticated);
      setUsername(session.username);
    } catch {
      setAuthenticated(false);
      setUsername(null);
    } finally {
      setReady(true);
    }
  }, []);

  const logout = useCallback(async () => {
    await peopleDataApiClient.logout();
    setAuthenticated(false);
    setUsername(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const session = await peopleDataApiClient.me();
        if (cancelled) return;
        setAuthenticated(session.authenticated);
        setUsername(session.username);
      } catch {
        if (cancelled) return;
        setAuthenticated(false);
        setUsername(null);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { ready, authenticated, username, refresh, logout };
}
