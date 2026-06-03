"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import { useAdminRawTableRows } from "@/lib/hooks";
import type { AdminRawTableName, AdminRawTableSortDirection } from "@/types/admin";

const PAGE_SIZE = 20;

const TABLE_OPTIONS: { value: AdminRawTableName; label: string }[] = [
  { value: "sync_log", label: "Sync Log" },
  { value: "repository", label: "Repository" },
  { value: "release", label: "Release" },
  { value: "production_bug", label: "Production Bug" },
  { value: "merge_request", label: "Merge Request" },
  { value: "issue_worklog", label: "Issue Worklog" },
];

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.join(", ");
  return JSON.stringify(value);
}

export default function AdminRawTablesPage() {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  const [table, setTable] = useState<AdminRawTableName>("sync_log");
  const [page, setPage] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<AdminRawTableSortDirection>("desc");

  useEffect(() => {
    (async () => {
      try {
        const me = await adminApiClient.me();
        if (me.role !== "admin") {
          router.push("/admin/login");
          return;
        }
        setAllowed(true);
      } catch {
        router.push("/admin/login");
      }
    })();
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(0);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const query = useAdminRawTableRows(table, page, PAGE_SIZE, search, sortBy, sortDir);
  const rows = query.data?.rows ?? [];
  const columns = query.data?.columns ?? [];
  const pagination = query.data?.pagination;

  const tableTitle = useMemo(
    () => TABLE_OPTIONS.find((opt) => opt.value === table)?.label ?? table,
    [table],
  );

  function handleSort(columnKey: string) {
    if (sortBy !== columnKey) {
      setSortBy(columnKey);
      setSortDir("asc");
      setPage(0);
      return;
    }
    setSortDir((current) => (current === "asc" ? "desc" : "asc"));
    setPage(0);
  }

  if (!allowed) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="h-16 w-16 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  if (query.isLoading) {
    return (
      <div className="w-full space-y-8">
        <div className="h-16 bg-surface-container rounded-2xl animate-pulse" />
        <div className="h-72 bg-surface-container rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (query.error || !query.data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-3">
          <span className="material-symbols-outlined text-error text-5xl">error</span>
          <p className="text-on-surface-variant font-editorial">
            {query.error instanceof Error ? query.error.message : "Failed to load raw table rows."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full pb-24 space-y-6">
      <header className="space-y-3">
        <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary">
          Operations
        </p>
        <h1 className="text-5xl font-editorial font-bold tracking-tight text-on-surface">Raw Data</h1>
        <p className="text-on-surface-variant text-sm max-w-4xl">
          Review selected database tables with search and sortable columns. Technical internals are hidden
          in favor of user-relevant fields.
        </p>
      </header>

      <section className="rounded-2xl bg-surface-container-lowest p-5 border border-outline-variant flex flex-col gap-4 md:flex-row md:items-end">
        <div className="flex-1">
          <label className="block text-xs uppercase tracking-widest text-on-surface-variant mb-2">
            Table
          </label>
          <select
            value={table}
            onChange={(event) => {
              setTable(event.target.value as AdminRawTableName);
              setPage(0);
              setSortBy(null);
              setSortDir("desc");
            }}
            className="w-full px-3 py-2 rounded-xl bg-surface-container border border-outline-variant"
          >
            {TABLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-[2]">
          <label className="block text-xs uppercase tracking-widest text-on-surface-variant mb-2">
            Search
          </label>
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder={`Search in ${tableTitle}`}
            className="w-full px-3 py-2 rounded-xl bg-surface-container border border-outline-variant"
          />
        </div>
      </section>

      <section className="rounded-2xl bg-surface-container-lowest p-6 border border-outline-variant space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-editorial font-semibold">{tableTitle}</h2>
          <div className="flex items-center gap-2 text-xs">
            <button
              className="px-3 py-1 rounded border border-outline-variant disabled:opacity-50"
              disabled={!pagination?.has_previous}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
            >
              Prev
            </button>
            <span>
              Page {(pagination?.page ?? 0) + 1} / {Math.max(1, pagination?.total_pages ?? 0)}
            </span>
            <button
              className="px-3 py-1 rounded border border-outline-variant disabled:opacity-50"
              disabled={!pagination?.has_next}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-on-surface-variant border-b border-outline-variant">
                {columns.map((column) => (
                  <th key={column.key} className="py-2 pr-3">
                    {column.sortable ? (
                      <button
                        className="inline-flex items-center gap-1 hover:text-on-surface"
                        onClick={() => handleSort(column.key)}
                      >
                        {column.label}
                        {sortBy === column.key ? (sortDir === "asc" ? "↑" : "↓") : ""}
                      </button>
                    ) : (
                      column.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td className="py-3 text-on-surface-variant" colSpan={Math.max(1, columns.length)}>
                    No rows found.
                  </td>
                </tr>
              ) : (
                rows.map((row, index) => (
                  <tr key={`${table}-${index}`} className="border-b border-outline-variant/50">
                    {columns.map((column) => (
                      <td key={column.key} className="py-2 pr-3 align-top">
                        {formatCellValue(row[column.key])}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
