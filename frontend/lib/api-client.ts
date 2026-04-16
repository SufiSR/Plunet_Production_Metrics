import type {
  CustomerReleaseDrilldownListResponse,
  FailedCustomerReleaseDrilldownListResponse,
  MetricsCurrentResponse,
  MetricsHistoryResponse,
  ReleaseMergeRequestListResponse,
  ReleaseProductionBugListResponse,
  RepositoriesResponse,
  ReleaseTimelineResponse,
  SyncStatusResponse,
  PeriodType,
} from "@/types/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 0 }, // always client-side; no Next.js SSR caching
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

const backendPeriodType: Record<PeriodType, "WEEK" | "MONTH" | "QUARTER"> = {
  "30d": "WEEK",
  quarterly: "MONTH",
  yearly: "QUARTER",
};

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

function normalizeMetricsCurrent(raw: any, period: PeriodType): MetricsCurrentResponse {
  if (raw && "lead_time_for_changes" in raw) {
    return raw as MetricsCurrentResponse;
  }
  return {
    generated_at: raw?.generated_at ?? null,
    period_label: raw?.period_end ?? "",
    deployment_frequency: mapMetric(raw?.deployment_frequency, "deploy", period),
    lead_time_for_changes: mapMetric(raw?.lead_time ?? raw?.mean_lead_time, "lead"),
    change_failure_rate: mapMetric(raw?.change_failure_rate, "cfr"),
    mttr_alpha: mapMetric(raw?.mttr_alpha ?? raw?.mttr, "mttr"),
    lead_time_diagnostics: raw?.lead_time_diagnostics ?? null,
  };
}

function _historyDateKey(iso: string): number {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : 0;
}

/** Backend returns periods newest-first; charts read best oldest → newest on the X axis. */
function _sortHistoryPointsChronologically<T extends { date: string }>(points: T[]): T[] {
  return [...points].sort((a, b) => _historyDateKey(a.date) - _historyDateKey(b.date));
}

function normalizeMetricsHistory(raw: any, period: PeriodType): MetricsHistoryResponse {
  if (raw && "data_points" in raw) {
    const typed = raw as MetricsHistoryResponse;
    return { ...typed, data_points: _sortHistoryPointsChronologically(typed.data_points) };
  }
  const points = Array.isArray(raw?.data)
    ? raw.data.map((item: any) => ({
        date: item?.period_end ?? item?.period_start ?? "",
        deployment_frequency:
          typeof item?.deployment_frequency === "number"
            ? item.deployment_frequency
            : null,
        lead_time_for_changes:
          typeof item?.lead_time_minutes === "number"
            ? item.lead_time_minutes / 60.0
            : null,
        lead_time_sample_count:
          typeof item?.lead_time_sample_count === "number"
            ? item.lead_time_sample_count
            : null,
        change_failure_rate:
          typeof item?.change_failure_rate === "number"
            ? item.change_failure_rate * 100.0
            : null,
        mttr_alpha:
          typeof item?.mttr_alpha_minutes === "number"
            ? item.mttr_alpha_minutes
            : null,
      }))
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
  getMetricsCurrent: (period: PeriodType) =>
    request<any>(
      `/metrics/current?period_type=${backendPeriodType[period]}`
    ).then((raw) => normalizeMetricsCurrent(raw, period)),

  getMetricsHistory: (period: PeriodType) =>
    request<any>(
      `/metrics/history?period_type=${backendPeriodType[period]}`
    ).then((raw) => normalizeMetricsHistory(raw, period)),

  getSyncStatus: () => request<any>("/sync/status").then(normalizeSyncStatus),

  getRepositories: () => request<RepositoriesResponse>("/repositories"),

  getReleaseTimeline: () =>
    request<ReleaseTimelineResponse>("/metrics/releases/timeline?min_major=8&limit=3000"),

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
};
