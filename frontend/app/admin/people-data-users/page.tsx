"use client";

import { useEffect, useState } from "react";
import { AdminNewPageHeader } from "@/app/components/admin-new/AdminNewPageHeader";
import { adminApiClient } from "@/lib/admin-api-client";
import { useAdminSession } from "@/lib/hooks/use-admin-session";
import type { PeopleDataUserItem } from "@/types/admin";

export default function Page() {
  const { ready } = useAdminSession("/admin/people-data-users");
  const [users, setUsers] = useState<PeopleDataUserItem[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [resetPasswords, setResetPasswords] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const response = await adminApiClient.getPeopleDataUsers();
      setUsers(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ready) void loadUsers();
  }, [ready]);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (password.length < 12) {
      setError("Password must be at least 12 characters long.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await adminApiClient.createPeopleDataUser({ username, password });
      setUsername("");
      setPassword("");
      setSuccess("User created.");
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create user");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(user: PeopleDataUserItem) {
    await mutateUser(() =>
      adminApiClient.patchPeopleDataUser(user.id, { is_active: !user.is_active }),
    );
  }

  async function handleResetPassword(user: PeopleDataUserItem) {
    const nextPassword = resetPasswords[user.id]?.trim();
    if (!nextPassword) {
      setError("Enter a new password before resetting.");
      return;
    }
    if (nextPassword.length < 12) {
      setError("Password must be at least 12 characters long.");
      return;
    }
    await mutateUser(() => adminApiClient.patchPeopleDataUser(user.id, { password: nextPassword }));
    setResetPasswords((current) => {
      const next = { ...current };
      delete next[user.id];
      return next;
    });
  }

  async function handleDelete(user: PeopleDataUserItem) {
    if (!window.confirm(`Delete people-data user "${user.username}"?`)) return;
    await mutateUser(() => adminApiClient.deletePeopleDataUser(user.id));
  }

  async function mutateUser(action: () => Promise<unknown>) {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess("User updated.");
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update user");
    } finally {
      setSaving(false);
    }
  }

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-background px-6 py-8 text-on-background">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <AdminNewPageHeader
          eyebrow="Access control"
          title="People-data users"
          description="Manage accounts that can unlock individual-level analytics drilldowns."
        />

        <section className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6">
          <h2 className="font-editorial text-xl font-semibold text-on-surface">Create user</h2>
          <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username"
              className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface outline-none focus:border-primary"
            />
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Initial password (min. 12 chars)"
              minLength={12}
              className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-sm text-on-surface outline-none focus:border-primary"
            />
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-60"
            >
              Create
            </button>
          </form>
          {error ? <p className="mt-3 text-sm text-error">{error}</p> : null}
          {success ? <p className="mt-3 text-sm text-primary">{success}</p> : null}
        </section>

        <section className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6">
          <h2 className="font-editorial text-xl font-semibold text-on-surface">Users</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-outline-variant/20 text-left text-on-surface-variant">
                  <th className="px-3 py-2">Username</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2">Reset password</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="px-3 py-4 text-on-surface-variant" colSpan={5}>
                      Loading users...
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td className="px-3 py-4 text-on-surface-variant" colSpan={5}>
                      No people-data users yet.
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="border-b border-outline-variant/10">
                      <td className="px-3 py-2 font-medium text-on-surface">{user.username}</td>
                      <td className="px-3 py-2 text-on-surface">
                        {user.is_active ? "Active" : "Inactive"}
                      </td>
                      <td className="px-3 py-2 text-on-surface-variant">
                        {new Date(user.created_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex gap-2">
                          <input
                            type="password"
                            value={resetPasswords[user.id] ?? ""}
                            onChange={(event) =>
                              setResetPasswords((current) => ({
                                ...current,
                                [user.id]: event.target.value,
                              }))
                            }
                            placeholder="New password (min. 12 chars)"
                            minLength={12}
                            className="min-w-48 rounded-lg border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm text-on-surface outline-none focus:border-primary"
                          />
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => handleResetPassword(user)}
                            className="rounded-lg border border-outline-variant/40 px-3 py-2 text-xs font-semibold text-primary disabled:opacity-60"
                          >
                            Reset
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => handleToggle(user)}
                            className="rounded-lg border border-outline-variant/40 px-3 py-2 text-xs font-semibold text-primary disabled:opacity-60"
                          >
                            {user.is_active ? "Deactivate" : "Activate"}
                          </button>
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => handleDelete(user)}
                            className="rounded-lg border border-error/40 px-3 py-2 text-xs font-semibold text-error disabled:opacity-60"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
