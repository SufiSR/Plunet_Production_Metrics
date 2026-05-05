import type {
  AdminConfigPatch,
  AdminConfigResponse,
  AdminRawTableName,
  AdminRawTableResponse,
  AdminRawTableSortDirection,
  DataHealthResponse,
  WorklogAuthorListResponse,
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

  getWorklogAuthors: (params?: { page?: number; size?: number }) => {
    const query = new URLSearchParams();
    query.set("page", String(params?.page ?? 0));
    query.set("size", String(params?.size ?? 500));
    return adminRequest<WorklogAuthorListResponse>(
      `/admin/jira/worklog-authors?${query.toString()}`,
    );
  },
};
