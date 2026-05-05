export type UserRole = "admin" | null;

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  role: "admin";
  expires_at: string | null;
}

export interface MeResponse {
  role: UserRole;
  username: string | null;
}

export type WorklogRole = "pm" | "dev" | "qa";

export interface JiraWorklogUserAssignment {
  jira_account_id: string;
  role: WorklogRole;
  team: string;
}

export interface WorklogAuthorListItem {
  jira_account_id: string | null;
  author: string | null;
}

export interface WorklogAuthorListResponse {
  items: WorklogAuthorListItem[];
  page: number;
  size: number;
  total_elements: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface AdminConfigResponse {
  environment: string;
  gitlab_url: string;
  gitlab_token_hint: string | null;
  gitlab_project_paths: string[];
  target_branches: string[];
  additional_merge_target_branches: string[];
  non_customer_release_markers: string[];
  exclude_release_only_mrs_from_lead_time: boolean;
  release_mr_title_markers: string[];
  release_mr_source_branch_markers: string[];
  jira_url: string;
  jira_username: string;
  jira_token_hint: string | null;
  excluded_projects: string[];
  ready_for_qa_status_names: string[];
  production_bug_indicator_cf_ids: string[];
  mttr_alpha_priorities: string[];
  sync_cron_hour: number;
  sync_cron_minute: number;
  lookback_days: number;
  notifications_webhook_url: string | null;
  jira_worklog_user_assignments: JiraWorklogUserAssignment[];
  jira_worklog_author_denylist: string[];
}

export interface AdminConfigPatch {
  environment?: string;
  gitlab_url?: string;
  gitlab_token?: string;
  gitlab_project_paths?: string[];
  target_branches?: string[];
  additional_merge_target_branches?: string[];
  non_customer_release_markers?: string[];
  exclude_release_only_mrs_from_lead_time?: boolean;
  release_mr_title_markers?: string[];
  release_mr_source_branch_markers?: string[];
  jira_url?: string;
  jira_username?: string;
  jira_token?: string;
  excluded_projects?: string[];
  ready_for_qa_status_names?: string[];
  production_bug_indicator_cf_ids?: string[];
  mttr_alpha_priorities?: string[];
  sync_cron_hour?: number;
  sync_cron_minute?: number;
  lookback_days?: number;
  notifications_webhook_url?: string | null;
  jira_worklog_user_assignments?: JiraWorklogUserAssignment[];
  jira_worklog_author_denylist?: string[];
}

export interface WebhookTestRequest {
  webhook_url?: string | null;
}

export interface WebhookTestResponse {
  delivered: boolean;
  effective_webhook_url: string;
  payload: Record<string, unknown>;
}

export interface OffsetPagination {
  page: number;
  size: number;
  total_elements: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface DataHealthSummary {
  total_bugs: number;
  healthy_bugs: number;
  healthy_bugs_pct: number;
  unmatched_mr_count: number;
  version_mismatch_count: number;
}

export interface JiraHealthBreakdownRow {
  healthy: boolean;
  healthmemo: string | null;
  count: number;
  share_pct: number;
}

export interface UnmatchedMergeRequestRow {
  repository_id: number;
  repository_path: string;
  gitlab_mr_id: number;
  title: string | null;
  merged_at: string;
  jira_key: string | null;
  reason: string;
  gitlab_merge_request_url: string | null;
  jira_browse_url: string | null;
}

export interface VersionMismatchRow {
  jira_key: string;
  summary: string | null;
  last_updated_at: string | null;
  healthmemo: string | null;
  affects_versions: string[];
  fix_versions: string[];
  unmatched_versions: string[];
  reason: string;
  jira_browse_url: string | null;
}

export interface DataHealthResponse {
  generated_at: string;
  summary: DataHealthSummary;
  jira_health_breakdown: JiraHealthBreakdownRow[];
  unmatched_merge_requests: UnmatchedMergeRequestRow[];
  unmatched_merge_requests_pagination: OffsetPagination;
  version_mismatches: VersionMismatchRow[];
  version_mismatches_pagination: OffsetPagination;
}

export type AdminRawTableName =
  | "sync_log"
  | "repository"
  | "release"
  | "production_bug"
  | "merge_request"
  | "issue_worklog";

export type AdminRawTableSortDirection = "asc" | "desc";

export interface AdminRawTableColumn {
  key: string;
  label: string;
  sortable: boolean;
}

export interface AdminRawTableResponse {
  table: AdminRawTableName;
  columns: AdminRawTableColumn[];
  rows: Record<string, unknown>[];
  pagination: OffsetPagination;
}
