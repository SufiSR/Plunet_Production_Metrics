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

const periodQueryParam: Record<PeriodType, string> = {
  "30d": "30d",
  quarterly: "quarterly",
  yearly: "yearly",
};

export const apiClient = {
  getMetricsCurrent: (period: PeriodType) =>
    request<MetricsCurrentResponse>(
      `/metrics/current?period=${periodQueryParam[period]}`
    ),

  getMetricsHistory: (period: PeriodType) =>
    request<MetricsHistoryResponse>(
      `/metrics/history?period=${periodQueryParam[period]}`
    ),

  getSyncStatus: () => request<SyncStatusResponse>("/sync/status"),

  getRepositories: () => request<RepositoriesResponse>("/repositories"),
};
