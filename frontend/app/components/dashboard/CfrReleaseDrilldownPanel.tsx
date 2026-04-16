"use client";

import { useEffect, useMemo, useState } from "react";
import { useFailedReleaseDrilldown, useFailedReleaseIssues, useRepositories } from "@/lib/hooks";
import type { FailedCustomerReleaseDrilldownItem } from "@/types/api";

type SelectedRelease = {
  repository_id: number;
  tag_name: string;
  repository_path: string;
};

const RELEASE_PAGE_SIZE = 20;
const ISSUE_PAGE_SIZE = 50;

function laneLabel(lane: string): string {
  const m: Record<string, string> = {
    major: "Major",
    minor: "Minor",
    patch: "Patch",
    unknown: "Unknown",
  };
  return m[lane] ?? lane;
}

function formatShort(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function PaginationBar(props: {
  pagination: {
    page: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
    total_elements: number;
  };
  onPrev: () => void;
  onNext: () => void;
  noun: string;
}) {
  const { pagination, onPrev, onNext, noun } = props;
  const pageDisplay = pagination.total_pages === 0 ? 0 : pagination.page + 1;
  return (
    <div className="flex items-center justify-between gap-3 mt-4 pt-4 border-t border-outline-variant/30">
      <p className="text-[10px] font-editorial text-on-surface-variant uppercase tracking-widest">
        {pagination.total_elements} {noun}
        {pagination.total_pages > 0
          ? ` · Page ${pageDisplay} of ${pagination.total_pages}`
          : ""}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onPrev}
          disabled={!pagination.has_previous}
          className="px-3 py-1.5 text-[10px] font-editorial font-bold uppercase tracking-wider rounded-md bg-surface-container text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container-high transition-colors"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={!pagination.has_next}
          className="px-3 py-1.5 text-[10px] font-editorial font-bold uppercase tracking-wider rounded-md bg-surface-container text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container-high transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function CfrReleaseDrilldownPanel() {
  const [repoFilter, setRepoFilter] = useState<number | "all">("all");
  const [releasePage, setReleasePage] = useState(0);
  const [issuePage, setIssuePage] = useState(0);
  const [selected, setSelected] = useState<SelectedRelease | null>(null);

  const { data: repos } = useRepositories();
  const { data: drilldown, isLoading: loadingReleases, isError: errReleases } = useFailedReleaseDrilldown(
    releasePage,
    repoFilter === "all" ? null : repoFilter,
    RELEASE_PAGE_SIZE,
  );
  const { data: issues, isLoading: loadingIssues, isError: errIssues } = useFailedReleaseIssues(
    selected?.repository_id ?? null,
    selected?.tag_name ?? null,
    issuePage,
    ISSUE_PAGE_SIZE,
  );

  const items = useMemo(() => drilldown?.items ?? [], [drilldown?.items]);
  const relPag = drilldown?.pagination;
  const issuePag = issues?.pagination;

  useEffect(() => {
    if (!items.length) {
      setSelected(null);
      return;
    }
    const stillThere =
      selected &&
      items.some(
        (r) => r.repository_id === selected.repository_id && r.tag_name === selected.tag_name,
      );
    if (!stillThere) {
      const first = items[0];
      setSelected({
        repository_id: first.repository_id,
        tag_name: first.tag_name,
        repository_path: first.repository_path,
      });
      setIssuePage(0);
    }
  }, [items, selected]);

  const onSelectRelease = (r: FailedCustomerReleaseDrilldownItem) => {
    setSelected({
      repository_id: r.repository_id,
      tag_name: r.tag_name,
      repository_path: r.repository_path,
    });
    setIssuePage(0);
  };

  const onRepoFilterChange = (v: string) => {
    setRepoFilter(v === "all" ? "all" : Number(v));
    setReleasePage(0);
    setSelected(null);
    setIssuePage(0);
  };

  return (
    <div className="bg-surface-container-lowest p-8 rounded-xl shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-editorial font-bold tracking-tight text-on-surface">
            Failed customer releases → Jira issues
          </h2>
          <p className="text-xs font-editorial text-on-surface-variant uppercase tracking-widest mt-1">
            Post-production defects only (internal QA pre-production classifications are excluded).
            Linked via affects version → tag.
          </p>
        </div>
        {repos && repos.repositories.length > 0 && (
          <label className="flex flex-col gap-1 min-w-[200px]">
            <span className="text-[10px] font-editorial uppercase tracking-widest text-outline">
              Repository
            </span>
            <select
              value={repoFilter === "all" ? "all" : String(repoFilter)}
              onChange={(e) => onRepoFilterChange(e.target.value)}
              className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm font-editorial text-on-surface"
            >
              <option value="all">All repositories</option>
              {repos.repositories.map((r) => (
                <option key={r.id} value={String(r.id)}>
                  {r.path}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(240px,300px)_1fr] gap-8">
        <div className="flex flex-col min-h-[280px]">
          <h3 className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline mb-3">
            Releases with issues
          </h3>
          {loadingReleases ? (
            <div className="space-y-2 flex-1">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-16 bg-surface-container animate-pulse rounded-lg" />
              ))}
            </div>
          ) : errReleases ? (
            <p className="text-sm text-error font-editorial">Could not load releases.</p>
          ) : !items.length ? (
            <p className="text-sm text-on-surface-variant font-editorial">
              No customer releases with linked healthy Jira issues.
            </p>
          ) : (
            <ul className="space-y-2 flex-1 overflow-y-auto max-h-[480px] pr-1">
              {items.map((r) => {
                const isSel =
                  selected?.repository_id === r.repository_id && selected?.tag_name === r.tag_name;
                return (
                  <li key={`${r.repository_id}-${r.tag_name}`}>
                    <button
                      type="button"
                      onClick={() => onSelectRelease(r)}
                      className={[
                        "w-full text-left rounded-lg border px-3 py-2.5 transition-colors",
                        isSel
                          ? "border-primary bg-primary/5 shadow-sm"
                          : "border-outline-variant/40 hover:bg-surface-container-low",
                      ].join(" ")}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-editorial font-bold text-sm text-on-surface truncate">
                          {r.tag_name}
                        </span>
                        <span className="shrink-0 text-[9px] font-editorial font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant">
                          {laneLabel(r.lane)}
                        </span>
                      </div>
                      <p className="text-[10px] text-on-surface-variant mt-1 truncate">
                        {r.repository_path}
                      </p>
                      <p className="text-[10px] text-on-surface-variant mt-0.5">
                        {formatShort(r.committed_at)} · {r.issue_count} issue
                        {r.issue_count === 1 ? "" : "s"} · {r.mr_count} MR{r.mr_count === 1 ? "" : "s"}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {relPag && relPag.total_pages > 0 && (
            <PaginationBar
              pagination={relPag}
              noun="failed releases"
              onPrev={() => setReleasePage((p) => Math.max(0, p - 1))}
              onNext={() => setReleasePage((p) => (relPag.has_next ? p + 1 : p))}
            />
          )}
        </div>

        <div className="flex flex-col min-h-[280px] min-w-0">
          <h3 className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline mb-3">
            Linked Jira issues
          </h3>
          {!selected ? (
            <p className="text-sm text-on-surface-variant font-editorial">Select a release.</p>
          ) : loadingIssues ? (
            <div className="space-y-2 flex-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-10 bg-surface-container animate-pulse rounded-lg" />
              ))}
            </div>
          ) : errIssues ? (
            <p className="text-sm text-error font-editorial">Could not load issues.</p>
          ) : (
            <>
              <p className="text-xs font-editorial text-on-surface mb-2">
                <span className="font-bold">{selected.tag_name}</span>
                <span className="text-on-surface-variant"> · {selected.repository_path}</span>
              </p>
              <div className="overflow-x-auto rounded-lg border border-outline-variant/40">
                <table className="w-full text-left text-sm min-w-[560px]">
                  <thead>
                    <tr className="bg-surface-container text-[10px] font-editorial uppercase tracking-widest text-outline">
                      <th className="px-3 py-2.5">Key</th>
                      <th className="px-3 py-2.5">Summary</th>
                      <th className="px-3 py-2.5">Priority</th>
                      <th className="px-3 py-2.5">Status</th>
                      <th className="px-3 py-2.5">Classification</th>
                    </tr>
                  </thead>
                  <tbody className="font-editorial text-on-surface divide-y divide-outline-variant/20">
                    {(issues?.items ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-3 py-6 text-center text-on-surface-variant text-sm">
                          No issues for this selection.
                        </td>
                      </tr>
                    ) : (
                      (issues?.items ?? []).map((row) => (
                        <tr key={row.jira_key} className="hover:bg-surface-container-low/60">
                          <td className="px-3 py-2 whitespace-nowrap">
                            {row.jira_browse_url ? (
                              <a
                                href={row.jira_browse_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-mono text-xs font-bold text-primary hover:underline"
                              >
                                {row.jira_key}
                              </a>
                            ) : (
                              <span className="font-mono text-xs font-bold">{row.jira_key}</span>
                            )}
                          </td>
                          <td className="px-3 py-2 max-w-[220px] truncate" title={row.summary ?? ""}>
                            {row.summary ?? "—"}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-on-surface-variant text-xs">
                            {row.priority ?? "—"}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-on-surface-variant text-xs">
                            {row.status ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-xs text-on-surface-variant max-w-[200px] truncate" title={row.healthmemo ?? ""}>
                            {row.healthmemo ?? "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              {issuePag && issuePag.total_pages > 0 && (
                <PaginationBar
                  pagination={issuePag}
                  noun="issues"
                  onPrev={() => setIssuePage((p) => Math.max(0, p - 1))}
                  onNext={() => setIssuePage((p) => (issuePag.has_next ? p + 1 : p))}
                />
              )}
            </>
          )}
        </div>
      </div>

      <p className="text-[10px] text-on-surface-variant font-editorial mt-6 leading-relaxed">
        Issues appear when nightly sync links a Jira production bug to this GitLab tag (bug_release).
        Only post-production classifications count toward CFR (healthy with healthmemo starting
        post-production), matching the snapshot formula.
      </p>
    </div>
  );
}
