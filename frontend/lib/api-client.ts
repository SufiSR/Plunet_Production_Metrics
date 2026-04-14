import type {
  MetricsCurrentResponse,
  MetricsHistoryResponse,
  RepositoriesResponse,
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
  };
}

function normalizeMetricsHistory(raw: any, period: PeriodType): MetricsHistoryResponse {
  if (raw && "data_points" in raw) {
    return raw as MetricsHistoryResponse;
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
    data_points: points,
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
};
