"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { LoginCard } from "@/app/components/auth/LoginCard";
import { adminApiClient } from "@/lib/admin-api-client";

function AdminLoginForm() {
  const searchParams = useSearchParams();
  const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
  const defaultNext = `${basePath}/admin`;
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
    <LoginCard
      eyebrow="Admin access"
      description="Access the DORA Metrics configuration console."
      footer="DORA Metrics - Admin Console"
      username={username}
      password={password}
      loading={loading}
      error={error}
      success={success}
      usernamePlaceholder="admin"
      successLabel="Redirecting..."
      onUsernameChange={setUsername}
      onPasswordChange={setPassword}
      onSubmit={handleSubmit}
    />
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
