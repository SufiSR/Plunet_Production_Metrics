"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";

export function useAdminSession(loginNextPath = "/admin") {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await adminApiClient.me();
        if (cancelled) return;
        if (me.role !== "admin") {
          router.push(`/admin/login?next=${encodeURIComponent(loginNextPath)}`);
          return;
        }
        setUsername(me.username);
        setReady(true);
      } catch {
        if (!cancelled) {
          router.push(`/admin/login?next=${encodeURIComponent(loginNextPath)}`);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loginNextPath, router]);

  return { ready, username };
}
