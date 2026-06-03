import type {
  CustomerReleaseDrilldownListResponse,
  FailedCustomerReleaseDrilldownListResponse,
  MetricsCurrentResponse,
  MetricsHistoryResponse,
  ReleaseMergeRequestListResponse,
  ReleaseProductionBugListResponse,
  RepositoriesResponse,
  ReleaseTimelineResponse,
  ReleaseWorklogHoursResponse,
  MttrAlphaSummaryResponse,
  MttrAlphaIncidentListResponse,
  MttrAlphaReleaseDrilldownListResponse,
  SyncStatusResponse,
  LeadTimeBreakdown,
  PeriodType,
} from "@/types/api";

import { parseApiErrorBody } from "@/lib/parse-api-error";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 0 }, // always client-side; no Next.js SSR caching
  });

  if (!res.ok) {
    let message = parseApiErrorBody(null, res.status);
    try {
      message = parseApiErrorBody(await res.json(), res.status);
    } catch {
      // ignore parse error
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

const backendPeriodType: Record<PeriodType, "WEEK" | "MONTH" | "QUARTER"> = {
  "30d": "WEEK",
  quarterly: "MONTH",
  yearly: "QUARTER",
};

function _leadTimeBreakdownQuery(leadTimeBreakdown: LeadTimeBreakdown): string {
  if (leadTimeBreakdown === "none") {
    return "";
  }
  return `&lead_time_breakdown=${encodeURIComponent(leadTimeBreakdown)}`;
}

function mapMetric(raw: any, kind: "deploy" | "lead" | "cfr" | "mttr", periodTypeForCadence?: PeriodType) {
  if (!raw || typeof raw !== "object") {
    return {
      value: null,
      unit: kind === "deploy" ? "deploys / week" : kind === "lead" ? "hours" : kind === "cfr" ? "%" : "minutes",
      dora_level: "UNKNOWN" as const,
      trend_pct: null,
    };
  }
  let value = typeof raw.value === "number" ? raw.value : null;
  let unit = "";
  let secondary_text: string | undefined = undefined;

  if (kind === "deploy") {
    unit = "deploys / week";
    if (value !== null) {
      if (periodTypeForCadence === "30d") {
        secondary_text = `~${Math.round(value * (30 / 7))} deploys this period`;
      } else if (periodTypeForCadence === "quarterly") {
        secondary_text = `~${Math.round(value * 13)} deploys this quarter`;
      } else if (periodTypeForCadence === "yearly") {
        secondary_text = `~${Math.round(value * 52)} deploys this year`;
      }
    }
  } else if (kind === "lead") {
    if (value !== null) value = value / 60.0;
    unit = "hours";
  } else if (kind === "cfr") {
    if (value !== null) value = value * 100.0;
    unit = "%";
  } else {
    unit = "minutes";
  }
  return {
    value,
    unit,
    dora_level: (raw.performance_level ?? "UNKNOWN") as
      | "ELITE"
      | "HIGH"
      | "MEDIUM"
      | "LOW"
      | "UNKNOWN",
    trend_pct: typeof raw.trend_percentage === "number" ? raw.trend_percentage : null,
    secondary_text,
  };
}

/** When there are no customer deployments in the window, CFR is undefined — not 0%. */
function applyCfrNoDataWhenNoDeploys(res: MetricsCurrentResponse): MetricsCurrentResponse {
  const dep = res.deployment_frequency?.value;
  const cfr = res.change_failure_rate?.value;
  if (dep === 0 && cfr === 0) {
    return {
      ...res,
      change_failure_rate: {
        ...res.change_failure_rate,
        value: null,
        dora_level: "UNKNOWN",
        trend_pct: null,
      },
    };
  }
  return res;
}

function normalizeMetricsCurrent(raw: any, period: PeriodType): MetricsCurrentResponse {
  if (raw && "lead_time_for_changes" in raw) {
    return applyCfrNoDataWhenNoDeploys(raw as MetricsCurrentResponse);
  }
  const leadMetric = mapMetric(raw?.release_wait_time ?? raw?.lead_time ?? raw?.mean_lead_time, "lead");
  const totalLeadHours =
    typeof raw?.lead_time?.value === "number" ? raw.lead_time.value / 60.0 : null;
  const devReviewHours =
    typeof raw?.dev_review_time?.value === "number" ? raw.dev_review_time.value / 60.0 : null;
  if (totalLeadHours !== null || devReviewHours !== null) {
    leadMetric.secondary_text = `Total lead ${
      totalLeadHours !== null ? `${totalLeadHours.toFixed(1)}h` : "—"
    } · dev/review ${
      devReviewHours !== null ? `${devReviewHours.toFixed(1)}h` : "—"
    }`;
  }
  return applyCfrNoDataWhenNoDeploys({
    generated_at: raw?.generated_at ?? null,
    period_label: raw?.period_end ?? "",
    deployment_frequency: mapMetric(raw?.deployment_frequency, "deploy", period),
    lead_time_for_changes: leadMetric,
    change_failure_rate: mapMetric(raw?.change_failure_rate, "cfr"),
    mttr_alpha: mapMetric(raw?.mttr_alpha ?? raw?.mttr, "mttr"),
    lead_time_diagnostics: raw?.lead_time_diagnostics ?? null,
    lead_time_by_branch: raw?.lead_time_by_branch ?? null,
    lead_time_by_stream: raw?.lead_time_by_stream ?? null,
  });
}

function _historyDateKey(iso: string): number {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : 0;
}

/** Backend returns periods newest-first; charts read best oldest → newest on the X axis. */
function _sortHistoryPointsChronologically<T extends { date: string }>(points: T[]): T[] {
  return [...points].sort((a, b) => _historyDateKey(a.date) - _historyDateKey(b.date));
}

/**
 * DEVOPS-515: Median total lead, median dev/review, and median release-wait are independent.
 * For stacked charts, scale the two segment values so they sum to the median total while
 * preserving the ratio of the two segment medians.
 */
function leadTimeStackHoursFromMedians(
  leadMinutes: number | null | undefined,
  devReviewMinutes: number | null | undefined,
  releaseWaitMinutes: number | null | undefined,
): { devH: number | null; waitH: number | null } {
  const totalH =
    typeof leadMinutes === "number" && Number.isFinite(leadMinutes) ? leadMinutes / 60.0 : null;
  if (totalH == null) {
    return {
      devH: typeof devReviewMinutes === "number" ? devReviewMinutes / 60.0 : null,
      waitH: typeof releaseWaitMinutes === "number" ? releaseWaitMinutes / 60.0 : null,
    };
  }
  if (
    typeof devReviewMinutes === "number" &&
    typeof releaseWaitMinutes === "number" &&
    devReviewMinutes + releaseWaitMinutes > 0
  ) {
    const dH = devReviewMinutes / 60.0;
    const wH = releaseWaitMinutes / 60.0;
    const sum = dH + wH;
    return {
      devH: totalH * (dH / sum),
      waitH: totalH * (wH / sum),
    };
  }
  return {
    devH: typeof devReviewMinutes === "number" ? devReviewMinutes / 60.0 : null,
    waitH: typeof releaseWaitMinutes === "number" ? releaseWaitMinutes / 60.0 : null,
  };
}

function normalizeMetricsHistory(raw: any, period: PeriodType): MetricsHistoryResponse {
  if (raw && "data_points" in raw) {
    const typed = raw as MetricsHistoryResponse;
    const mapped = typed.data_points.map((p) => {
      const base =
        p.deployment_frequency === 0 && p.change_failure_rate === 0
          ? { ...p, change_failure_rate: null }
          : p;
      const totalH = base.lead_time_for_changes;
      const devH = base.lead_time_dev_review_hours ?? null;
      const waitH = base.lead_time_release_wait_hours ?? null;
      if (totalH == null || devH == null || waitH == null) return base;
      const s = devH + waitH;
      if (s <= 0) return base;
      return {
        ...base,
        lead_time_dev_review_hours: totalH * (devH / s),
        lead_time_release_wait_hours: totalH * (waitH / s),
      };
    });
    return { ...typed, data_points: _sortHistoryPointsChronologically(mapped) };
  }
  const points = Array.isArray(raw?.data)
    ? raw.data.map((item: any) => {
        const leadMin = item?.lead_time_minutes;
        const { devH, waitH } = leadTimeStackHoursFromMedians(
          leadMin,
          item?.dev_review_median_minutes,
          item?.release_wait_median_minutes,
        );
        const dep =
          typeof item?.deployment_frequency === "number" ? item.deployment_frequency : null;
        const cfrPct =
          typeof item?.change_failure_rate === "number"
            ? item.change_failure_rate * 100.0
            : null;
        const cfrOut = dep === 0 && cfrPct === 0 ? null : cfrPct;
        return {
          date: item?.period_end ?? item?.period_start ?? "",
          deployment_frequency: dep,
          lead_time_for_changes:
            typeof leadMin === "number" && Number.isFinite(leadMin) ? leadMin / 60.0 : null,
          lead_time_dev_review_hours: devH,
          lead_time_release_wait_hours: waitH,
          lead_time_sample_count:
            typeof item?.lead_time_sample_count === "number"
              ? item.lead_time_sample_count
              : null,
          change_failure_rate: cfrOut,
          mttr_alpha:
            typeof item?.mttr_alpha_minutes === "number" ? item.mttr_alpha_minutes : null,
          lead_time_by_branch: item?.lead_time_by_branch ?? null,
          lead_time_by_stream: item?.lead_time_by_stream ?? null,
        };
      })
    : [];
  return {
    period,
    data_points: _sortHistoryPointsChronologically(points),
  };
}

function normalizeSyncStatus(raw: any): SyncStatusResponse {
  if (raw && "pipeline_in_progress" in raw && "last_sync" in raw) {
    return raw as SyncStatusResponse;
  }
  return {
    last_sync: null,
    last_successful_sync_at: raw?.last_sync_at ?? null,
    next_scheduled_sync: raw?.next_scheduled_sync ?? raw?.next_scheduled_sync_at ?? null,
    sync_schedule_cron: raw?.sync_schedule_cron ?? "0 2 * * *",
    pipeline_in_progress: Boolean(raw?.pipeline_in_progress),
    pipeline_run_started_at: raw?.pipeline_run_started_at ?? null,
    pipeline_run_trigger: raw?.pipeline_run_trigger ?? null,
    pipeline_runtime: raw?.pipeline_runtime ?? null,
  };
}

export const apiClient = {
  getMetricsCurrent: (period: PeriodType, leadTimeBreakdown: LeadTimeBreakdown = "none") =>
    request<any>(
      `/metrics/current?period_type=${backendPeriodType[period]}${_leadTimeBreakdownQuery(leadTimeBreakdown)}`
    ).then((raw) => normalizeMetricsCurrent(raw, period)),

  getMetricsHistory: (period: PeriodType, leadTimeBreakdown: LeadTimeBreakdown = "none") =>
    request<any>(
      `/metrics/history?period_type=${backendPeriodType[period]}${_leadTimeBreakdownQuery(leadTimeBreakdown)}`
    ).then((raw) => normalizeMetricsHistory(raw, period)),

  getSyncStatus: () => request<any>("/sync/status").then(normalizeSyncStatus),

  getRepositories: () => request<RepositoriesResponse>("/repositories"),

  getReleaseTimeline: () =>
    request<ReleaseTimelineResponse>("/metrics/releases/timeline?min_major=8&limit=3000"),

  getReleaseWorklogHours: (opts: { repositoryId: number; tagName: string }) => {
    const p = new URLSearchParams();
    p.set("repository_id", String(opts.repositoryId));
    p.set("tag_name", opts.tagName);
    return request<ReleaseWorklogHoursResponse>(
      `/metrics/releases/worklog-hours?${p.toString()}`,
    );
  },

  getReleaseDrilldown: (opts: {
    page?: number;
    size?: number;
    repositoryId?: number | null;
  }) => {
    const p = new URLSearchParams();
    p.set("page", String(opts.page ?? 0));
    p.set("size", String(opts.size ?? 20));
    if (opts.repositoryId != null && opts.repositoryId !== undefined) {
      p.set("repository_id", String(opts.repositoryId));
    }
    return request<CustomerReleaseDrilldownListResponse>(
      `/metrics/releases/customer/drilldown?${p.toString()}`,
    );
  },

  getReleaseMergeRequests: (opts: {
    repositoryId: number;
    tagName: string;
    page?: number;
    size?: number;
  }) => {
    const p = new URLSearchParams();
    p.set("repository_id", String(opts.repositoryId));
    p.set("tag_name", opts.tagName);
    p.set("page", String(opts.page ?? 0));
    p.set("size", String(opts.size ?? 50));
    return request<ReleaseMergeRequestListResponse>(
      `/metrics/releases/customer/merge-requests?${p.toString()}`,
    );
  },

  getFailedReleaseDrilldown: (opts: {
    page?: number;
    size?: number;
    repositoryId?: number | null;
  }) => {
    const p = new URLSearchParams();
    p.set("page", String(opts.page ?? 0));
    p.set("size", String(opts.size ?? 20));
    if (opts.repositoryId != null && opts.repositoryId !== undefined) {
      p.set("repository_id", String(opts.repositoryId));
    }
    return request<FailedCustomerReleaseDrilldownListResponse>(
      `/metrics/releases/customer/failed-drilldown?${p.toString()}`,
    );
  },

  getFailedReleaseIssues: (opts: {
    repositoryId: number;
    tagName: string;
    page?: number;
    size?: number;
  }) => {
    const p = new URLSearchParams();
    p.set("repository_id", String(opts.repositoryId));
    p.set("tag_name", opts.tagName);
    p.set("page", String(opts.page ?? 0));
    p.set("size", String(opts.size ?? 50));
    return request<ReleaseProductionBugListResponse>(
      `/metrics/releases/customer/failed/issues?${p.toString()}`,
    );
  },

  getMttrAlphaSummary: (period: PeriodType) =>
    request<MttrAlphaSummaryResponse>(
      `/metrics/bugs/mttr-alpha/summary?period_type=${backendPeriodType[period]}`,
    ),

  getMttrAlphaIncidents: (opts: {
    period: PeriodType;
    page?: number;
    size?: number;
    firstFixReleaseTag?: string | null;
  }) => {
    const p = new URLSearchParams();
    p.set("period_type", backendPeriodType[opts.period]);
    p.set("page", String(opts.page ?? 0));
    p.set("size", String(opts.size ?? 50));
    if (opts.firstFixReleaseTag) {
      p.set("first_fix_release_tag", opts.firstFixReleaseTag);
    }
    return request<MttrAlphaIncidentListResponse>(
      `/metrics/bugs/mttr-alpha/incidents?${p.toString()}`,
    );
  },

  getMttrAlphaReleases: (opts: {
    period: PeriodType;
    page?: number;
    size?: number;
  }) => {
    const p = new URLSearchParams();
    p.set("period_type", backendPeriodType[opts.period]);
    p.set("page", String(opts.page ?? 0));
    p.set("size", String(opts.size ?? 20));
    return request<MttrAlphaReleaseDrilldownListResponse>(
      `/metrics/bugs/mttr-alpha/releases?${p.toString()}`,
    );
  },
};
