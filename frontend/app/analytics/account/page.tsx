"use client";

import Link from "next/link";
import { useState } from "react";
import { JiraAnalyticsShell } from "@/app/components/jira-analytics/JiraAnalyticsShell";
import { usePeopleDataSession } from "@/lib/hooks/use-people-data-session";
import { peopleDataApiClient } from "@/lib/people-data-api-client";

export default function Page() {
  const { ready, authenticated, username } = usePeopleDataSession();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      await peopleDataApiClient.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setSuccess("Password changed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password");
    } finally {
      setSaving(false);
    }
  }

  return (
    <JiraAnalyticsShell title="People-data account" hidePageHeader hideMethodology>
      <main className="mx-auto w-full max-w-xl px-6 py-10">
        <div className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6">
          <h1 className="font-editorial text-2xl font-bold text-on-surface">
            People-data account
          </h1>
          {!ready ? (
            <p className="mt-4 text-sm text-on-surface-variant">Loading account...</p>
          ) : !authenticated ? (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-on-surface-variant">
                Sign in to change your people-data password.
              </p>
              <Link
                href="/analytics/login?next=/analytics/account"
                className="inline-flex rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
              >
                Sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 space-y-5">
              <p className="text-sm text-on-surface-variant">
                Signed in as <span className="font-medium text-on-surface">{username}</span>.
              </p>
              <div className="space-y-2">
                <label htmlFor="current-password" className="block text-sm font-medium text-on-surface">
                  Current password
                </label>
                <input
                  id="current-password"
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface outline-none focus:border-primary"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="new-password" className="block text-sm font-medium text-on-surface">
                  New password
                </label>
                <input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface outline-none focus:border-primary"
                />
              </div>
              {error ? <p className="text-sm text-error">{error}</p> : null}
              {success ? <p className="text-sm text-primary">{success}</p> : null}
              <button
                type="submit"
                disabled={saving}
                className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-60"
              >
                {saving ? "Saving..." : "Change password"}
              </button>
            </form>
          )}
        </div>
      </main>
    </JiraAnalyticsShell>
  );
}
