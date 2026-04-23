import type { LeadTimeBreakdown, PeriodType } from "@/types/api";
import type { AdminRawTableSortDirection } from "@/types/admin";

export const queryKeys = {
  metricsCurrent: (period: PeriodType, leadBreakdown: LeadTimeBreakdown) =>
    ["metrics", "current", period, leadBreakdown] as const,

  metricsHistory: (period: PeriodType, leadBreakdown: LeadTimeBreakdown) =>
    ["metrics", "history", period, leadBreakdown] as const,

  syncStatus: () => ["sync", "status"] as const,

  repositories: () => ["repositories"] as const,

  releaseTimeline: () => ["metrics", "releases", "timeline"] as const,

  releaseDrilldown: (page: number, repositoryId: number | null | undefined) =>
    ["metrics", "releases", "customer", "drilldown", page, repositoryId ?? "all"] as const,

  releaseMergeRequests: (
    repositoryId: number,
    tagName: string,
    page: number,
    size: number,
  ) => ["metrics", "releases", "customer", "mr", repositoryId, tagName, page, size] as const,

  releaseFailedDrilldown: (page: number, repositoryId: number | null | undefined) =>
    ["metrics", "releases", "customer", "failed", page, repositoryId ?? "all"] as const,

  releaseFailedIssues: (
    repositoryId: number,
    tagName: string,
    page: number,
    size: number,
  ) => ["metrics", "releases", "customer", "failed", "issues", repositoryId, tagName, page, size] as const,

  mttrAlphaSummary: (period: PeriodType) => ["metrics", "bugs", "mttr-alpha", "summary", period] as const,

  mttrAlphaIncidents: (
    period: PeriodType,
    page: number,
    size: number,
    firstFixReleaseTag: string | null | undefined,
  ) =>
    [
      "metrics",
      "bugs",
      "mttr-alpha",
      "incidents",
      period,
      page,
      size,
      firstFixReleaseTag ?? "all",
    ] as const,

  mttrAlphaReleases: (period: PeriodType, page: number, size: number) =>
    ["metrics", "bugs", "mttr-alpha", "releases", period, page, size] as const,

  adminDataHealth: (
    unmatchedPage: number,
    unmatchedSize: number,
    mismatchPage: number,
    mismatchSize: number,
  ) =>
    [
      "admin",
      "data-health",
      "unmatched",
      unmatchedPage,
      unmatchedSize,
      "mismatch",
      mismatchPage,
      mismatchSize,
    ] as const,

  adminRawTableRows: (
    table: string,
    page: number,
    size: number,
    search: string,
    sortBy: string | null,
    sortDir: AdminRawTableSortDirection,
  ) => ["admin", "raw-tables", table, page, size, search, sortBy ?? "default", sortDir] as const,
} as const;
