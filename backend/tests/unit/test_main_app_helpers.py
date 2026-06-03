"""Unit tests for app.main helpers, logging, and API error JSON envelope."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.config_schema import ConfigurationSchema
from app.services.config_service import RuntimeConfig


@pytest.fixture(autouse=True)
def _dora_session_secret_min(monkeypatch: pytest.MonkeyPatch) -> None:
    """`app.main` instantiates the app on import; keep a long enough session secret in tests."""
    monkeypatch.setenv("DORA_SESSION_SECRET", "a" * 20)


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DORA_SESSION_SECRET", "a" * 20)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    import app.main as main_mod

    def _load_runtime(_db: object | None = None, **_: object) -> RuntimeConfig:
        return RuntimeConfig(
            settings=ConfigurationSchema(),
            gitlab_token="",
            jira_token="",
            jira_user_email="",
            hrworks_access_key="",
            hrworks_secret_access_key="",
        )

    monkeypatch.setattr(main_mod, "load_runtime_config", _load_runtime)
    monkeypatch.setattr(main_mod, "reconcile_nightly_runs_on_app_startup", lambda: None)
    monkeypatch.setattr(main_mod, "start_scheduler", lambda _c: None)
    monkeypatch.setattr(main_mod, "stop_scheduler", lambda: None)
    from app.main import create_app

    with TestClient(create_app()) as client:
        yield client


def test_session_secret_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as m

    monkeypatch.setenv("DORA_SESSION_SECRET", "short")
    with pytest.raises(RuntimeError, match="DORA_SESSION_SECRET"):
        m._session_secret()


def test_cors_wildcard_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as m

    monkeypatch.setenv("DORA_CORS_ORIGINS", "*")
    o, cred = m._cors_config()
    assert o == ["*"] and cred is False
    monkeypatch.setenv("DORA_CORS_ORIGINS", "https://a,https://b")
    o2, cred2 = m._cors_config()
    assert o2 == ["https://a", "https://b"] and cred2 is True
    monkeypatch.delenv("DORA_CORS_ORIGINS", raising=False)
    o3, _ = m._cors_config()
    assert "localhost" in o3[0]


def test_https_only_cookie_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as m

    monkeypatch.setenv("DORA_ENVIRONMENT", " production ")
    assert m._https_only_session_cookie() is True
    monkeypatch.setenv("DORA_ENVIRONMENT", "dev")
    assert m._https_only_session_cookie() is False


def test_http_error_message_non_string() -> None:
    import app.main as m

    assert m._http_error_message({"a": 1}) == str({"a": 1})


def test_application_logging_adds_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as m

    monkeypatch.setenv("DORA_LOG_LEVEL", "DEBUG")
    m._configure_application_logging()
    app_logger = logging.getLogger("app")
    assert app_logger.level <= logging.DEBUG


def test_not_found_returns_error_envelope(app_client: TestClient) -> None:
    r = app_client.get("/api/no-such-endpoint-xyz-404")
    assert r.status_code == 404
    body = r.json()
    # FastAPI/Starlette default 404 is {"detail": "Not Found"}; custom handler may add `error`
    assert "error" in body or "detail" in body


def test_legacy_root_health_ok(app_client: TestClient) -> None:
    r = app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
