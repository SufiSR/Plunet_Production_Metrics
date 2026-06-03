"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { adminApiClient } from "@/lib/admin-api-client";
import { useAdminDataHealth } from "@/lib/hooks";

const PAGE_SIZE = 20;

type ReasonDetails = {
  title: string;
  explanation: string;
  kpis: string[];
};

function unmatchedReasonDetails(reason: string): ReasonDetails {
  if (reason === "missing_jira_key") {
    return {
      title: "Missing JIRA Key",
      explanation:
        "The merge request cannot be reliably linked to a Jira issue. This weakens cross-system traceability between code changes and incidents.",
      kpis: ["Change Failure Rate (CFR)", "MTTR Alpha", "Lead Post-Production"],
    };
  }
  if (reason === "no_customer_release_tag") {
    return {
      title: "No customer release tag",
      explanation:
        "The merge request has no detected customer release tag, so release-based timing and incident-link analyses cannot place it into a customer delivery window.",
      kpis: ["Lead Time for Changes", "Lead Post-Production", "Deployment traceability"],
    };
  }
  if (reason.startsWith("lead_time_")) {
    return {
      title: "Lead-time derivation mismatch",
      explanation:
        "The MR has a non-matched lead-time derivation status, indicating incomplete commit/tag linkage for lead-time computation.",
      kpis: ["Lead Time for Changes", "Lead time diagnostics"],
    };
  }
  return {
    title: "Linkage inconsistency",
    explanation:
      "This merge request has incomplete cross-system linkage metadata, reducing confidence in metric derivations that depend on MR-to-release/Jira mapping.",
    kpis: ["Lead Time for Changes", "CFR", "MTTR Alpha"],
  };
}

function versionMismatchReasonDetails(reason: string): ReasonDetails {
  if (reason === "jira_versions_not_found_in_release_tags") {
    return {
      title: "Jira versions not found in release tags",
      explanation:
        "Affects/fix versions on the Jira bug do not match known Git tags. That prevents robust bug-to-release association in version-based paths.",
      kpis: ["Change Failure Rate (CFR)", "MTTR Alpha"],
    };
  }
  return {
    title: "Version linkage mismatch",
    explanation:
      "Version metadata between Jira and GitLab tags is inconsistent, reducing confidence in release-incident derivations.",
    kpis: ["CFR", "MTTR Alpha"],
  };
}

