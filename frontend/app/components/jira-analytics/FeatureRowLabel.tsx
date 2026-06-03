"use client";

import type { FeatureHoursMatrixRow } from "@/types/jira-analytics";
import { JiraIssueLink, jiraBrowseUrl } from "@/app/components/jira-analytics/JiraIssueLink";

function formatIsoDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDateRange(start?: string | null, end?: string | null): string {
  if (start && end) {
    return `${formatIsoDate(start)} – ${formatIsoDate(end)} (target)`;
  }
  if (start) return `${formatIsoDate(start)} – No target date`;
  if (end) return `No start date – ${formatIsoDate(end)} (target)`;
  return "No start date – No target date";
}

interface FeatureRowLabelProps {
  row: FeatureHoursMatrixRow;
  jiraBaseUrl: string;
}

export function FeatureRowLabel({ row, jiraBaseUrl }: FeatureRowLabelProps) {
  if (row.row_type !== "feature") {
    return (
      <span className="italic text-on-surface-variant">{row.label}</span>
    );
  }

  const name = row.feature_name ?? row.label;
  const dateRange = formatDateRange(row.start_date, row.target_end_date);
  const metaParts = [
    dateRange,
    `Progress: ${row.delivery_progress?.trim() || "Not set"}`,
    `Team: ${row.team_name?.trim() || "Not assigned"}`,
  ];

  return (
    <div className="min-w-0">
      <div className="font-medium text-on-surface leading-snug">
        <span className="block truncate">{name}</span>
        {row.root_key ? (
          <JiraIssueLink
            issueKey={row.root_key}
            issueUrl={jiraBrowseUrl(jiraBaseUrl, row.root_key)}
            jiraBaseUrl={jiraBaseUrl}
            className="text-xs font-normal"
          />
        ) : null}
      </div>
      <div className="text-xs text-on-surface-variant mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
        {metaParts.map((part, index) => (
          <span key={`${part}-${index}`}>{part}</span>
        ))}
      </div>
    </div>
  );
}
