// ─────────────────────────────────────────────────────────────────────────────
// API response types — aligned with backend OpenAPI schema (DEVOPS-440)
// ─────────────────────────────────────────────────────────────────────────────

export type DoraLevel = "ELITE" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type SyncRunStatus = "SUCCESS" | "PARTIAL_FAILURE" | "FAILED" | "RUNNING";
export type PeriodType = "30d" | "quarterly" | "yearly";

// ── Metrics current ──────────────────────────────────────────────────────────

export interface MetricValue {
  value: number | null;
  unit: string;
  dora_level: DoraLevel;
  trend_pct: number | null;
  secondary_text?: string;
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
}

// ── Metrics history ──────────────────────────────────────────────────────────

export interface MetricDataPoint {
  date: string; // ISO 8601 date
  deployment_frequency: number | null;
  lead_time_for_changes: number | null;
  change_failure_rate: number | null;
  mttr_alpha: number | null;
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

export interface RepositoryMetrics {
  repository_path: string;
  deployment_frequency: number | null;
  lead_time_for_changes: number | null;
  change_failure_rate: number | null;
  mttr_alpha: number | null;
  dora_level: DoraLevel;
}

export interface RepositoriesResponse {
  repositories: RepositoryMetrics[];
}

// ── Error response ───────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  status: number;
}