export default function AdminDataHealthPage() {
  const router = useRouter();
  const [unmatchedPage, setUnmatchedPage] = useState(0);
  const [mismatchPage, setMismatchPage] = useState(0);
  const [allowed, setAllowed] = useState(false);
  const restoreScrollRef = useRef<number | null>(null);

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

  const query = useAdminDataHealth(unmatchedPage, PAGE_SIZE, mismatchPage, PAGE_SIZE);

  useEffect(() => {
    if (restoreScrollRef.current === null || query.isLoading) return;
    const targetY = restoreScrollRef.current;
    requestAnimationFrame(() => {
      window.scrollTo({ top: targetY });
      restoreScrollRef.current = null;
    });
  }, [query.isLoading, query.data]);

  const captureScrollForPagination = useCallback(() => {
    restoreScrollRef.current = window.scrollY;
  }, []);

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
        <div className="h-20 bg-surface-container rounded-2xl animate-pulse" />
        <div className="h-56 bg-surface-container rounded-2xl animate-pulse" />
        <div className="h-56 bg-surface-container rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (query.error || !query.data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-3">
          <span className="material-symbols-outlined text-error text-5xl">error</span>
          <p className="text-on-surface-variant font-editorial">
            {query.error instanceof Error ? query.error.message : "Failed to load data health."}
          </p>
        </div>
      </div>
    );
  }

  const data = query.data;

  return (
    <div className="w-full pb-24 space-y-10">
      <header className="space-y-3">
        <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary">
          Operations
        </p>
        <h1 className="text-5xl font-editorial font-bold tracking-tight text-on-surface">
          Data Health
        </h1>
        <p className="text-on-surface-variant text-sm max-w-3xl">
          Transparency into DORA data quality, including healthy Jira bug classification, unmatched
          merge requests, and Jira version mismatches against known release tags.
        </p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <article className="rounded-2xl bg-surface-container-lowest p-5 border border-outline-variant">
          <p className="text-[10px] uppercase tracking-widest text-on-surface-variant font-editorial">
            Healthy Bugs
          </p>
          <p className="text-3xl font-editorial font-semibold mt-2">
            {data.summary.healthy_bugs_pct.toFixed(2)}%
          </p>
          <p className="text-xs text-on-surface-variant mt-1">
            {data.summary.healthy_bugs} / {data.summary.total_bugs} issues
          </p>
        </article>
        <article className="rounded-2xl bg-surface-container-lowest p-5 border border-outline-variant">
          <p className="text-[10px] uppercase tracking-widest text-on-surface-variant font-editorial">
            Unmatched MRs
          </p>
          <p className="text-3xl font-editorial font-semibold mt-2">
            {data.summary.unmatched_mr_count}
          </p>
          <p className="text-xs text-on-surface-variant mt-1">No stable Jira/release linkage</p>
        </article>
        <article className="rounded-2xl bg-surface-container-lowest p-5 border border-outline-variant">
          <p className="text-[10px] uppercase tracking-widest text-on-surface-variant font-editorial">
            Version Mismatches
          </p>
          <p className="text-3xl font-editorial font-semibold mt-2">
            {data.summary.version_mismatch_count}
          </p>
          <p className="text-xs text-on-surface-variant mt-1">Jira versions not found in tags</p>
        </article>
      </section>

      <section className="rounded-2xl bg-surface-container-lowest p-6 border border-outline-variant">
        <h2 className="text-xl font-editorial font-semibold mb-4">Jira Health Breakdown</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-on-surface-variant border-b border-outline-variant">
                <th className="py-2 pr-3">Healthy</th>
                <th className="py-2 pr-3">Memo</th>
                <th className="py-2 pr-3">Count</th>
                <th className="py-2 pr-3">Share</th>
              </tr>
            </thead>
            <tbody>
              {data.jira_health_breakdown.map((row, idx) => (
                <tr key={`${row.healthmemo}-${idx}`} className="border-b border-outline-variant/50">
                  <td className="py-2 pr-3">{row.healthy ? "true" : "false"}</td>
                  <td className="py-2 pr-3">{row.healthmemo ?? "-"}</td>
                  <td className="py-2 pr-3">{row.count}</td>
                  <td className="py-2 pr-3">{row.share_pct.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl bg-surface-container-lowest p-6 border border-outline-variant space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-editorial font-semibold">Unmatched Merge Requests</h2>
          <div className="flex items-center gap-2 text-xs">
            <button
              className="px-3 py-1 rounded border border-outline-variant disabled:opacity-50"
              disabled={!data.unmatched_merge_requests_pagination.has_previous}
              onClick={() => {
                captureScrollForPagination();
                setUnmatchedPage((p) => Math.max(0, p - 1));
              }}
            >
              Prev
            </button>
            <span>
              Page {data.unmatched_merge_requests_pagination.page + 1} /{" "}
              {Math.max(1, data.unmatched_merge_requests_pagination.total_pages)}
            </span>
            <button
              className="px-3 py-1 rounded border border-outline-variant disabled:opacity-50"
              disabled={!data.unmatched_merge_requests_pagination.has_next}
              onClick={() => {
                captureScrollForPagination();
                setUnmatchedPage((p) => p + 1);
              }}
            >
              Next
            </button>
          </div>
        </div>
        <p className="text-xs text-on-surface-variant">
          These rows identify merge requests which cannot be reliably linked to a JIRA issue. This
          weakens cross-system traceability between code changes and incidents. Impacts: Change
          Failure Rate (CFR), MTTR Alpha, Lead Post-Production
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-on-surface-variant border-b border-outline-variant">
                <th className="py-2 pr-3">MR</th>
                <th className="py-2 pr-3">Repository</th>
                <th className="py-2 pr-3">Jira</th>
                <th className="py-2 pr-3">Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.unmatched_merge_requests.length === 0 ? (
                <tr>
                  <td className="py-3 text-on-surface-variant" colSpan={4}>
                    No unmatched merge requests in current page.
                  </td>
                </tr>
              ) : (
                data.unmatched_merge_requests.map((row) => (
                  <tr
                    key={`${row.repository_id}-${row.gitlab_mr_id}`}
                    className="border-b border-outline-variant/50"
                  >
                    <td className="py-2 pr-3">
                      {row.gitlab_merge_request_url ? (
                        <Link
                          href={row.gitlab_merge_request_url}
                          target="_blank"
                          className="text-primary hover:underline"
                        >
                          !{row.gitlab_mr_id}
                        </Link>
                      ) : (
                        `!${row.gitlab_mr_id}`
                      )}
                    </td>
                    <td className="py-2 pr-3">{row.repository_path}</td>
                    <td className="py-2 pr-3">
                      {row.jira_key && row.jira_browse_url ? (
                        <Link href={row.jira_browse_url} target="_blank" className="text-primary hover:underline">
                          {row.jira_key}
                        </Link>
                      ) : (
                        row.jira_key ?? "-"
                      )}
                    </td>
                    <td className="py-2 pr-3">{unmatchedReasonDetails(row.reason).title}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl bg-surface-container-lowest p-6 border border-outline-variant space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-editorial font-semibold">Version Mismatches</h2>
          <div className="flex items-center gap-2 text-xs">
            <button
              className="px-3 py-1 rounded border border-outline-variant disabled:opacity-50"
              disabled={!data.version_mismatches_pagination.has_previous}
              onClick={() => {
                captureScrollForPagination();
                setMismatchPage((p) => Math.max(0, p - 1));
              }}
            >
              Prev
            </button>
            <span>
              Page {data.version_mismatches_pagination.page + 1} /{" "}
              {Math.max(1, data.version_mismatches_pagination.total_pages)}
            </span>
            <button
              className="px-3 py-1 rounded border border-outline-variant disabled:opacity-50"
              disabled={!data.version_mismatches_pagination.has_next}
              onClick={() => {
                captureScrollForPagination();
                setMismatchPage((p) => p + 1);
              }}
            >
              Next
            </button>
          </div>
        </div>
        <p className="text-xs text-on-surface-variant">
          Affects/fix versions on the Jira bug do not match known Git tags. That prevents robust
          bug-to-release association in version-based paths. Impacts: Change Failure Rate (CFR),
          MTTR Alpha
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-on-surface-variant border-b border-outline-variant">
                <th className="py-2 pr-3">Jira</th>
                <th className="py-2 pr-3">Summary</th>
                <th className="py-2 pr-3">Unmatched Versions</th>
                <th className="py-2 pr-3">Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.version_mismatches.length === 0 ? (
                <tr>
                  <td className="py-3 text-on-surface-variant" colSpan={4}>
                    No version mismatches in current page.
                  </td>
                </tr>
              ) : (
                data.version_mismatches.map((row) => (
                  <tr key={row.jira_key} className="border-b border-outline-variant/50">
                    <td className="py-2 pr-3">
                      {row.jira_browse_url ? (
                        <Link href={row.jira_browse_url} target="_blank" className="text-primary hover:underline">
                          {row.jira_key}
                        </Link>
                      ) : (
                        row.jira_key
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      {row.summary ?? "-"}
                      {row.last_updated_at ? (
                        <span className="text-xs text-on-surface-variant">
                          {" "}
                          (last updated: {new Date(row.last_updated_at).toLocaleDateString()})
                        </span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3">{row.unmatched_versions.join(", ") || "-"}</td>
                    <td className="py-2 pr-3">{versionMismatchReasonDetails(row.reason).title}</td>
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
