"use client";

import { useEffect, useMemo, useState } from "react";
import { useReleaseDrilldown, useReleaseMergeRequests, useRepositories } from "@/lib/hooks";
import type { CustomerReleaseDrilldownItem } from "@/types/api";

type SelectedRelease = {
  repository_id: number;
  tag_name: string;
  repository_path: string;
};

const RELEASE_PAGE_SIZE = 20;
const MR_PAGE_SIZE = 50;

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

function hoursCell(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(1)} h`;
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

export function ReleaseDrilldownPanel() {
  const [repoFilter, setRepoFilter] = useState<number | "all">("all");
  const [releasePage, setReleasePage] = useState(0);
  const [mrPage, setMrPage] = useState(0);
  const [selected, setSelected] = useState<SelectedRelease | null>(null);

  const { data: repos } = useRepositories();
  const { data: drilldown, isLoading: loadingReleases, isError: errReleases } = useReleaseDrilldown(
    releasePage,
    repoFilter === "all" ? null : repoFilter,
    RELEASE_PAGE_SIZE,
  );
  const { data: mrs, isLoading: loadingMrs, isError: errMrs } = useReleaseMergeRequests(
    selected?.repository_id ?? null,
    selected?.tag_name ?? null,
    mrPage,
    MR_PAGE_SIZE,
  );

  const items = useMemo(() => drilldown?.items ?? [], [drilldown?.items]);
  const relPag = drilldown?.pagination;
  const mrPag = mrs?.pagination;

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
      setMrPage(0);
    }
  }, [items, selected]);

  const onSelectRelease = (r: CustomerReleaseDrilldownItem) => {
    setSelected({
      repository_id: r.repository_id,
      tag_name: r.tag_name,
      repository_path: r.repository_path,
    });
    setMrPage(0);
  };

  const onRepoFilterChange = (v: string) => {
    setRepoFilter(v === "all" ? "all" : Number(v));
    setReleasePage(0);
    setSelected(null);
    setMrPage(0);
  };

  return (
    <div className="bg-surface-container-lowest p-8 rounded-xl shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-editorial font-bold tracking-tight text-on-surface">
            Customer releases → merge requests
          </h2>
          <p className="text-xs font-editorial text-on-surface-variant uppercase tracking-widest mt-1">
            MRs where this tag is the first customer release
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
        {/* Release list */}
        <div className="flex flex-col min-h-[280px]">
          <h3 className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline mb-3">
            Releases
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
              No customer releases found.
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
                        {formatShort(r.committed_at)} · {r.mr_count} MR{r.mr_count === 1 ? "" : "s"}
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
              noun="releases"
              onPrev={() => setReleasePage((p) => Math.max(0, p - 1))}
              onNext={() => setReleasePage((p) => (relPag.has_next ? p + 1 : p))}
            />
          )}
        </div>

        {/* MR detail */}
        <div className="flex flex-col min-h-[280px] min-w-0">
          <h3 className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline mb-3">
            Merge requests
          </h3>
          {!selected ? (
            <p className="text-sm text-on-surface-variant font-editorial">Select a release.</p>
          ) : loadingMrs ? (
            <div className="space-y-2 flex-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-10 bg-surface-container animate-pulse rounded-lg" />
              ))}
            </div>
          ) : errMrs ? (
            <p className="text-sm text-error font-editorial">Could not load merge requests.</p>
          ) : (
            <>
              <p className="text-xs font-editorial text-on-surface mb-2">
                <span className="font-bold">{selected.tag_name}</span>
                <span className="text-on-surface-variant"> · {selected.repository_path}</span>
              </p>
              <div className="flex flex-col gap-1.5 mb-3 text-[10px] text-on-surface-variant">
                <p>
                  MRs with Jira key:{" "}
                  <span className="font-bold text-on-surface">{mrs?.mr_with_jira_key_count ?? 0}</span>
                  {mrPag ? (
                    <>
                      {" "}
                      / {mrPag.total_elements} with{" "}
                      <code className="font-mono text-[9px]">first_customer_tag</code>
                    </>
                  ) : null}
                </p>
                {mrs?.gitlab_compare_url ? (
                  <a
                    href={mrs.gitlab_compare_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary font-bold hover:underline w-fit"
                  >
                    View commits vs previous customer tag on GitLab
                    {mrs.previous_customer_tag
                      ? ` (${mrs.previous_customer_tag} → ${selected.tag_name})`
                      : ""}
                  </a>
                ) : (
                  <p className="text-outline italic">
                    No earlier customer tag in this database — compare link unavailable.
                  </p>
                )}
              </div>
              <div className="overflow-x-auto rounded-lg border border-outline-variant/40">
                <table className="w-full text-left text-sm min-w-[640px]">
                  <thead>
                    <tr className="bg-surface-container text-[10px] font-editorial uppercase tracking-widest text-outline">
                      <th className="px-3 py-2.5">MR</th>
                      <th className="px-3 py-2.5">Title</th>
                      <th className="px-3 py-2.5">Branch</th>
                      <th className="px-3 py-2.5">Merged</th>
                      <th className="px-3 py-2.5 text-right">Lead</th>
                      <th className="px-3 py-2.5 text-right">Rel. wait</th>
                      <th className="px-3 py-2.5">Jira</th>
                    </tr>
                  </thead>
                  <tbody className="font-editorial text-on-surface divide-y divide-outline-variant/20">
                    {(mrs?.items ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-3 py-6 text-center text-on-surface-variant text-sm">
                          No merge requests mapped to this tag.
                        </td>
                      </tr>
                    ) : (
                      (mrs?.items ?? []).map((row) => (
                        <tr key={row.gitlab_mr_id} className="hover:bg-surface-container-low/60">
                          <td className="px-3 py-2 font-bold whitespace-nowrap">!{row.gitlab_mr_id}</td>
                          <td className="px-3 py-2 max-w-[200px] truncate" title={row.title ?? ""}>
                            {row.title ?? "—"}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-on-surface-variant">
                            {row.target_branch}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-xs text-on-surface-variant">
                            {formatShort(row.merged_at)}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {hoursCell(row.lead_time_hours)}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {hoursCell(row.release_wait_time_hours)}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-xs font-mono">
                            {row.jira_key ?? "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              {mrPag && mrPag.total_pages > 0 && (
                <PaginationBar
                  pagination={mrPag}
                  noun="merge requests"
                  onPrev={() => setMrPage((p) => Math.max(0, p - 1))}
                  onNext={() => setMrPage((p) => (mrPag.has_next ? p + 1 : p))}
                />
              )}
            </>
          )}
        </div>
      </div>

      <p className="text-[10px] text-on-surface-variant font-editorial mt-6 leading-relaxed">
        MR-based view: only merge requests ingested from configured GitLab target + additional merge
        branches. Lead = first commit → tag; release wait = merge → tag. Commits shipped without a
        merged MR on those branches will not appear here — use the GitLab compare link to audit them.
      </p>
    </div>
  );
}
