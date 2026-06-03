from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from app.models.app_configuration import AppConfiguration
from app.scheduler import reschedule_all_schedulers
from app.schemas.admin_config import AdminConfigPatch, AdminConfigResponse
from app.services import config_service
from app.services.jira_user_assignments import list_worklog_assignments


def _env_text(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _nested_dict(root: dict[str, Any], key: str) -> dict[str, Any]:
    cur = root.get(key)
    if isinstance(cur, dict):
        return dict(cur)
    return {}


def _jira_username_for_display(settings_json: dict[str, Any]) -> str:
    jira = settings_json.get("jira")
    if isinstance(jira, dict):
        stored = jira.get("api_user_email")
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
    return _env_text("JIRA_USER_EMAIL") or ""


def build_admin_config_response(db: Session) -> AdminConfigResponse:
    runtime = config_service.load_runtime_config(db=db)
    cfg = runtime.settings
    app_row = db.get(AppConfiguration, 1)
    settings_json: dict[str, Any] = (
        dict(app_row.settings_json) if app_row and isinstance(app_row.settings_json, dict) else {}
    )
    return AdminConfigResponse(
        environment=cfg.environment,
        gitlab_url=cfg.gitlab.base_url,
        gitlab_token_hint=config_service.mask_secret_hint(runtime.gitlab_token or None),
        gitlab_project_paths=list(cfg.gitlab.project_paths),
        target_branches=list(cfg.gitlab.target_branches),
        additional_merge_target_branches=list(cfg.gitlab.additional_merge_target_branches),
        non_customer_release_markers=list(cfg.gitlab.non_customer_release_markers),
        exclude_release_only_mrs_from_lead_time=cfg.gitlab.exclude_release_only_mrs_from_lead_time,
        release_mr_title_markers=list(cfg.gitlab.release_mr_title_markers),
        release_mr_source_branch_markers=list(cfg.gitlab.release_mr_source_branch_markers),
        jira_url=cfg.jira.base_url,
        jira_username=_jira_username_for_display(settings_json),
        jira_token_hint=config_service.mask_secret_hint(runtime.jira_token or None),
        excluded_projects=list(cfg.jira.excluded_projects),
        ready_for_qa_status_names=list(cfg.jira.ready_for_qa_status_names),
        production_bug_indicator_cf_ids=list(cfg.jira.production_bug_indicator_cf_ids),
        mttr_alpha_priorities=list(cfg.jira.mttr_alpha_priorities),
        sync_cron_hour=cfg.backend.sync_cron_hour,
        sync_cron_minute=cfg.backend.sync_cron_minute,
        lookback_days=cfg.backend.lookback_days,
        hrworks_sync_cron_day_of_week=cfg.hrworks.sync_cron_day_of_week,
        hrworks_sync_cron_hour=cfg.hrworks.sync_cron_hour,
        hrworks_sync_cron_minute=cfg.hrworks.sync_cron_minute,
        jira_analytics_sync_cron_hour=cfg.jira_analytics.sync_cron_hour,
        jira_analytics_sync_cron_minute=cfg.jira_analytics.sync_cron_minute,
        jira_analytics_scheduled_lookback_days=cfg.jira_analytics.scheduled_lookback_days,
        notifications_webhook_url=cfg.notifications.webhook_url,
        jira_worklog_user_assignments=list_worklog_assignments(db),
    )


def _get_or_create_app_configuration_row(db: Session) -> AppConfiguration:
    row = db.get(AppConfiguration, 1)
    if row is None:
        row = AppConfiguration(id=1, settings_json={})
        db.add(row)
        db.flush()
    elif not isinstance(row.settings_json, dict):
        row.settings_json = {}
    return row


def patch_admin_configuration(db: Session, patch: AdminConfigPatch) -> AdminConfigResponse:
    row = _get_or_create_app_configuration_row(db)
    if isinstance(row.settings_json, dict):
        settings_json = dict(row.settings_json)
    else:
        settings_json = {}

    data = patch.model_dump(exclude_unset=True)

    if "gitlab_token" in data:
        token = data.pop("gitlab_token")
        if isinstance(token, str) and token.strip():
            row.gitlab_token_enc = config_service.encrypt_secret(token.strip())

    if "jira_token" in data:
        token = data.pop("jira_token")
        if isinstance(token, str) and token.strip():
            row.jira_token_enc = config_service.encrypt_secret(token.strip())

    gl = _nested_dict(settings_json, "gitlab")
    jr = _nested_dict(settings_json, "jira")
    bk = _nested_dict(settings_json, "backend")
    hw = _nested_dict(settings_json, "hrworks")
    ja = _nested_dict(settings_json, "jira_analytics")
    nt = _nested_dict(settings_json, "notifications")

    if "environment" in data and data["environment"] is not None:
        settings_json["environment"] = data.pop("environment")
    if "gitlab_url" in data and data["gitlab_url"] is not None:
        gl["base_url"] = data.pop("gitlab_url")
    if "gitlab_project_paths" in data:
        gl["project_paths"] = data.pop("gitlab_project_paths")
    if "target_branches" in data:
        gl["target_branches"] = data.pop("target_branches")
    if "additional_merge_target_branches" in data:
        gl["additional_merge_target_branches"] = data.pop("additional_merge_target_branches")
    if "non_customer_release_markers" in data:
        gl["non_customer_release_markers"] = data.pop("non_customer_release_markers")
    if "exclude_release_only_mrs_from_lead_time" in data:
        gl["exclude_release_only_mrs_from_lead_time"] = data.pop(
            "exclude_release_only_mrs_from_lead_time"
        )
    if "release_mr_title_markers" in data:
        gl["release_mr_title_markers"] = data.pop("release_mr_title_markers")
    if "release_mr_source_branch_markers" in data:
        gl["release_mr_source_branch_markers"] = data.pop("release_mr_source_branch_markers")
    if "jira_url" in data and data["jira_url"] is not None:
        jr["base_url"] = data.pop("jira_url")
    if "jira_username" in data:
        username = data.pop("jira_username")
        if username is not None:
            jr["api_user_email"] = username
    if "excluded_projects" in data:
        jr["excluded_projects"] = data.pop("excluded_projects")
    if "ready_for_qa_status_names" in data:
        jr["ready_for_qa_status_names"] = data.pop("ready_for_qa_status_names")
    if "production_bug_indicator_cf_ids" in data:
        jr["production_bug_indicator_cf_ids"] = data.pop("production_bug_indicator_cf_ids")
    if "mttr_alpha_priorities" in data:
        jr["mttr_alpha_priorities"] = data.pop("mttr_alpha_priorities")
    if "jira_worklog_user_assignments" in data:
        data.pop("jira_worklog_user_assignments")
    if "sync_cron_hour" in data:
        bk["sync_cron_hour"] = data.pop("sync_cron_hour")
    if "sync_cron_minute" in data:
        bk["sync_cron_minute"] = data.pop("sync_cron_minute")
    if "lookback_days" in data:
        bk["lookback_days"] = data.pop("lookback_days")
    if "hrworks_sync_cron_day_of_week" in data and data["hrworks_sync_cron_day_of_week"] is not None:
        hw["sync_cron_day_of_week"] = data.pop("hrworks_sync_cron_day_of_week").strip().lower()
    if "hrworks_sync_cron_hour" in data:
        hw["sync_cron_hour"] = data.pop("hrworks_sync_cron_hour")
    if "hrworks_sync_cron_minute" in data:
        hw["sync_cron_minute"] = data.pop("hrworks_sync_cron_minute")
    if "jira_analytics_sync_cron_hour" in data:
        ja["sync_cron_hour"] = data.pop("jira_analytics_sync_cron_hour")
    if "jira_analytics_sync_cron_minute" in data:
        ja["sync_cron_minute"] = data.pop("jira_analytics_sync_cron_minute")
    if "jira_analytics_scheduled_lookback_days" in data:
        ja["scheduled_lookback_days"] = data.pop("jira_analytics_scheduled_lookback_days")
    if "notifications_webhook_url" in data:
        nt["webhook_url"] = data.pop("notifications_webhook_url")

    settings_json["gitlab"] = gl
    settings_json["jira"] = jr
    settings_json["backend"] = bk
    settings_json["hrworks"] = hw
    settings_json["jira_analytics"] = ja
    settings_json["notifications"] = nt

    row.settings_json = settings_json
    db.commit()

    runtime = config_service.load_runtime_config(db=db)
    reschedule_all_schedulers(runtime.settings)
    return build_admin_config_response(db)
