import type {
  AdminConfigPatch,
  AdminConfigResponse,
  AdminRawTableName,
  AdminRawTableResponse,
  AdminRawTableSortDirection,
  AllocationRoleRulesResponse,
  DataHealthResponse,
  FeatureFamilyCreate,
  FeatureFamilyDetailResponse,
  FeatureFamilyFeatureListResponse,
  FeatureFamilyListResponse,
  FeatureFamilyMembersPut,
  FeatureFamilyPatch,
  FeatureFamilySuggestionsResponse,
  JiraUserAdminItem,
  JiraUserAdminListResponse,
  JiraUserPatch,
  JiraUserRoleAssignmentPut,
  LoginRequest,
  LoginResponse,
  MeResponse,
  WebhookTestRequest,
  WebhookTestResponse,
} from "@/types/admin";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function adminRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(options?.body ? { "Content-Type": "application/json" } : {}),
      ...options?.headers,
    },
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

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const adminApiClient = {
  login: (body: LoginRequest) =>
    adminRequest<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  logout: () =>
    adminRequest<void>("/auth/logout", { method: "POST" }),

  me: () => adminRequest<MeResponse>("/auth/me"),

  getConfig: () => adminRequest<AdminConfigResponse>("/admin/config"),

  patchConfig: (patch: AdminConfigPatch) =>
    adminRequest<AdminConfigResponse>("/admin/config", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  triggerSync: () =>
    adminRequest<{ detail: string }>("/admin/sync/trigger", {
      method: "POST",
    }),

  testWebhook: (body: WebhookTestRequest) =>
    adminRequest<WebhookTestResponse>("/admin/config/webhook/test", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getDataHealth: (params?: {
    unmatched_page?: number;
    unmatched_size?: number;
    mismatch_page?: number;
    mismatch_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.unmatched_page !== undefined) {
      query.set("unmatched_page", String(params.unmatched_page));
    }
    if (params?.unmatched_size !== undefined) {
      query.set("unmatched_size", String(params.unmatched_size));
    }
    if (params?.mismatch_page !== undefined) {
      query.set("mismatch_page", String(params.mismatch_page));
    }
    if (params?.mismatch_size !== undefined) {
      query.set("mismatch_size", String(params.mismatch_size));
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return adminRequest<DataHealthResponse>(`/admin/data-health${suffix}`);
  },

  getRawTableRows: (params: {
    table: AdminRawTableName;
    page?: number;
    size?: number;
    search?: string;
    sort_by?: string;
    sort_dir?: AdminRawTableSortDirection;
  }) => {
    const query = new URLSearchParams();
    if (params.page !== undefined) query.set("page", String(params.page));
    if (params.size !== undefined) query.set("size", String(params.size));
    if (params.search) query.set("search", params.search);
    if (params.sort_by) query.set("sort_by", params.sort_by);
    if (params.sort_dir) query.set("sort_dir", params.sort_dir);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return adminRequest<AdminRawTableResponse>(`/admin/raw-tables/${params.table}${suffix}`);
  },

  getJiraUsers: (params?: { page?: number; size?: number; search?: string }) => {
    const query = new URLSearchParams();
    query.set("page", String(params?.page ?? 0));
    query.set("size", String(params?.size ?? 500));
    if (params?.search) query.set("search", params.search);
    return adminRequest<JiraUserAdminListResponse>(`/admin/jira-users?${query.toString()}`);
  },

  getAllocationRoleRules: () =>
    adminRequest<AllocationRoleRulesResponse>("/admin/jira-users/allocation-role-rules"),

  patchJiraUser: (userId: number, body: JiraUserPatch) =>
    adminRequest<JiraUserAdminItem>(`/admin/jira-users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  putJiraUserRoleAssignment: (userId: number, body: JiraUserRoleAssignmentPut) =>
    adminRequest<JiraUserAdminItem>(`/admin/jira-users/${userId}/role-assignment`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getFeatureFamilies: () =>
    adminRequest<FeatureFamilyListResponse>("/admin/jira-feature-families"),

  createFeatureFamily: (body: FeatureFamilyCreate) =>
    adminRequest<FeatureFamilyDetailResponse>("/admin/jira-feature-families", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  patchFeatureFamily: (familyId: number, body: FeatureFamilyPatch) =>
    adminRequest<FeatureFamilyDetailResponse>(`/admin/jira-feature-families/${familyId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  getFeatureFamily: (familyId: number) =>
    adminRequest<FeatureFamilyDetailResponse>(`/admin/jira-feature-families/${familyId}`),

  putFeatureFamilyMembers: (familyId: number, body: FeatureFamilyMembersPut) =>
    adminRequest<FeatureFamilyDetailResponse>(`/admin/jira-feature-families/${familyId}/members`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getFeatureFamilyFeatures: (params?: { search?: string; unassigned_only?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.unassigned_only !== undefined) {
      query.set("unassigned_only", String(params.unassigned_only));
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return adminRequest<FeatureFamilyFeatureListResponse>(`/admin/jira-feature-families/features${suffix}`);
  },

  getFeatureFamilySuggestions: () =>
    adminRequest<FeatureFamilySuggestionsResponse>("/admin/jira-feature-families/suggestions"),

  acceptFeatureFamilySuggestion: (suggestionId: string, reason?: string | null) =>
    adminRequest<FeatureFamilyDetailResponse>(
      `/admin/jira-feature-families/suggestions/${encodeURIComponent(suggestionId)}/accept`,
      {
        method: "POST",
        body: JSON.stringify({ reason: reason ?? null }),
      },
    ),

  rejectFeatureFamilySuggestion: (suggestionId: string, reason?: string | null) =>
    adminRequest<FeatureFamilySuggestionsResponse>(
      `/admin/jira-feature-families/suggestions/${encodeURIComponent(suggestionId)}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason: reason ?? null }),
      },
    ),

  triggerJiraAnalyticsSync: (updatedAfterDays?: number) => {
    const query =
      updatedAfterDays !== undefined
        ? `?updated_after_days=${encodeURIComponent(String(updatedAfterDays))}`
        : "";
    return adminRequest<{ detail: string; updated_after_days: number | null }>(
      `/admin/jira-analytics/sync/trigger${query}`,
      { method: "POST" },
    );
  },

  getLatestJiraAnalyticsSync: () =>
    adminRequest<AdminPipelineSyncLatestResponse>("/admin/jira-analytics/sync/latest"),

  triggerHrworksSync: (incremental = false) =>
    adminRequest<{ detail: string }>(
      `/admin/hrworks/sync/trigger?incremental=${incremental ? "true" : "false"}`,
      { method: "POST" },
    ),

  getLatestHrworksSync: () =>
    adminRequest<AdminPipelineSyncLatestResponse>("/admin/hrworks/sync/latest"),

  rebuildJiraAnalyticsAllocation: (periodMonth?: string) => {
    const query = periodMonth ? `?period_month=${encodeURIComponent(periodMonth)}` : "";
    return adminRequest<JiraAnalyticsAllocationRebuildResponse>(
      `/admin/jira-analytics/rebuild-allocation${query}`,
      { method: "POST" },
    );
  },

  getJiraAnalyticsAllocationRebuildStatus: () =>
    adminRequest<JiraAnalyticsAllocationRebuildResponse>(
      "/admin/jira-analytics/rebuild-allocation/status",
    ),
};

export interface AdminSyncLogEntry {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  records_processed: number | null;
  error_message: string | null;
  details_json: Record<string, unknown> | null;
}

export interface AdminPipelineSyncLatestResponse {
  status: string | null;
  sync_log: AdminSyncLogEntry | null;
}

export interface JiraAnalyticsAllocationRebuildResponse {
  state: "idle" | "running" | "succeeded" | "failed";
  started_at?: string | null;
  finished_at?: string | null;
  periods?: string[];
  topic_rows?: number;
  allocation_rows?: number;
  error?: string | null;
  message?: string;
}
