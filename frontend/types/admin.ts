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

export interface AdminConfigResponse {
  environment: string;
  gitlab_url: string;
  gitlab_token_hint: string | null;
  gitlab_project_paths: string[];
  target_branches: string[];
  non_customer_release_markers: string[];
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
}

export interface AdminConfigPatch {
  environment?: string;
  gitlab_url?: string;
  gitlab_token?: string;
  gitlab_project_paths?: string[];
  target_branches?: string[];
  non_customer_release_markers?: string[];
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
}
