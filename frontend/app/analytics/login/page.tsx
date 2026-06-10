"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { LoginCard } from "@/app/components/auth/LoginCard";
import { peopleDataApiClient } from "@/lib/people-data-api-client";

function PeopleDataLoginForm() {
  const searchParams = useSearchParams();
  const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
  const requestedNext = searchParams.get("next")?.trim() ?? "";
  const next = requestedNext.startsWith("/") ? requestedNext : "/analytics";
  const target = basePath && next.startsWith("/") && !next.startsWith(basePath) ? `${basePath}${next}` : next;

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await peopleDataApiClient.login({ username, password });
      window.location.href = target;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  return (
    <LoginCard
      eyebrow="Individual data"
      description="Access person-level analytics drilldowns and utilization details."
      username={username}
      password={password}
      loading={loading}
      error={error}
      onUsernameChange={setUsername}
      onPasswordChange={setPassword}
      onSubmit={handleSubmit}
    />
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <PeopleDataLoginForm />
    </Suspense>
  );
}
