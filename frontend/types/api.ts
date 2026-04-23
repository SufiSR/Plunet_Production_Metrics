// ─────────────────────────────────────────────────────────────────────────────
// API response types — aligned with backend OpenAPI schema (DEVOPS-440)
// ─────────────────────────────────────────────────────────────────────────────

export type DoraLevel = "ELITE" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type SyncRunStatus = "SUCCESS" | "PARTIAL_FAILURE" | "FAILED" | "RUNNING";
export type PeriodType = "30d" | "quarterly" | "yearly";
/** Query param for GET /metrics/* — optional lead time disaggregation (DEVOPS-510). */
export type LeadTimeBreakdown = "none" | "branch" | "stream";

export interface LeadTimeBreakdownBucket {
  median_lead_time_minutes: number | null;
  sample_count: number;
  dev_review_median_minutes?: number | null;
  release_wait_median_minutes?: number | null;
}

// ── Metrics current ──────────────────────────────────────────────────────────

export interface MetricValue {
  value: number | null;
  unit: string;
  dora_level: DoraLevel;
  trend_pct: number | null;
  secondary_text?: string;
}

/** Backend `lead_time_diagnostics` — MR-based DORA lead time transparency. */
export interface LeadTimeDiagnostics {
  definition: string;
  sample_count: number;
  match_counts: Record<string, number>;
}

export interface MetricsCurrentResponse {
  generated_at: string; // ISO 8601
  period_label: string;
  deployment_frequency: MetricValue;
  lead_time_for_changes: MetricValue;
  change_failure_rate: MetricValue;
  mttr_alpha: MetricValue;
  lead_post_production?: MetricValue;
  logged_vs_calendar?: {
    logged_hours: number | null;
    calendar_days: number | null;
  };
  lead_time_diagnostics?: LeadTimeDiagnostics | null;
  lead_time_by_branch?: Record<string, LeadTimeBreakdownBucket> | null;
  lead_time_by_stream?: Record<string, LeadTimeBreakdownBucket> | null;
}

// ── Metrics history ──────────────────────────────────────────────────────────

export interface MetricDataPoint {
  date: string; // ISO 8601 date
  deployment_frequency: number | null;
  lead_time_for_changes: number | null;
  lead_time_dev_review_hours?: number | null;
  lead_time_release_wait_hours?: number | null;
  /** MR count summed across repos for that period (lead time sample). */
  lead_time_sample_count?: number | null;
  change_failure_rate: number | null;
  mttr_alpha: number | null;
  lead_time_by_branch?: Record<string, LeadTimeBreakdownBucket> | null;
  lead_time_by_stream?: Record<string, LeadTimeBreakdownBucket> | null;
}

export interface MetricsHistoryResponse {
  period: PeriodType;
  data_points: MetricDataPoint[];
}

// ── Sync status (GET /api/sync/status) ───────────────────────────────────────

export interface CollectorStatusBlock {
  status: string;
  records_processed: Record<string, number>;
}

export interface LastSyncBlock {
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  status: "SUCCESS" | "PARTIAL_FAILURE" | "FAILED";
  collectors: Record<string, CollectorStatusBlock>;
  snapshots_generated: number;
  snapshot_generated_at: string | null;
  error_message?: string | null;
}

export interface PipelinePhaseBlock {
  status: "pending" | "running" | "success" | "failed" | "skipped" | string;
  message?: string | null;
  records_processed: Record<string, number>;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
}

export interface PipelineRuntimeBlock {
  current_phase: string;
  phase_started_at: string | null;
  phases: Record<string, PipelinePhaseBlock>;
  errors: string[];
}

export interface SyncStatusResponse {
  last_sync: LastSyncBlock | null;
  last_successful_sync_at: string | null;
  next_scheduled_sync: string | null;
  sync_schedule_cron: string;
  pipeline_in_progress: boolean;
  pipeline_run_started_at: string | null;
  pipeline_run_trigger: string | null;
  pipeline_runtime: PipelineRuntimeBlock | null;
}

// ── Repositories ─────────────────────────────────────────────────────────────

