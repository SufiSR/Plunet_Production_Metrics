"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";

function AdminLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
  const defaultNext = `${basePath}/admin_legacy/config`;
  const requestedNext = searchParams.get("next");
  const normalizedRequestedNext = requestedNext?.trim() ?? "";
  const next = (() => {
    if (!normalizedRequestedNext.startsWith("/")) {
      return defaultNext;
    }
    // Keep navigation inside the app when deployed under a base path.
    if (basePath && normalizedRequestedNext.startsWith(`${basePath}/`)) {
      return normalizedRequestedNext;
    }
    if (
      basePath &&
      (normalizedRequestedNext.startsWith("/admin") || normalizedRequestedNext.startsWith("/admin_legacy"))
    ) {
      return `${basePath}${normalizedRequestedNext}`;
    }
    return normalizedRequestedNext;
  })();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      await adminApiClient.login({ username, password });
      setSuccess("Signed in. Redirecting…");
      // Hard navigation ensures the next page request carries the new session
      // cookie from the start, avoiding Next.js App Router soft-nav cache issues.
      window.location.href = next;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {/* Brand header */}
        <div className="mb-10">
          <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary mb-2">
            Admin Access
          </p>
          <h1 className="text-4xl font-editorial font-bold tracking-tight text-on-surface">
            Sign In
          </h1>
          <p className="text-sm text-on-surface-variant mt-2 leading-relaxed">
            Access the DORA Metrics configuration console.
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface-container-lowest p-8 rounded-2xl shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Username */}
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-body text-on-surface placeholder:text-outline"
                placeholder="admin"
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <label
                htmlFor="password"
                className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-outline px-1 block"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 bg-surface-container-low border-b-2 border-transparent focus:bg-surface-container-lowest focus:border-primary focus:outline-none transition-all font-body text-on-surface placeholder:text-outline"
                placeholder="••••••••"
              />
            </div>

            {/* Error */}
            {error && (
              <div
                role="alert"
                className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-error-container text-on-error-container text-xs font-editorial"
              >
                <span className="material-symbols-outlined text-base shrink-0">
                  error
                </span>
                {error}
              </div>
            )}

            {success && (
              <div
                role="status"
                className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-primary-container/30 text-on-surface text-xs font-editorial"
              >
                <span className="material-symbols-outlined text-base shrink-0 text-primary">
                  check_circle
                </span>
                {success}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-editorial font-bold text-sm rounded-xl shadow-lg shadow-primary/20 hover:scale-[1.01] active:scale-100 transition-all disabled:opacity-60 disabled:pointer-events-none"
            >
              {success ? "Redirecting…" : loading ? "Signing in…" : "Sign In"}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-outline mt-6 font-editorial uppercase tracking-widest">
          DORA Metrics — Admin Console
        </p>
      </div>
    </div>
  );
}

export default function AdminLoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background flex items-center justify-center p-6">
          <p className="text-sm text-on-surface-variant font-editorial">Loading…</p>
        </div>
      }
    >
      <AdminLoginForm />
    </Suspense>
  );
}
