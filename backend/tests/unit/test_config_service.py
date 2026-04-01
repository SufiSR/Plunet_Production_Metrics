from __future__ import annotations

from dataclasses import dataclass

from app.config_schema import ConfigurationSchema
from app.models.app_configuration import AppConfiguration
from app.services import config_service


@dataclass
class _FakeSession:
    app_config: AppConfiguration | None

    def get(self, _model: object, _pk: int) -> AppConfiguration | None:
        return self.app_config


def test_runtime_config_merge_order_defaults_yaml_db_env(monkeypatch) -> None:
    monkeypatch.setattr(
        config_service,
        "_load_yaml_config",
        lambda: {
            "gitlab": {"base_url": "https://yaml.example", "project_paths": ["yaml/path"]},
            "jira": {"ready_for_qa_status_names": ["Ready for test"]},
        },
    )
    monkeypatch.setenv("GITLAB_BASE_URL", "https://env.example")
    monkeypatch.setenv("JIRA_READY_FOR_QA_STATUS_NAMES", "Ready for QA,Ready for test")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")

    app_config = AppConfiguration(
        id=1,
        settings_json={
            "gitlab": {"base_url": "https://db.example", "project_paths": ["db/path"]},
            "jira": {"ready_for_qa_status_names": ["DB QA"]},
        },
    )
    runtime = config_service.load_runtime_config(db=_FakeSession(app_config))
    assert runtime.settings.gitlab.base_url == "https://env.example"
    assert runtime.settings.gitlab.project_paths == ["db/path"]
    assert runtime.settings.jira.ready_for_qa_status_names == ["Ready for QA", "Ready for test"]


def test_runtime_tokens_resolve_env_then_db_encrypted(monkeypatch) -> None:
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")

    gitlab_enc = config_service.encrypt_secret("gitlab-db-token")
    jira_enc = config_service.encrypt_secret("jira-db-token")
    app_config = AppConfiguration(
        id=1,
        settings_json={},
        gitlab_token_enc=gitlab_enc,
        jira_token_enc=jira_enc,
    )
    runtime_from_db = config_service.load_runtime_config(db=_FakeSession(app_config))
    assert runtime_from_db.gitlab_token == "gitlab-db-token"
    assert runtime_from_db.jira_token == "jira-db-token"

    monkeypatch.setenv("GITLAB_TOKEN", "gitlab-env-token")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-env-token")
    runtime_from_env = config_service.load_runtime_config(db=_FakeSession(app_config))
    assert runtime_from_env.gitlab_token == "gitlab-env-token"
    assert runtime_from_env.jira_token == "jira-env-token"


def test_mask_secret_hint_masks_value() -> None:
    assert config_service.mask_secret_hint("glpat-1234567890") == "glpat****7890"


def test_env_sync_cron_hour_zero_not_falsy_fallback(monkeypatch) -> None:
    monkeypatch.setenv("DORA_SYNC_CRON_HOUR", "0")
    cfg = config_service._apply_env_overrides(ConfigurationSchema())
    assert cfg.backend.sync_cron_hour == 0


def test_env_backend_port_zero_not_falsy_fallback(monkeypatch) -> None:
    monkeypatch.setenv("DORA_BACKEND_PORT", "0")
    cfg = config_service._apply_env_overrides(ConfigurationSchema())
    assert cfg.backend.port == 0
