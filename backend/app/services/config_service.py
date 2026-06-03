from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.models.app_configuration import AppConfiguration


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "configuration.yml"


def _load_yaml_config() -> dict[str, Any]:
    config_path = Path(os.getenv("DORA_CONFIG_PATH", str(_default_config_path())))
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_dict(current, value)
        else:
            merged[key] = value
    return merged


def _coerce_gitlab_project_paths_from_poc_shape(merged: dict[str, Any]) -> None:
    """Map POC-style ``gitlab.project_path`` (singular string) to ``project_paths`` when needed."""
    gl = merged.get("gitlab")
    if not isinstance(gl, dict):
        return
    paths = gl.get("project_paths")
    singular = gl.get("project_path")
    normalized_paths: list[str] = []
    if isinstance(paths, list):
        normalized_paths = [p.strip() for p in paths if isinstance(p, str) and p.strip()]
    if normalized_paths:
        gl["project_paths"] = normalized_paths
        gl.pop("project_path", None)
        return
    if isinstance(singular, str) and singular.strip():
        gl["project_paths"] = [singular.strip()]
    gl.pop("project_path", None)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_text(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _env_int(name: str) -> int | None:
    value = _env_text(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _env_bool(name: str) -> bool | None:
    value = _env_text(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _apply_env_overrides(config: ConfigurationSchema) -> ConfigurationSchema:
    if _env_text("DORA_ENVIRONMENT"):
        config.environment = _env_text("DORA_ENVIRONMENT") or config.environment

    if _env_text("DORA_BACKEND_HOST"):
        config.backend.host = _env_text("DORA_BACKEND_HOST") or config.backend.host
    _port = _env_int("DORA_BACKEND_PORT")
    if _port is not None:
        config.backend.port = _port
    if _env_text("DORA_BACKEND_LOG_LEVEL"):
        config.backend.log_level = _env_text("DORA_BACKEND_LOG_LEVEL") or config.backend.log_level
    _cron_hour = _env_int("DORA_SYNC_CRON_HOUR")
    if _cron_hour is not None:
        config.backend.sync_cron_hour = _cron_hour
    _cron_minute = _env_int("DORA_SYNC_CRON_MINUTE")
    if _cron_minute is not None:
        config.backend.sync_cron_minute = _cron_minute
    _lookback = _env_int("DORA_LOOKBACK_DAYS")
    if _lookback is not None:
        config.backend.lookback_days = _lookback

    if _env_text("GITLAB_BASE_URL"):
        config.gitlab.base_url = _env_text("GITLAB_BASE_URL") or config.gitlab.base_url
    gitlab_project_paths = _split_csv(_env_text("GITLAB_PROJECT_PATHS"))
    if gitlab_project_paths:
        config.gitlab.project_paths = gitlab_project_paths
    gitlab_target_branches = _split_csv(_env_text("GITLAB_TARGET_BRANCHES"))
    if gitlab_target_branches:
        config.gitlab.target_branches = gitlab_target_branches
    gitlab_extra_branches = _split_csv(_env_text("GITLAB_ADDITIONAL_MERGE_TARGET_BRANCHES"))
    if gitlab_extra_branches:
        config.gitlab.additional_merge_target_branches = gitlab_extra_branches
    gitlab_markers = [
        item.lower() for item in _split_csv(_env_text("GITLAB_NON_CUSTOMER_RELEASE_MARKERS"))
    ]
    if gitlab_markers:
        config.gitlab.non_customer_release_markers = gitlab_markers
    exclude_release_only = _env_bool("GITLAB_EXCLUDE_RELEASE_ONLY_MRS_FROM_LEAD_TIME")
    if exclude_release_only is not None:
        config.gitlab.exclude_release_only_mrs_from_lead_time = exclude_release_only
    release_title_markers = _split_csv(_env_text("GITLAB_RELEASE_MR_TITLE_MARKERS"))
    if release_title_markers:
        config.gitlab.release_mr_title_markers = [item.lower() for item in release_title_markers]
    release_source_markers = _split_csv(_env_text("GITLAB_RELEASE_MR_SOURCE_BRANCH_MARKERS"))
    if release_source_markers:
        config.gitlab.release_mr_source_branch_markers = [
            item.lower() for item in release_source_markers
        ]

    if _env_text("JIRA_BASE_URL"):
        config.jira.base_url = _env_text("JIRA_BASE_URL") or config.jira.base_url
    jira_excluded_projects = _split_csv(_env_text("JIRA_EXCLUDED_PROJECTS"))
    if jira_excluded_projects:
        config.jira.excluded_projects = jira_excluded_projects
    jira_ready_statuses = _split_csv(_env_text("JIRA_READY_FOR_QA_STATUS_NAMES"))
    if jira_ready_statuses:
        config.jira.ready_for_qa_status_names = jira_ready_statuses
    jira_indicator_ids = _split_csv(_env_text("JIRA_PRODUCTION_BUG_INDICATOR_CF_IDS"))
    if jira_indicator_ids:
        config.jira.production_bug_indicator_cf_ids = jira_indicator_ids
    jira_mttr_priorities = _split_csv(_env_text("JIRA_MTTR_ALPHA_PRIORITIES"))
    if jira_mttr_priorities:
        config.jira.mttr_alpha_priorities = jira_mttr_priorities

    notifications_webhook = _env_text("NOTIFICATIONS_WEBHOOK_URL")
    if notifications_webhook is not None:
        config.notifications.webhook_url = notifications_webhook

    if _env_text("HRWORKS_BASE_URL"):
        config.hrworks.base_url = _env_text("HRWORKS_BASE_URL") or config.hrworks.base_url
    hrworks_dow = _env_text("HRWORKS_SYNC_CRON_DAY_OF_WEEK")
    if hrworks_dow is not None:
        config.hrworks.sync_cron_day_of_week = hrworks_dow
    _hrworks_hour = _env_int("HRWORKS_SYNC_CRON_HOUR")
    if _hrworks_hour is not None:
        config.hrworks.sync_cron_hour = _hrworks_hour
    _hrworks_minute = _env_int("HRWORKS_SYNC_CRON_MINUTE")
    if _hrworks_minute is not None:
        config.hrworks.sync_cron_minute = _hrworks_minute
    hrworks_backfill = _env_text("HRWORKS_BACKFILL_START_DATE")
    if hrworks_backfill is not None:
        config.hrworks.backfill_start_date = hrworks_backfill
    _incremental_months = _env_int("HRWORKS_INCREMENTAL_MONTHS_BACK")
    if _incremental_months is not None:
        config.hrworks.incremental_months_back = _incremental_months
    _batch_size = _env_int("HRWORKS_PERSONS_BATCH_SIZE")
    if _batch_size is not None:
        config.hrworks.persons_batch_size = 1
    _roster_refresh = _env_int("HRWORKS_ROSTER_REFRESH_HOURS")
    if _roster_refresh is not None:
        config.hrworks.roster_refresh_hours = _roster_refresh

    return config


def _normalize_fernet_key(raw_key: str) -> bytes:
    candidate = raw_key.strip().encode("utf-8")
    try:
        Fernet(candidate)
        return candidate
    except Exception:
        digest = hashlib.sha256(candidate).digest()
        return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet | None:
    raw_key = _env_text("CONFIG_ENCRYPTION_KEY")
    if raw_key is None:
        return None
    return Fernet(_normalize_fernet_key(raw_key))


def encrypt_secret(value: str) -> bytes:
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("CONFIG_ENCRYPTION_KEY is required to encrypt secrets")
    return fernet.encrypt(value.encode("utf-8"))


def decrypt_secret(value: bytes) -> str:
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("CONFIG_ENCRYPTION_KEY is required to decrypt secrets")
    try:
        decrypted = fernet.decrypt(value)
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt stored configuration secret") from exc
    return decrypted.decode("utf-8")


def _to_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


@dataclass(slots=True)
class RuntimeConfig:
    settings: ConfigurationSchema
    gitlab_token: str
    jira_token: str
    jira_user_email: str
    hrworks_access_key: str
    hrworks_secret_access_key: str


def _resolve_jira_user_email(app_config: AppConfiguration | None) -> str:
    """Jira Cloud API tokens require Basic auth (email + token); email from env or admin UI."""
    env_email = _env_text("JIRA_USER_EMAIL")
    if env_email:
        return env_email
    if app_config is not None and isinstance(app_config.settings_json, dict):
        jira = app_config.settings_json.get("jira")
        if isinstance(jira, dict):
            stored = jira.get("api_user_email")
            if isinstance(stored, str) and stored.strip():
                return stored.strip()
    return ""


def _resolve_db_tokens(app_config: AppConfiguration | None) -> tuple[str | None, str | None]:
    if app_config is None:
        return None, None
    gitlab_token: str | None = None
    jira_token: str | None = None
    if app_config.gitlab_token_enc:
        gitlab_token = decrypt_secret(app_config.gitlab_token_enc)
    if app_config.jira_token_enc:
        jira_token = decrypt_secret(app_config.jira_token_enc)
    return gitlab_token, jira_token


def _apply_db_overrides(
    config_payload: dict[str, Any],
    app_config: AppConfiguration | None,
) -> dict[str, Any]:
    if app_config is None or not isinstance(app_config.settings_json, dict):
        return config_payload
    settings = dict(app_config.settings_json)
    # Backward-compatible flat key accepted by earlier stories.
    if "gitlab_project_paths" in settings and "gitlab" not in settings:
        settings["gitlab"] = {
            "project_paths": _to_string_list(settings.get("gitlab_project_paths"))
        }
    merged = _merge_dict(config_payload, settings)
    # Admin UI may persist project_paths: [] meaning "not set"; do not wipe YAML/env defaults.
    gl = merged.get("gitlab")
    if isinstance(gl, dict):
        pp = gl.get("project_paths")
        if isinstance(pp, list) and len(pp) == 0:
            base_gl = config_payload.get("gitlab")
            if isinstance(base_gl, dict):
                base_pp = base_gl.get("project_paths")
                if isinstance(base_pp, list) and base_pp:
                    gl["project_paths"] = [
                        str(p).strip() for p in base_pp if isinstance(p, str) and str(p).strip()
                    ]
                else:
                    gl.pop("project_paths", None)
            else:
                gl.pop("project_paths", None)
    return merged


def load_runtime_config(db: Session | None = None) -> RuntimeConfig:
    defaults = ConfigurationSchema().model_dump()
    yaml_payload = _load_yaml_config()
    merged = _merge_dict(defaults, yaml_payload)

    app_config: AppConfiguration | None = None
    if db is not None:
        app_config = db.get(AppConfiguration, 1)
        merged = _apply_db_overrides(merged, app_config)

    _coerce_gitlab_project_paths_from_poc_shape(merged)
    config = _apply_env_overrides(ConfigurationSchema.model_validate(merged))

    env_gitlab_token = _env_text("GITLAB_TOKEN") or _env_text("GITLAB_API_TOKEN")
    env_jira_token = _env_text("JIRA_TOKEN") or _env_text("JIRA_API_TOKEN")
    db_gitlab_token, db_jira_token = _resolve_db_tokens(app_config)

    return RuntimeConfig(
        settings=config,
        gitlab_token=env_gitlab_token or db_gitlab_token or "",
        jira_token=env_jira_token or db_jira_token or "",
        jira_user_email=_resolve_jira_user_email(app_config),
        hrworks_access_key=_env_text("ACCESSKEY") or _env_text("HRWORKS_ACCESS_KEY") or "",
        hrworks_secret_access_key=(
            _env_text("SECRETACCESSKEY")
            or _env_text("SECRET_ACCESSKEY")
            or _env_text("HRWORKS_SECRET_ACCESS_KEY")
            or ""
        ),
    )


def mask_secret_hint(secret_value: str | None) -> str | None:
    if not secret_value:
        return None
    trimmed = secret_value.strip()
    if not trimmed:
        return None
    if len(trimmed) <= 8:
        return "*" * len(trimmed)
    return f"{trimmed[:5]}****{trimmed[-4:]}"
