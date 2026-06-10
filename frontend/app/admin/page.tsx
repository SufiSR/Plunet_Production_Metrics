"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import { SyncLogCard } from "@/app/components/admin-new/SyncLogCard";
import { adminApiClient, type AdminPipelineSyncLatestResponse } from "@/lib/admin-api-client";
import { useAdminSession } from "@/lib/hooks/use-admin-session";
import type { SyncStatusResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

function toDoraCardData(sync: SyncStatusResponse | null): AdminPipelineSyncLatestResponse | null {
  if (!sync) return null;
  if (sync.pipeline_in_progress && sync.pipeline_run_started_at) {
    return {
      status: "running",
      sync_log: {
        id: 0,
        source: "dora",
        started_at: sync.pipeline_run_started_at,
        finished_at: null,
        records_processed: null,
        error_message: null,
        details_json: { trigger: sync.pipeline_run_trigger },
      },
    };
  }
  if (!sync.last_sync) {
    return {
      status: null,
      sync_log: null,
    };
  }
  return {
    status: sync.last_sync.status,
    sync_log: {
      id: 0,
      source: "dora",
      started_at: sync.last_sync.started_at,
      finished_at: sync.last_sync.finished_at,
      records_processed: null,
      error_message: sync.last_sync.error_message ?? null,
      details_json: { trigger: sync.last_sync.trigger ?? null },
    },
  };
}

export default function AdminNewOverviewPage() {
  const { ready } = useAdminSession("/admin");
  const [doraSync, setDoraSync] = useState<SyncStatusResponse | null>(null);
  const [hrworks, setHrworks] = useState<AdminPipelineSyncLatestResponse | null>(null);
  const [jiraAnalytics, setJiraAnalytics] = useState<AdminPipelineSyncLatestResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      try {
        const [syncRes, hr, ja] = await Promise.all([
          fetch(`${API_BASE}/sync/status`, { headers: { Accept: "application/json" } }),
          adminApiClient.getLatestHrworksSync(),
          adminApiClient.getLatestJiraAnalyticsSync(),
        ]);
        if (cancelled) return;
        if (syncRes.ok) {
          setDoraSync((await syncRes.json()) as SyncStatusResponse);
        }
        setHrworks(hr);
        setJiraAnalytics(ja);
      } catch (e) {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : "Failed to load status");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready]);

  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="h-12 w-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="w-full pb-16">
      <AdminNewPageHeader
        eyebrow="Operations"
        title="Overview"
        description="Health of all ingestion pipelines and shortcuts into setup and diagnostics. This preview console uses the same admin session as the legacy /admin area."
      />

      {loadError ? (
        <p className="text-sm text-error mb-6" role="alert">
          {loadError}
        </p>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
        <SyncLogCard
          title="DORA pipeline"
          data={toDoraCardData(doraSync)}
          emptyHint="No public sync status yet."
        />
        <SyncLogCard title="HRWorks sync" data={hrworks} emptyHint="No HRWorks sync log yet." />
        <SyncLogCard
          title="Jira Analytics sync"
          data={jiraAnalytics}
          emptyHint="No Jira Analytics sync log yet. Configure schedule under Schedulers."
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="elevated-panel rounded-2xl p-6">
          <h2 className="text-lg font-editorial font-semibold mb-4">Ingestion</h2>
          <ul className="space-y-2 text-sm">
            <li>
              <Link href="/admin/ingestion/dora" className="text-primary hover:underline">
                DORA nightly pipeline
              </Link>
            </li>
            <li>
              <Link href="/admin/ingestion/hrworks" className="text-primary hover:underline">
                HRWorks capacity
              </Link>
            </li>
            <li>
              <Link href="/admin/ingestion/jira-analytics" className="text-primary hover:underline">
                Jira Analytics warehouse
              </Link>
            </li>
          </ul>
        </section>
        <section className="elevated-panel rounded-2xl p-6">
          <h2 className="text-lg font-editorial font-semibold mb-4">Setup & diagnostics</h2>
          <ul className="space-y-2 text-sm">
            <li>
              <Link href="/admin/schedulers" className="text-primary hover:underline">
                Schedulers (all pipelines)
              </Link>
            </li>
            <li>
              <Link href="/admin/secrets" className="text-primary hover:underline">
                Secrets & credentials
              </Link>
            </li>
            <li>
              <Link href="/admin/jira-analytics/assignments" className="text-primary hover:underline">
                User & team assignments
              </Link>
            </li>
            <li>
              <Link href="/admin/people-data-users" className="text-primary hover:underline">
                People-data users
              </Link>
            </li>
            <li>
              <Link href="/admin/jira-analytics/feature-families" className="text-primary hover:underline">
                Feature families
              </Link>
            </li>
            <li>
              <Link href="/admin/dora/linkage-health" className="text-primary hover:underline">
                DORA linkage data health
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
