import type {
  AnalyticsReportResponse,
  DataQualityResponse,
  DataQualityUserDrilldownResponse,
  FeatureFamilyHoursDrilldownResponse,
  FeatureFamilyHoursMatrixResponse,
  FeatureHoursDrilldownResponse,
  FeatureHoursMatrixResponse,
  ReportQueryParams,
} from "@/types/jira-analytics";
import { parseApiErrorBody } from "@/lib/parse-api-error";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    let message = parseApiErrorBody(null, res.status);
    try {
      message = parseApiErrorBody(await res.json(), res.status);
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

function query(params: Record<string, string | number | string[] | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item) search.append(key, item);
      }
      continue;
    }
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function fetchFeatureHoursMatrix(options?: {
  months?: number;
  role?: string | null;
  team?: string | null;
}): Promise<FeatureHoursMatrixResponse> {
  return request(
    `/jira-analytics/feature-hours/matrix${query({
      months: options?.months ?? 12,
      role: options?.role ?? undefined,
      team: options?.team ?? undefined,
    })}`,
  );
}

export function fetchFeatureHoursDrilldown(
  rowId: string,
  options?: {
    months?: number;
    role?: string | null;
    team?: string | null;
  },
): Promise<FeatureHoursDrilldownResponse> {
  return request(
    `/jira-analytics/feature-hours/${encodeURIComponent(rowId)}/drilldown${query({
      months: options?.months ?? 12,
      role: options?.role ?? undefined,
      team: options?.team ?? undefined,
    })}`,
  );
}

export function fetchFeatureFamilyHoursMatrix(options?: {
  months?: number;
  role?: string | null;
  team?: string | null;
}): Promise<FeatureFamilyHoursMatrixResponse> {
  return request(
    `/jira-analytics/feature-families/matrix${query({
      months: options?.months ?? 12,
      role: options?.role ?? undefined,
      team: options?.team ?? undefined,
    })}`,
  );
}

export function fetchFeatureFamilyHoursDrilldown(
  familyId: number,
  options?: {
    months?: number;
    role?: string | null;
    team?: string | null;
  },
): Promise<FeatureFamilyHoursDrilldownResponse> {
  return request(
    `/jira-analytics/feature-families/${familyId}/drilldown${query({
      months: options?.months ?? 12,
      role: options?.role ?? undefined,
      team: options?.team ?? undefined,
    })}`,
  );
}

export function fetchDataQuality(): Promise<DataQualityResponse> {
  return request("/jira-analytics/data-quality");
}

export function fetchDataQualityUserDrilldown(
  checkId: string,
): Promise<DataQualityUserDrilldownResponse> {
  return request(`/jira-analytics/data-quality/checks/${encodeURIComponent(checkId)}/users`);
}

export function ignoreDataQualityUser(
  checkId: string,
  userId: number,
  reason?: string | null,
): Promise<DataQualityUserDrilldownResponse> {
  return request(
    `/jira-analytics/data-quality/checks/${encodeURIComponent(checkId)}/users/${userId}/ignore`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason ?? null }),
    },
  );
}

export function unignoreDataQualityUser(
  checkId: string,
  userId: number,
): Promise<DataQualityUserDrilldownResponse> {
  return request(
    `/jira-analytics/data-quality/checks/${encodeURIComponent(checkId)}/users/${userId}/ignore`,
    { method: "DELETE" },
  );
}

export function rebuildAllocation(periodMonth?: string | null): Promise<{
  state?: "idle" | "running" | "succeeded" | "failed";
  periods: string[];
  topic_rows: number;
  allocation_rows: number;
  error?: string | null;
}> {
  return request(
    `/jira-analytics/allocation/rebuild${query({ period_month: periodMonth ?? undefined })}`,
    { method: "POST" },
  );
}

export function fetchAllocationRebuildStatus(): Promise<{
  state: "idle" | "running" | "succeeded" | "failed";
  started_at?: string | null;
  finished_at?: string | null;
  periods: string[];
  topic_rows: number;
  allocation_rows: number;
  error?: string | null;
}> {
  return request("/jira-analytics/allocation/rebuild/status");
}

export function fetchAnalyticsReport(
  path: string,
  params?: ReportQueryParams,
  signal?: AbortSignal,
): Promise<AnalyticsReportResponse> {
  return request(
    `/jira-analytics/${path}${query({
      from: params?.from,
      to: params?.to,
      team: params?.team,
      project_key: params?.projectKeys ?? params?.projectKey,
      issueType: params?.issueType,
      workflow: params?.workflow,
      includeOtherWorkflows: params?.includeOtherWorkflows ? "true" : undefined,
      role: params?.role,
      family_id: params?.familyId,
      feature_key: params?.featureKey,
      issue_key: params?.issueKey,
      customer: params?.customer,
      mode: params?.mode,
      min_hours: params?.minHours,
      min_score: params?.minScore,
      min_age_days: params?.minAgeDays,
      limit: params?.limit,
    })}`,
    { signal },
  );
}

export function fetchFeatureInvestmentAudit(params?: ReportQueryParams): Promise<AnalyticsReportResponse> {
  return fetchAnalyticsReport("features/investment-audit", params);
}

export function fetchFeatureInvestmentAuditIssues(params?: ReportQueryParams): Promise<AnalyticsReportResponse> {
  return fetchAnalyticsReport("features/investment-audit/drilldown/issues", params);
}

export function fetchFeatureInvestmentAuditWorklogs(params: ReportQueryParams): Promise<AnalyticsReportResponse> {
  return fetchAnalyticsReport("features/investment-audit/drilldown/worklogs", params);
}

export async function downloadFeatureInvestmentAuditExport(params?: ReportQueryParams): Promise<Blob> {
  const res = await fetch(
    `${BASE_URL}/jira-analytics/features/investment-audit/export.xlsx${query({
      from: params?.from,
      to: params?.to,
      team: params?.team,
      role: params?.role,
      family_id: params?.familyId,
      feature_key: params?.featureKey,
    })}`,
    { headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" } },
  );
  if (!res.ok) {
    let message = parseApiErrorBody(null, res.status);
    try {
      message = parseApiErrorBody(await res.json(), res.status);
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return res.blob();
}

export const reportPaths = {
  investmentCategory: "capacity/investment-category",
  withoutFeature: "issues/without-feature",
  featureCost: "features/cost",
  featureInvestmentAudit: "features/investment-audit",
  investmentRanking: "features/investment-ranking",
  heatmap: "work-allocation/heatmap",
  plannedVsUnplanned: "teams/planned-vs-unplanned",
  availabilityVsBooked: "teams/availability-vs-booked",
  capacityForecast: "teams/capacity-forecast",
  realInterruptionRatio: "teams/real-interruption-ratio",
  lifecycle: "features/lifecycle",
  promisedVsActual: "features/promised-vs-actual",
  ideaAging: "features/idea-aging",
  statusWaiting: "workflow/status-waiting-time",
  activeVsPassive: "workflow/active-vs-passive",
  activeVsPassiveTrend: "workflow/active-vs-passive-trend",
  thrashing: "workflow/thrashing",
  throughput: "teams/throughput-stability",
  busFactor: "risks/single-contributor",
  customerEffort: "customers/effort",
  investmentByTheme: "product/investment-by-theme",
  featureRisk: "features/risk",
  engineeringHealth: "executive/engineering-health",
  roadmapReliability: "product/roadmap-reliability",
  sizeVsSpeed: "features/size-vs-speed",
} as const;
