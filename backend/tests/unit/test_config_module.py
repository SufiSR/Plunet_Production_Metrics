from __future__ import annotations

import app.config as app_config
import app.services.config_service as config_service
from app.config_schema import ConfigurationSchema


def test_load_configuration_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        app_config,
        "load_runtime_config",
        lambda db=None: config_service.RuntimeConfig(
            settings=ConfigurationSchema(environment="unit"),
            gitlab_token="",
            jira_token="",
            jira_user_email="",
        ),
    )
    cfg = app_config.load_configuration()
    assert cfg.environment == "unit"
