from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.services.admin_config_service as acs
import app.services.config_service as config_service
from app.models.app_configuration import AppConfiguration
from app.models.base import Base
from pydantic import ValidationError

from app.schemas.admin_config import AdminConfigPatch


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_nested_dict() -> None:
    assert acs._nested_dict({}, "gitlab") == {}
    assert acs._nested_dict({"gitlab": {"a": 1}}, "gitlab") == {"a": 1}
    assert acs._nested_dict({"gitlab": "x"}, "gitlab") == {}


def test_jira_username_for_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
    assert acs._jira_username_for_display({}) == ""
    email = acs._jira_username_for_display({"jira": {"api_user_email": "  me@x.test  "}})
    assert email == "me@x.test"
    monkeypatch.setenv("JIRA_USER_EMAIL", "  env@x.test  ")
    assert acs._jira_username_for_display({"jira": {}}) == "env@x.test"


def test_get_or_create_app_configuration_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    with _session() as db:
        row = acs._get_or_create_app_configuration_row(db)
        assert row.id == 1
        assert row.settings_json == {}
        same = acs._get_or_create_app_configuration_row(db)
        assert same.id == 1


def test_build_admin_config_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.delenv("GITLAB_BASE_URL", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    with _session() as db:
        db.add(
            AppConfiguration(
                id=1,
                settings_json={
                    "gitlab": {"base_url": "https://db-gl.example", "project_paths": ["a/b"]},
                    "jira": {"api_user_email": "db@user.test"},
                },
            )
        )
        db.commit()
        resp = acs.build_admin_config_response(db)
    assert resp.gitlab_url == "https://db-gl.example"
    assert resp.jira_username == "db@user.test"
    assert resp.jira_worklog_user_assignments == []
    assert resp.gitlab_project_paths == ["a/b"]
    assert resp.exclude_release_only_mrs_from_lead_time is True
    assert " release" in resp.release_mr_title_markers
    assert "release" in resp.release_mr_source_branch_markers


def test_patch_admin_configuration_updates_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.setattr(acs, "reschedule_all_schedulers", lambda _cfg: None)
    monkeypatch.delenv("GITLAB_BASE_URL", raising=False)
    with _session() as db:
        db.add(AppConfiguration(id=1, settings_json={}))
        db.commit()
        acs.patch_admin_configuration(
            db,
            AdminConfigPatch(
                gitlab_url="https://patched.example",
                jira_username="patch@user.test",
                sync_cron_hour=3,
                notifications_webhook_url="https://hooks.example/x",
                exclude_release_only_mrs_from_lead_time=False,
                release_mr_title_markers=[" release", "gui "],
                release_mr_source_branch_markers=["release", "hotfix-release"],
            ),
        )
        row = db.get(AppConfiguration, 1)
        assert row is not None
        assert row.settings_json["gitlab"]["base_url"] == "https://patched.example"
        assert row.settings_json["jira"]["api_user_email"] == "patch@user.test"
        assert row.settings_json["backend"]["sync_cron_hour"] == 3
        assert row.settings_json["notifications"]["webhook_url"] == "https://hooks.example/x"
        assert row.settings_json["gitlab"]["exclude_release_only_mrs_from_lead_time"] is False
        assert row.settings_json["gitlab"]["release_mr_title_markers"] == [" release", "gui "]
        assert row.settings_json["gitlab"]["release_mr_source_branch_markers"] == [
            "release",
            "hotfix-release",
        ]


def test_patch_admin_configuration_ignores_legacy_worklog_assignments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.setattr(acs, "reschedule_all_schedulers", lambda _cfg: None)
    monkeypatch.delenv("GITLAB_BASE_URL", raising=False)
    with _session() as db:
        db.add(AppConfiguration(id=1, settings_json={}))
        db.commit()
        acs.patch_admin_configuration(
            db,
            AdminConfigPatch(
                jira_worklog_user_assignments=[
                    {"jira_account_id": "acc-1", "role": "dev", "team": "Core"},
                ],
            ),
        )
        row = db.get(AppConfiguration, 1)
        assert row is not None
        assert "jira_worklog_user_assignments" not in row.settings_json.get("jira", {})


def test_admin_config_patch_rejects_duplicate_assignment_account_ids() -> None:
    with pytest.raises(ValidationError):
        AdminConfigPatch(
            jira_worklog_user_assignments=[
                {"jira_account_id": "dup", "role": "dev", "team": "A"},
                {"jira_account_id": "dup", "role": "qa", "team": "B"},
            ],
        )


def test_patch_admin_configuration_encrypts_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.setattr(acs, "reschedule_all_schedulers", lambda _cfg: None)
    with _session() as db:
        db.add(AppConfiguration(id=1, settings_json={}))
        db.commit()
        acs.patch_admin_configuration(
            db,
            AdminConfigPatch(gitlab_token="  gl-secret  ", jira_token="  ji-secret  "),
        )
        row = db.get(AppConfiguration, 1)
        assert row is not None
        assert row.gitlab_token_enc is not None
        assert row.jira_token_enc is not None
        assert config_service.decrypt_secret(row.gitlab_token_enc) == "gl-secret"
        assert config_service.decrypt_secret(row.jira_token_enc) == "ji-secret"


def test_patch_admin_configuration_ignores_blank_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.setattr(acs, "reschedule_all_schedulers", lambda _cfg: None)
    with _session() as db:
        db.add(AppConfiguration(id=1, settings_json={}))
        db.commit()
        acs.patch_admin_configuration(
            db,
            AdminConfigPatch(gitlab_token="   ", jira_token=""),
        )
        row = db.get(AppConfiguration, 1)
        assert row is not None
        assert row.gitlab_token_enc is None
        assert row.jira_token_enc is None


def test_patch_admin_configuration_replaces_non_dict_settings_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setattr(config_service, "_load_yaml_config", lambda: {})
    monkeypatch.setattr(acs, "reschedule_all_schedulers", lambda _cfg: None)
    with _session() as db:
        db.add(AppConfiguration(id=1, settings_json=[]))  # type: ignore[arg-type]
        db.commit()
        acs.patch_admin_configuration(db, AdminConfigPatch(environment="staging"))
        row = db.get(AppConfiguration, 1)
        assert row is not None
        assert isinstance(row.settings_json, dict)
        assert row.settings_json.get("environment") == "staging"
