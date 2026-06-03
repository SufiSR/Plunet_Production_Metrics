export type FeatureHoursRowType = "feature" | "other_bug" | "other_feature" | "other_misc";

export interface FeatureHoursMatrixRow {
  row_id: string;
  label: string;
  row_type: FeatureHoursRowType;
  root_key?: string | null;
  feature_name?: string | null;
  start_date?: string | null;
  target_end_date?: string | null;
  delivery_progress?: string | null;
  team_name?: string | null;
  hours_by_period: Record<string, number>;
  total_hours: number;
}

export interface FeatureHoursMatrixResponse {
  periods: string[];
  rows: FeatureHoursMatrixRow[];
  jira_base_url: string;
  role_filter: string | null;
  team_filter: string | null;
  available_roles: string[];
  available_teams: string[];
}

export interface FeatureHoursDrilldownIssue {
  issue_key: string;
  issue_url: string;
  summary: string | null;
  issue_type_name: string | null;
  depth: number;
  hours_by_period: Record<string, number>;
  total_hours: number;
  multi_feature: boolean;
  other_feature_keys: string[];
}

export interface FeatureHoursDrilldownSection {
  epic_key: string | null;
  epic_url: string | null;
  epic_summary: string | null;
  total_hours: number;
  issues: FeatureHoursDrilldownIssue[];
}

export interface FeatureHoursDrilldownResponse {
  row_id: string;
  row_label: string;
  row_type: FeatureHoursRowType;
  feature_root_key: string;
  feature_summary: string | null;
  row_url: string | null;
  periods: string[];
  sections: FeatureHoursDrilldownSection[];
  role_filter: string | null;
  team_filter: string | null;
}

export interface FeatureFamilyHoursMatrixRow {
  row_id: string;
  family_id: number;
  label: string;
  feature_count: number;
  start_date: string | null;
  target_end_date: string | null;
  delivery_progress: string | null;
  team_names: string[];
  hours_by_period: Record<string, number>;
  total_hours: number;
}

export interface FeatureFamilyHoursMatrixResponse {
  periods: string[];
  rows: FeatureFamilyHoursMatrixRow[];
  jira_base_url: string;
  role_filter: string | null;
  team_filter: string | null;
  available_roles: string[];
  available_teams: string[];
}

export interface FeatureFamilyDrilldownFeature {
  root_key: string;
  feature_name: string;
  row_url: string | null;
  start_date: string | null;
  target_end_date: string | null;
  delivery_progress: string | null;
  team_name: string | null;
  hours_by_period: Record<string, number>;
  total_hours: number;
  sections: FeatureHoursDrilldownSection[];
}

export interface FeatureFamilyHoursDrilldownResponse {
  row_id: string;
  family_id: number;
  row_label: string;
  periods: string[];
  features: FeatureFamilyDrilldownFeature[];
  role_filter: string | null;
  team_filter: string | null;
}

export interface DataQualityCheck {
  check_id: string;
  label: string;
  count: number;
  ignored_count?: number;
  affected_hours?: number | null;
  severity: "low" | "medium" | "high";
}

export interface DataQualityUserDrilldownRow {
  user_id: number | null;
  account_id: string;
  display_name: string | null;
  email_address: string | null;
  jira_active: boolean | null;
  reporting_excluded: boolean;
  role_name: string | null;
  team_name: string | null;
  worklog_count: number;
  total_hours: number;
  first_worklog_at: string | null;
  last_worklog_at: string | null;
  ignored: boolean;
  ignore_reason: string | null;
  can_ignore: boolean;
}

export interface DataQualityUserDrilldownResponse {
  check_id: string;
  label: string;
  active_count: number;
  ignored_count: number;
  users: DataQualityUserDrilldownRow[];
}

export interface DataQualityResponse {
  filters: Record<string, unknown>;
  summary: Record<string, unknown>;
  data_quality: {
    warnings: DataQualityCheck[];
    unclassified_hours?: number;
    missing_role_assignments?: number;
  };
}

export interface AnalyticsReportResponse {
  filters: Record<string, unknown>;
  summary: Record<string, unknown>;
  series: Record<string, unknown>[];
  table: Record<string, unknown>[];
  drilldowns?: Record<string, string | null>;
  data_quality?: DataQualityResponse["data_quality"];
}

export interface FeatureInvestmentAuditRow {
  rank: number;
  family_identifier: string;
  family_name: string;
  feature_identifier: string;
  feature_name: string;
  team?: string | null;
  booked_hours: number;
  calculated_hours: number;
  overhead_hours: number;
  monthly: Record<string, { booked: number; calculated: number; overhead: number }>;
}

export interface FeatureInvestmentAuditIssueRow {
  issue_identifier: string;
  issue_name?: string | null;
  issue_type?: string | null;
  family_name: string;
  feature_identifier: string;
  feature_name: string;
  booked_hours: number;
  calculated_hours: number;
  overhead_hours: number;
}

export interface FeatureInvestmentAuditWorklogRow {
  period: string;
  person: string;
  role?: string | null;
  issue_key: string;
  worklog_id?: string | null;
  worklog_date?: string | null;
  source: string;
  booked_hours: number;
  calculated_hours: number;
  overhead_hours: number;
  scale_factor: number;
  hrworks_planned_hours: number;
}

export interface StatusWaitingDataPoint {
  issue_id: number;
  issue_key?: string;
  issue_type: string;
  status: string;
  priority: string;
  days: number;
}

export interface StatusWaitingPriorityRow {
  status: string;
  unique_issue_count: number;
  average_days_all_priorities: number | null;
  median_by_priority: Record<string, number | null>;
  average_by_priority: Record<string, number | null>;
}

export interface StatusWaitingWorkflowSection {
  catalog_key: string;
  label: string;
  workflow_id?: number | null;
  workflow_name?: string | null;
  issue_type_options?: string[];
  status_order?: string[];
  data_points?: StatusWaitingDataPoint[];
  priority_columns?: string[];
  projects?: { key: string; name?: string | null }[];
  rows: StatusWaitingPriorityRow[];
}

export interface ReportQueryParams {
  from?: string;
  to?: string;
  team?: string;
  projectKey?: string;
  projectKeys?: string[];
  issueType?: string;
  workflow?: string;
  includeOtherWorkflows?: boolean;
  role?: string;
  familyId?: string;
  featureKey?: string;
  issueKey?: string;
  customer?: string;
  mode?: string;
  minHours?: number;
  minScore?: number;
  minAgeDays?: number;
  limit?: number;
}