export interface RepositoryListItem {
  id: number;
  gitlab_id: number;
  name: string;
  path: string;
  default_branch: string;
  active: boolean;
}

export interface RepositoriesResponse {
  repositories: RepositoryListItem[];
  total: number;
}

export interface ReleaseTimelineItem {
  repository_id: number;
  repository_path: string;
  tag_name: string;
  committed_at: string;
  customer_release: boolean;
  version_major: number | null;
  version_minor: number | null;
  version_patch: number | null;
}

export interface ReleaseTimelineResponse {
  items: ReleaseTimelineItem[];
  total: number;
}

export interface OffsetPagination {
  page: number;
  size: number;
  total_elements: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface CustomerReleaseDrilldownItem {
  repository_id: number;
  repository_path: string;
  tag_name: string;
  committed_at: string;
  version_major: number | null;
  version_minor: number | null;
  version_patch: number | null;
  lane: string;
  mr_count: number;
}

export interface CustomerReleaseDrilldownListResponse {
  items: CustomerReleaseDrilldownItem[];
  pagination: OffsetPagination;
}

export interface ReleaseMergeRequestRow {
  gitlab_mr_id: number;
  title: string | null;
  target_branch: string;
  merged_at: string;
  lead_time_hours: number | null;
  release_wait_time_hours: number | null;
  jira_key: string | null;
  /** Same rules as lead-time KPIs: tag date present, and not matching admin “release-only MR” markers when that filter is on. */
  included_in_lead_time_metrics: boolean;
}

export interface ReleaseMergeRequestListResponse {
  repository_id: number;
  tag_name: string;
  items: ReleaseMergeRequestRow[];
  pagination: OffsetPagination;
  previous_customer_tag?: string | null;
  gitlab_compare_url?: string | null;
  mr_with_jira_key_count?: number;
}

export interface FailedCustomerReleaseDrilldownItem {
  repository_id: number;
  repository_path: string;
  tag_name: string;
  committed_at: string;
  version_major: number | null;
  version_minor: number | null;
  version_patch: number | null;
  lane: string;
  mr_count: number;
  issue_count: number;
}

export interface FailedCustomerReleaseDrilldownListResponse {
  items: FailedCustomerReleaseDrilldownItem[];
  pagination: OffsetPagination;
}

export interface ReleaseProductionBugRow {
  jira_key: string;
  summary: string | null;
  status: string | null;
  priority: string | null;
  healthmemo: string | null;
  jira_browse_url: string | null;
}

export interface ReleaseProductionBugListResponse {
  repository_id: number;
  tag_name: string;
  items: ReleaseProductionBugRow[];
  pagination: OffsetPagination;
}

export interface MttrAlphaResolutionPathCount {
  resolution_path: string;
  count: number;
}

export interface MttrAlphaSummaryResponse {
  period_type: "WEEK" | "MONTH" | "QUARTER";
  period_start: string;
  period_end: string;
  incident_count: number;
  median_minutes: number | null;
  resolution_paths: MttrAlphaResolutionPathCount[];
}

export interface MttrAlphaIncidentRow {
  jira_key: string;
  summary: string | null;
  status: string | null;
  priority: string | null;
  healthmemo: string | null;
  created_at: string | null;
  first_fix_release_date: string | null;
  first_fix_release_tag: string | null;
  mttr_alpha_minutes: number | null;
  mttr_alpha_resolution_path: string | null;
  jira_browse_url: string | null;
}

export interface MttrAlphaIncidentListResponse {
  period_type: "WEEK" | "MONTH" | "QUARTER";
  period_start: string;
  period_end: string;
  items: MttrAlphaIncidentRow[];
  pagination: OffsetPagination;
}

export interface MttrAlphaReleaseDrilldownItem {
  first_fix_release_tag: string;
  first_fix_release_date: string;
  issue_count: number;
  median_minutes: number | null;
}

export interface MttrAlphaReleaseDrilldownListResponse {
  period_type: "WEEK" | "MONTH" | "QUARTER";
  period_start: string;
  period_end: string;
  items: MttrAlphaReleaseDrilldownItem[];
  pagination: OffsetPagination;
}

// ── Error response ───────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  status: number;
}
