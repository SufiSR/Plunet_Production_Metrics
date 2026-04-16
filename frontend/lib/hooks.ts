"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./api-client";
import { queryKeys } from "./query-keys";
import { useUIStore } from "./store";

export function useMetricsCurrent() {
  const period = useUIStore((s) => s.period);
  return useQuery({
    queryKey: queryKeys.metricsCurrent(period),
    queryFn: () => apiClient.getMetricsCurrent(period),
  });
}

export function useMetricsHistory() {
  const period = useUIStore((s) => s.period);
  return useQuery({
    queryKey: queryKeys.metricsHistory(period),
    queryFn: () => apiClient.getMetricsHistory(period),
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
