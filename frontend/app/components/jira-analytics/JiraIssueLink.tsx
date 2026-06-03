"use client";

import type { ReactNode } from "react";

interface JiraIssueLinkProps {
  issueKey: string;
  issueUrl: string;
  jiraBaseUrl?: string;
  className?: string;
  children?: ReactNode;
}

export function JiraIssueLink({
  issueKey,
  issueUrl,
  jiraBaseUrl,
  className = "",
  children,
}: JiraIssueLinkProps) {
  const href =
    jiraBaseUrl != null ? normalizeJiraIssueUrl(issueUrl, issueKey, jiraBaseUrl) : issueUrl;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-primary hover:underline font-medium ${className}`.trim()}
      onClick={(event) => event.stopPropagation()}
    >
      {children ?? issueKey}
    </a>
  );
}

export function jiraBrowseUrl(baseUrl: string, issueKey: string): string {
  return `${baseUrl.replace(/\/$/, "")}/browse/${issueKey}`;
}

/** Normalize API self URLs to human-facing Jira browse links. */
export function normalizeJiraIssueUrl(issueUrl: string, issueKey: string, jiraBaseUrl: string): string {
  const trimmed = issueUrl.trim();
  if (!trimmed) {
    return jiraBrowseUrl(jiraBaseUrl, issueKey);
  }
  if (/\/browse\/[^/]+$/i.test(trimmed)) {
    return trimmed;
  }
  if (/\/rest\/api\//i.test(trimmed) || /\/issue\/\d+$/i.test(trimmed)) {
    return jiraBrowseUrl(jiraBaseUrl, issueKey);
  }
  return trimmed;
}
