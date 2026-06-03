"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import type {
  AllocationRoleRuleItem,
  JiraUserAdminItem,
} from "@/types/admin";

type UserDraft = {
  reporting_excluded: boolean;
  role_name: string;
  team_name: string;
  allocatable_percentage: string;
  allocation_scope: string;
};

type SortKey = "account" | "display" | "reporting" | "role" | "team" | "alloc" | "scope";

function isIndirectRole(roleName: string, rules: AllocationRoleRuleItem[]): boolean {
  const rule = rules.find((r) => r.role_name === roleName);
  return Boolean(rule?.is_indirect_role);
}

function sortValue(user: JiraUserAdminItem, draft: UserDraft, key: SortKey): string | number {
  switch (key) {
    case "account":
      return user.account_id.toLowerCase();
    case "display":
      return (user.display_name ?? "").toLowerCase();
    case "reporting":
      return draft.reporting_excluded ? 1 : 0;
    case "role":
      return draft.role_name.toLowerCase();
    case "team":
      return draft.team_name.toLowerCase();
    case "alloc":
      return draft.allocatable_percentage ? Number(draft.allocatable_percentage) : -1;
    case "scope":
      return draft.allocation_scope.toLowerCase();
  }
}

export default function UserAssignmentsPage() {
  const router = useRouter();
  const [loaded, setLoaded] = useState(false);
  const [users, setUsers] = useState<JiraUserAdminItem[]>([]);
  const [roleRules, setRoleRules] = useState<AllocationRoleRuleItem[]>([]);
  const [draftByUserId, setDraftByUserId] = useState<Record<number, UserDraft>>({});
  const [showExcluded, setShowExcluded] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("display");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const initDraft = useCallback((items: JiraUserAdminItem[]) => {
    const m: Record<number, UserDraft> = {};
    for (const u of items) {
      const a = u.role_assignment;
      m[u.id] = {
        reporting_excluded: u.reporting_excluded,
        role_name: a?.role_name ?? "",
        team_name: a?.team_name ?? "",
        allocatable_percentage:
          a?.allocatable_percentage != null ? String(a.allocatable_percentage) : "",
        allocation_scope: a?.allocation_scope ?? "",
      };
    }
    setDraftByUserId(m);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const me = await adminApiClient.me();
        if (me.role !== "admin") {
          router.push("/admin/login");
          return;
        }
        const [userPage, rulesResp] = await Promise.all([
          adminApiClient.getJiraUsers({ page: 0, size: 500 }),
          adminApiClient.getAllocationRoleRules(),
        ]);
        setUsers(userPage.items);
        setRoleRules(rulesResp.items);
        initDraft(userPage.items);
        setLoaded(true);
        setLoadError(null);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : "Failed to load");
        router.push("/admin/login");
      }
    })();
  }, [router, initDraft]);

  const updateDraft = useCallback((userId: number, next: UserDraft) => {
    setDraftByUserId((prev) => ({ ...prev, [userId]: next }));
    setSaveState("idle");
  }, []);

  const requestSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
        return prev;
      }
      setSortDir("asc");
      return key;
    });
  }, []);

  const roleOptions = useMemo(
    () => roleRules.map((r) => r.role_name).sort((a, b) => a.localeCompare(b)),
    [roleRules],
  );

  const visibleUsers = useMemo(() => {
    const filtered = showExcluded
      ? users
      : users.filter((user) => !(draftByUserId[user.id]?.reporting_excluded ?? user.reporting_excluded));
    return [...filtered].sort((a, b) => {
      const ad = draftByUserId[a.id] ?? {
        reporting_excluded: a.reporting_excluded,
        role_name: "",
        team_name: "",
        allocatable_percentage: "",
        allocation_scope: "",
      };
      const bd = draftByUserId[b.id] ?? {
        reporting_excluded: b.reporting_excluded,
        role_name: "",
        team_name: "",
        allocatable_percentage: "",
        allocation_scope: "",
      };
      const av = sortValue(a, ad, sortKey);
      const bv = sortValue(b, bd, sortKey);
      const cmp = typeof av === "number" && typeof bv === "number"
        ? av - bv
        : String(av).localeCompare(String(bv));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [draftByUserId, showExcluded, sortDir, sortKey, users]);

  const sortMark = useCallback(
    (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : ""),
    [sortDir, sortKey],
  );

  const handleSave = useCallback(async () => {
    setSaveState("saving");
    setSaveError(null);
    try {
      for (const user of users) {
        const draft = draftByUserId[user.id];
        if (!draft) continue;
        if (draft.reporting_excluded !== user.reporting_excluded) {
          await adminApiClient.patchJiraUser(user.id, {
            reporting_excluded: draft.reporting_excluded,
          });
        }
        if (!draft.role_name.trim()) continue;
        const indirect = isIndirectRole(draft.role_name, roleRules);
        const allocPct = draft.allocatable_percentage.trim();
        await adminApiClient.putJiraUserRoleAssignment(user.id, {
          role_name: draft.role_name.trim(),
          team_name: draft.team_name,
          allocatable_percentage: indirect && allocPct ? Number(allocPct) : null,
          allocation_scope: indirect ? draft.allocation_scope.trim() || null : null,
        });
      }

      const userPage = await adminApiClient.getJiraUsers({ page: 0, size: 500 });
      setUsers(userPage.items);
      initDraft(userPage.items);
      setSaveState("success");
      setTimeout(() => setSaveState("idle"), 2500);
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof Error ? err.message : "Save failed");
    }
  }, [users, draftByUserId, roleRules, initDraft]);

  if (!loaded) {
    return (
      <main className="pl-72 pr-10 py-10 text-on-surface-variant text-sm font-editorial">
        {loadError ?? "Loading…"}
      </main>
    );
  }

  return (
    <div className="w-full pb-24 space-y-10">
      <header className="space-y-3">
        <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary">
          Operations
        </p>
        <h1 className="text-5xl font-editorial font-bold tracking-tight text-on-surface">
          User assignments
        </h1>
        <p className="text-on-surface-variant text-sm max-w-3xl">
          Manage reporting roles and teams from synced Jira users. Users marked as excluded from
          reporting are omitted from allocation and analytics. Indirect roles support optional
          allocatable percentage and scope overrides.
        </p>
      </header>

      <section className="rounded-2xl bg-surface-container-lowest p-6 border border-outline-variant space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h2 className="text-xl font-editorial font-semibold text-on-surface">
              Jira users ({visibleUsers.length})
            </h2>
            <label className="inline-flex items-center gap-2 text-xs text-on-surface-variant">
              <input
                type="checkbox"
                checked={showExcluded}
                onChange={(e) => setShowExcluded(e.target.checked)}
              />
              Show excluded users
            </label>
          </div>
          <button
            type="button"
            onClick={() => handleSave()}
            disabled={saveState === "saving"}
            className="px-6 py-2 rounded-xl bg-primary text-on-primary text-sm font-editorial font-bold uppercase tracking-wider disabled:opacity-50"
          >
            {saveState === "saving" ? "Saving…" : "Save"}
          </button>
        </div>
        {saveState === "success" && (
          <p className="text-xs text-secondary">Saved.</p>
        )}
        {saveError && <p className="text-xs text-error">{saveError}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left border-collapse min-w-[960px]">
            <thead>
              <tr className="border-b border-outline-variant text-on-surface-variant">
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("account")}>Account{sortMark("account")}</button>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("display")}>Name{sortMark("display")}</button>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("reporting")}>Reporting{sortMark("reporting")}</button>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("role")}>Role{sortMark("role")}</button>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("team")}>Team{sortMark("team")}</button>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("alloc")}>Alloc %{sortMark("alloc")}</button>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <button type="button" onClick={() => requestSort("scope")}>Scope{sortMark("scope")}</button>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleUsers.map((user) => {
                const draft =
                  draftByUserId[user.id] ??
                  ({
                    reporting_excluded: user.reporting_excluded,
                    role_name: "",
                    team_name: "",
                    allocatable_percentage: "",
                    allocation_scope: "",
                  } satisfies UserDraft);
                const indirect = isIndirectRole(draft.role_name, roleRules);
                return (
                  <tr key={user.id} className="border-b border-outline-variant/30">
                    <td className="py-2 pr-3 font-mono text-[11px] break-all">{user.account_id}</td>
                    <td className="py-2 pr-3">{user.display_name ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <label className="inline-flex items-center gap-2 text-xs">
                        <input
                          type="checkbox"
                          checked={!draft.reporting_excluded}
                          onChange={(e) =>
                            updateDraft(user.id, {
                              ...draft,
                              reporting_excluded: !e.target.checked,
                            })
                          }
                        />
                        {draft.reporting_excluded ? "Excluded" : "Active"}
                      </label>
                    </td>
                    <td className="py-2 pr-3">
                      <select
                        className="rounded border border-outline-variant bg-surface-container px-2 py-1 text-on-surface"
                        value={draft.role_name}
                        onChange={(e) =>
                          updateDraft(user.id, { ...draft, role_name: e.target.value })
                        }
                      >
                        <option value="">Unset</option>
                        {roleOptions.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="text"
                        className="w-full min-w-[100px] rounded border border-outline-variant bg-surface-container px-2 py-1 text-on-surface"
                        value={draft.team_name}
                        onChange={(e) =>
                          updateDraft(user.id, { ...draft, team_name: e.target.value })
                        }
                        placeholder="Team"
                      />
                    </td>
                    <td className="py-2 pr-3">
                      {indirect ? (
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step={1}
                          className="w-20 rounded border border-outline-variant bg-surface-container px-2 py-1 text-on-surface"
                          value={draft.allocatable_percentage}
                          onChange={(e) =>
                            updateDraft(user.id, {
                              ...draft,
                              allocatable_percentage: e.target.value,
                            })
                          }
                          placeholder="Default"
                        />
                      ) : (
                        <span className="text-on-surface-variant text-xs">worklog hrs</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      {indirect ? (
                        <select
                          className="rounded border border-outline-variant bg-surface-container px-2 py-1 text-on-surface"
                          value={draft.allocation_scope}
                          onChange={(e) =>
                            updateDraft(user.id, { ...draft, allocation_scope: e.target.value })
                          }
                        >
                          <option value="">Default</option>
                          <option value="team_only">team_only</option>
                          <option value="global">global</option>
                        </select>
                      ) : (
                        <span className="text-on-surface-variant">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
