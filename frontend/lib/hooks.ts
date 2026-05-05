"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApiClient } from "./admin-api-client";
import { apiClient } from "./api-client";
import { queryKeys } from "./query-keys";
import { useUIStore } from "./store";

function useEffectiveLeadBreakdown() {
  return useUIStore((s) =>
    s.trendOverviewMetric === "lead_time_for_changes" ? s.leadTimeBreakdown : "none"
  );
}

export function useMetricsCurrent() {
  const period = useUIStore((s) => s.period);
  const effectiveBreakdown = useEffectiveLeadBreakdown();
  return useQuery({
    queryKey: queryKeys.metricsCurrent(period, effectiveBreakdown),
    queryFn: () => apiClient.getMetricsCurrent(period, effectiveBreakdown),
  });
}

export function useMetricsHistory() {
  const period = useUIStore((s) => s.period);
  const effectiveBreakdown = useEffectiveLeadBreakdown();
  return useQuery({
    queryKey: queryKeys.metricsHistory(period, effectiveBreakdown),
    queryFn: () => apiClient.getMetricsHistory(period, effectiveBreakdown),
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: queryKeys.syncStatus(),
    queryFn: () => apiClient.getSyncStatus(),
    staleTime: 1000 * 60 * 5, // sync status refreshes more frequently (5 min)
    refetchInterval: 1000 * 60 * 5,
  });
}

export function useRepositories() {
  return useQuery({
    queryKey: queryKeys.repositories(),
    queryFn: () => apiClient.getRepositories(),
  });
}

export function useReleaseTimeline() {
  return useQuery({
    queryKey: queryKeys.releaseTimeline(),
    queryFn: () => apiClient.getReleaseTimeline(),
  });
}

export function useReleaseWorklogHours(
  repositoryId: number | null,
  tagName: string | null,
) {
  return useQuery({
    queryKey:
      repositoryId != null && tagName
        ? queryKeys.releaseWorklogHours(repositoryId, tagName)
        : ["metrics", "releases", "worklog-hours", "disabled"],
    queryFn: () =>
      apiClient.getReleaseWorklogHours({
        repositoryId: repositoryId!,
        tagName: tagName!,
      }),
    enabled: repositoryId != null && Boolean(tagName),
  });
}

export function useReleaseDrilldown(
  page: number,
  repositoryId: number | null | undefined,
  size = 20,
) {
  return useQuery({
    queryKey: queryKeys.releaseDrilldown(page, repositoryId),
    queryFn: () =>
      apiClient.getReleaseDrilldown({ page, size, repositoryId: repositoryId ?? undefined }),
  });
}

export function useReleaseMergeRequests(
  repositoryId: number | null,
  tagName: string | null,
  page: number,
  size = 50,
) {
  return useQuery({
    queryKey:
      repositoryId != null && tagName
        ? queryKeys.releaseMergeRequests(repositoryId, tagName, page, size)
        : ["metrics", "releases", "customer", "mr", "disabled"],
    queryFn: () =>
      apiClient.getReleaseMergeRequests({
        repositoryId: repositoryId!,
        tagName: tagName!,
        page,
        size,
      }),
    enabled: repositoryId != null && Boolean(tagName),
  });
}

export function useFailedReleaseDrilldown(
  page: number,
  repositoryId: number | null | undefined,
  size = 20,
) {
  return useQuery({
    queryKey: queryKeys.releaseFailedDrilldown(page, repositoryId),
    queryFn: () =>
      apiClient.getFailedReleaseDrilldown({ page, size, repositoryId: repositoryId ?? undefined }),
  });
}

export function useFailedReleaseIssues(
  repositoryId: number | null,
  tagName: string | null,
  page: number,
  size = 50,
) {
  return useQuery({
    queryKey:
      repositoryId != null && tagName
        ? queryKeys.releaseFailedIssues(repositoryId, tagName, page, size)
        : ["metrics", "releases", "customer", "failed", "issues", "disabled"],
    queryFn: () =>
      apiClient.getFailedReleaseIssues({
        repositoryId: repositoryId!,
        tagName: tagName!,
        page,
        size,
      }),
    enabled: repositoryId != null && Boolean(tagName),
  });
}

export function useMttrAlphaSummary() {
  const period = useUIStore((s) => s.period);
  return useQuery({
    queryKey: queryKeys.mttrAlphaSummary(period),
    queryFn: () => apiClient.getMttrAlphaSummary(period),
  });
}

export function useMttrAlphaIncidents(
  page: number,
  size = 50,
  firstFixReleaseTag: string | null = null,
) {
  const period = useUIStore((s) => s.period);
  return useQuery({
    queryKey: queryKeys.mttrAlphaIncidents(period, page, size, firstFixReleaseTag),
    queryFn: () =>
      apiClient.getMttrAlphaIncidents({
        period,
        page,
        size,
        firstFixReleaseTag,
      }),
  });
}

export function useMttrAlphaReleases(page: number, size = 20) {
  const period = useUIStore((s) => s.period);
  return useQuery({
    queryKey: queryKeys.mttrAlphaReleases(period, page, size),
    queryFn: () => apiClient.getMttrAlphaReleases({ period, page, size }),
  });
}

export function useAdminDataHealth(
  unmatchedPage: number,
  unmatchedSize = 20,
  mismatchPage = 0,
  mismatchSize = 20,
) {
  return useQuery({
    queryKey: queryKeys.adminDataHealth(
      unmatchedPage,
      unmatchedSize,
      mismatchPage,
      mismatchSize,
    ),
    queryFn: () =>
      adminApiClient.getDataHealth({
        unmatched_page: unmatchedPage,
        unmatched_size: unmatchedSize,
        mismatch_page: mismatchPage,
        mismatch_size: mismatchSize,
      }),
  });
}

export function useAdminRawTableRows(
  table: "sync_log" | "repository" | "release" | "production_bug" | "merge_request" | "issue_worklog",
  page: number,
  size = 20,
  search = "",
  sortBy: string | null = null,
  sortDir: "asc" | "desc" = "desc",
) {
  return useQuery({
    queryKey: queryKeys.adminRawTableRows(table, page, size, search, sortBy, sortDir),
    queryFn: () =>
      adminApiClient.getRawTableRows({
        table,
        page,
        size,
        search: search || undefined,
        sort_by: sortBy ?? undefined,
        sort_dir: sortDir,
      }),
  });
}
