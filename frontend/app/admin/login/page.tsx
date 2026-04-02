"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";

function AdminLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/admin/config";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await adminApiClient.login({ username, password });
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
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

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-editorial font-bold text-sm rounded-xl shadow-lg shadow-primary/20 hover:scale-[1.01] active:scale-100 transition-all disabled:opacity-60 disabled:pointer-events-none"
            >
              {loading ? "Signing in…" : "Sign In"}
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
