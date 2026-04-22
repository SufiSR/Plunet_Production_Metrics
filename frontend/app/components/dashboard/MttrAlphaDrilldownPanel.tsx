"use client";

import { useEffect, useMemo, useState } from "react";
import { useMttrAlphaIncidents, useMttrAlphaReleases, useMttrAlphaSummary } from "@/lib/hooks";

const RELEASE_PAGE_SIZE = 20;
const INCIDENT_PAGE_SIZE = 50;

function formatShort(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 24 * 60) return `${(minutes / 60).toFixed(1)}h`;
  return `${(minutes / (24 * 60)).toFixed(1)}d`;
}

function pathLabel(path: string): string {
  if (path === "mr_jira_key") return "MR Jira Key";
  if (path === "fix_version") return "Fix Version";
  if (path === "unknown") return "Unknown";
  return path;
}

export function MttrAlphaDrilldownPanel() {
  const [releasePage, setReleasePage] = useState(0);
  const [incidentPage, setIncidentPage] = useState(0);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const { data: summary, isLoading: loadingSummary, isError: summaryError } = useMttrAlphaSummary();
  const { data: releases, isLoading: loadingReleases, isError: releasesError } = useMttrAlphaReleases(
    releasePage,
    RELEASE_PAGE_SIZE,
  );
  const { data: incidents, isLoading: loadingIncidents, isError: incidentsError } = useMttrAlphaIncidents(
    incidentPage,
    INCIDENT_PAGE_SIZE,
    selectedTag,
  );
  const releaseItems = useMemo(() => releases?.items ?? [], [releases?.items]);
  const relPag = releases?.pagination;
  const incPag = incidents?.pagination;

  useEffect(() => {
    if (!releaseItems.length) {
      setSelectedTag(null);
      return;
    }
    const found = selectedTag && releaseItems.some((r) => r.first_fix_release_tag === selectedTag);
    if (!found) {
      setSelectedTag(releaseItems[0].first_fix_release_tag);
      setIncidentPage(0);
    }
  }, [releaseItems, selectedTag]);

  return (
    <div className="bg-surface-container-lowest p-8 rounded-xl shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)] dark:shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]">
      <div className="mb-6">
        <h2 className="text-2xl font-editorial font-bold tracking-tight text-on-surface">
          MTTR Alpha details
        </h2>
        <p className="text-xs font-editorial text-on-surface-variant uppercase tracking-widest mt-1">
          Incident-level view for the active period window (same period type as trend chart).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(240px,300px)_1fr] gap-8">
        <div className="space-y-3">
          <h3 className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline">
            Release versions
          </h3>
          {loadingReleases ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-surface-container animate-pulse rounded-lg" />
              ))}
            </div>
          ) : releasesError ? (
            <p className="text-sm text-error font-editorial">Could not load MTTR Alpha releases.</p>
          ) : (
            <>
              <div className="rounded-lg border border-outline-variant/40 bg-surface-container-low px-3 py-2">
                <p className="text-[10px] text-on-surface-variant uppercase tracking-widest">Incidents</p>
                <p className="text-lg font-editorial font-bold text-on-surface">
                  {summary?.incident_count ?? 0}
                </p>
                <p className="text-[10px] text-on-surface-variant">
                  Median: {formatMinutes(summary?.median_minutes ?? null)}
                </p>
              </div>
              <ul className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
                {releaseItems.map((row) => {
                  const selected = selectedTag === row.first_fix_release_tag;
                  return (
                    <li key={row.first_fix_release_tag}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedTag(row.first_fix_release_tag);
                          setIncidentPage(0);
                        }}
                        className={[
                          "w-full rounded-lg border px-3 py-2 text-left transition-colors",
                          selected
                            ? "border-primary bg-primary/5 shadow-sm"
                            : "border-outline-variant/40 hover:bg-surface-container-low",
                        ].join(" ")}
                      >
                        <p className="text-sm font-editorial font-bold text-on-surface truncate">
                          {row.first_fix_release_tag}
                        </p>
                        <p className="text-[10px] text-on-surface-variant">
                          {formatShort(row.first_fix_release_date)} · {row.issue_count} issue
                          {row.issue_count === 1 ? "" : "s"} · median {formatMinutes(row.median_minutes)}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {relPag && relPag.total_pages > 0 && (
                <div className="flex items-center justify-between gap-3 mt-3 pt-3 border-t border-outline-variant/30">
                  <p className="text-[10px] font-editorial text-on-surface-variant uppercase tracking-widest">
                    {relPag.total_elements} releases
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setReleasePage((p) => Math.max(0, p - 1))}
                      disabled={!relPag.has_previous}
                      className="px-3 py-1.5 text-[10px] font-editorial font-bold uppercase tracking-wider rounded-md bg-surface-container text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container-high transition-colors"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      onClick={() => setReleasePage((p) => (relPag.has_next ? p + 1 : p))}
                      disabled={!relPag.has_next}
                      className="px-3 py-1.5 text-[10px] font-editorial font-bold uppercase tracking-wider rounded-md bg-surface-container text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container-high transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="min-w-0">
          <h3 className="text-[10px] font-editorial font-bold uppercase tracking-widest text-outline mb-3">
            Incidents (longest first)
          </h3>
          {loadingIncidents ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-10 bg-surface-container animate-pulse rounded-lg" />
              ))}
            </div>
          ) : incidentsError ? (
            <p className="text-sm text-error font-editorial">Could not load incidents.</p>
          ) : (
            <>
            <p className="text-xs font-editorial text-on-surface mb-2">
              <span className="font-bold">{selectedTag ?? "All releases"}</span>
              {summaryError ? null : (
                <span className="text-on-surface-variant">
                  {" "}
                  · paths:{" "}
                  {(summary?.resolution_paths ?? [])
                    .map((p) => `${pathLabel(p.resolution_path)} ${p.count}`)
                    .join(" · ")}
                </span>
              )}
            </p>
            <div className="overflow-x-auto rounded-lg border border-outline-variant/40">
                <table className="w-full text-left text-sm min-w-[760px]">
                  <thead>
                    <tr className="bg-surface-container text-[10px] font-editorial uppercase tracking-widest text-outline">
                      <th className="px-3 py-2.5">Key</th>
                      <th className="px-3 py-2.5">Summary</th>
                      <th className="px-3 py-2.5">MTTR Alpha</th>
                      <th className="px-3 py-2.5">Path</th>
                      <th className="px-3 py-2.5">Fix release</th>
                      <th className="px-3 py-2.5">Bug created</th>
                    </tr>
                  </thead>
                  <tbody className="font-editorial text-on-surface divide-y divide-outline-variant/20">
                    {(incidents?.items ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-3 py-6 text-center text-on-surface-variant text-sm">
                          No MTTR Alpha incidents found in this period.
                        </td>
                      </tr>
                    ) : (
                      (incidents?.items ?? []).map((row) => (
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
                          <td className="px-3 py-2 max-w-[260px] truncate" title={row.summary ?? ""}>
                            {row.summary ?? "—"}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap tabular-nums">
                            {formatMinutes(row.mttr_alpha_minutes)}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-xs text-on-surface-variant">
                            {pathLabel(row.mttr_alpha_resolution_path ?? "unknown")}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-xs text-on-surface-variant">
                            {row.first_fix_release_tag ?? "—"} · {formatShort(row.first_fix_release_date)}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-xs text-on-surface-variant">
                            {formatShort(row.created_at)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              {incPag && incPag.total_pages > 0 && (
                <div className="flex items-center justify-between gap-3 mt-4 pt-4 border-t border-outline-variant/30">
                  <p className="text-[10px] font-editorial text-on-surface-variant uppercase tracking-widest">
                    {incPag.total_elements} incidents · Page {incPag.page + 1} of {incPag.total_pages}
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setIncidentPage((p) => Math.max(0, p - 1))}
                      disabled={!incPag.has_previous}
                      className="px-3 py-1.5 text-[10px] font-editorial font-bold uppercase tracking-wider rounded-md bg-surface-container text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container-high transition-colors"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      onClick={() => setIncidentPage((p) => (incPag.has_next ? p + 1 : p))}
                      disabled={!incPag.has_next}
                      className="px-3 py-1.5 text-[10px] font-editorial font-bold uppercase tracking-wider rounded-md bg-surface-container text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container-high transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
