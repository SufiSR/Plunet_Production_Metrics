import type {
  AdminConfigPatch,
  AdminConfigResponse,
  LoginRequest,
  LoginResponse,
  MeResponse,
} from "@/types/admin";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

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
};
