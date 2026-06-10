export interface PeopleDataLoginRequest {
  username: string;
  password: string;
}

export interface PeopleDataSessionResponse {
  authenticated: boolean;
  username: string | null;
}

export interface PeopleDataChangePasswordRequest {
  current_password: string;
  new_password: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
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
      detail = body?.message ?? body?.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const peopleDataApiClient = {
  login: (body: PeopleDataLoginRequest) =>
    request<PeopleDataSessionResponse>("/auth/people-data/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  logout: () =>
    request<void>("/auth/people-data/logout", {
      method: "POST",
    }),

  me: () => request<PeopleDataSessionResponse>("/auth/people-data/me"),

  changePassword: (body: PeopleDataChangePasswordRequest) =>
    request<PeopleDataSessionResponse>("/auth/people-data/change-password", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
