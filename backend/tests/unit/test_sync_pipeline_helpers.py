from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config_schema import ConfigurationSchema
from app.models import Base
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.models.sync_log import SyncLog
from app.services import sync_pipeline as sp
from app.services.config_service import RuntimeConfig
from app.services.webhook_service import send_webhook_notification


def _session_maker() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)


def test_normalize_version_key() -> None:
    assert sp._normalize_version_key("") == set()
    assert sp._normalize_version_key("  ") == set()
    assert "1.0.0" in sp._normalize_version_key("v1.0.0")
    assert "v1.0.0" in sp._normalize_version_key("1.0.0")


def test_lookback_start_utc() -> None:
    out = sp._lookback_start_utc(7)
    assert out.tzinfo == timezone.utc
    assert out.date() <= datetime.now(timezone.utc).date()


def test_gitlab_and_jira_table_counts_empty() -> None:
    maker = _session_maker()
    with maker() as db:
        counts_gl = sp._gitlab_table_counts(db)
        counts_j = sp._jira_table_counts(db)
    assert counts_gl["repositories"] == 0
    assert counts_j["bugs"] == 0


def test_gitlab_table_counts_with_repo() -> None:
    maker = _session_maker()
    with maker() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=9,
                name="r",
                path="g/r",
                default_branch="main",
                active=True,
            )
        )
        db.commit()
        counts = sp._gitlab_table_counts(db)
    assert counts["repositories"] == 1


def test_map_bugs_to_releases_links_matching_version() -> None:
    maker = _session_maker()
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with maker() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=9,
                name="r",
                path="g/r",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add(
            Release(
                id=1,
                repository_id=1,
                tag_name="v10.1.0",
                customer_release=True,
                commit_sha="a" * 40,
                committed_at=t,
            )
        )
        db.add(
            ProductionBug(
                id=1,
                jira_key="BUG-1",
                healthy=True,
                jira_created_at_valid=True,
                affects_versions=["10.1.0"],
                fix_versions=[],
                priority="Critical",
                created_at=t,
            )
        )
        db.commit()
        n = sp._map_bugs_to_releases(db)
    assert n >= 1


def test_finish_nightly_sync_log_when_row_missing() -> None:
    maker = _session_maker()

    def session_factory() -> Session:
        return maker()

    sp._finish_nightly_sync_log(
        session_factory,
        log_id=999_999,
        status="failed",
        records_processed=0,
        error_message=None,
    )


def test_notify_webhook_no_url() -> None:
    delivered = send_webhook_notification(None, {"status": "failed", "records_processed": 0})
    assert delivered is False


def test_run_nightly_sync_failed_without_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    maker = _session_maker()

    def session_factory() -> Session:
        return maker()

    monkeypatch.setattr(sp, "_resolve_orphaned_sync_logs", lambda _sf: None)
    monkeypatch.setattr(
        sp,
        "load_runtime_config",
        lambda db=None: RuntimeConfig(
            settings=ConfigurationSchema(),
            gitlab_token="",
            jira_token="",
            jira_user_email="",
        ),
    )
    monkeypatch.setattr(sp, "_create_nightly_sync_log", lambda _sf, **_: 1)
    monkeypatch.setattr(
        sp,
        "_read_nightly_log_started_at",
        lambda _db, _lid: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    finishes: list[dict[str, object]] = []

    def capture_finish(sf, **kwargs):  # type: ignore[no-untyped-def]
        finishes.append(kwargs)
        return 0

    monkeypatch.setattr(sp, "_finish_nightly_sync_log", capture_finish)
    monkeypatch.setattr(sp, "send_webhook_notification", lambda *_a, **_k: True)

    payload = sp.run_nightly_sync(config=ConfigurationSchema(), session_factory=session_factory)
    assert payload["status"] == "failed"
    assert finishes[-1]["status"] == "failed"
    details = finishes[-1]["details_json"]
    assert isinstance(details, dict)
    assert details["collectors"]["gitlab"]["status"] == "FAILED"


def test_run_nightly_sync_partial_branch_logs_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """One collector succeeds and one is skipped -> partial_failure and mapping skip log."""
    maker = _session_maker()

    def session_factory() -> Session:
        return maker()

    info_messages: list[str] = []
    real_info = sp.logger.info

    def capture_info(msg: object, *args: object, **kwargs: object) -> None:
        text = str(msg) % args if args else str(msg)
        info_messages.append(text)
        real_info(msg, *args, **kwargs)

    monkeypatch.setattr(sp.logger, "info", capture_info)
    monkeypatch.setattr(sp, "_resolve_orphaned_sync_logs", lambda _sf: None)
    monkeypatch.setattr(
        sp,
        "load_runtime_config",
        lambda db=None: RuntimeConfig(
            settings=ConfigurationSchema(),
            gitlab_token="tok",
            jira_token="",
            jira_user_email="",
        ),
    )
    monkeypatch.setattr(sp, "_create_nightly_sync_log", lambda _sf, **_: 1)
    monkeypatch.setattr(
        sp,
        "_read_nightly_log_started_at",
        lambda _db, _lid: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        sp,
        "collect_gitlab_tags_and_releases",
        lambda _db, **_kwargs: 3,
    )
    monkeypatch.setattr(sp, "_finish_nightly_sync_log", lambda *a, **k: 0)
    monkeypatch.setattr(sp, "send_webhook_notification", lambda *a, **k: True)
    monkeypatch.setattr(
        sp,
        "_generate_snapshots",
        lambda _db, _cfg: 0,
    )

    payload = sp.run_nightly_sync(config=ConfigurationSchema(), session_factory=session_factory)
    assert payload["status"] == "partial_failure"
    assert any("skipped bug_release mapping" in m for m in info_messages)


def test_run_nightly_sync_exception_after_success_finishes_failed_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Covers the outer except path (notify failure after main work)."""
    maker = _session_maker()

    def session_factory() -> Session:
        return maker()

    monkeypatch.setattr(
        sp,
        "_read_nightly_log_started_at",
        lambda _db, _lid: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(sp, "_resolve_orphaned_sync_logs", lambda _sf: None)
    monkeypatch.setattr(
        sp,
        "load_runtime_config",
        lambda db=None: RuntimeConfig(
            settings=ConfigurationSchema(),
            gitlab_token="a",
            jira_token="b",
            jira_user_email="",
        ),
    )
    monkeypatch.setattr(sp, "_create_nightly_sync_log", lambda _sf, **_: 7)
    monkeypatch.setattr(sp, "_gitlab_table_counts", lambda _db: {"repositories": 1})
    monkeypatch.setattr(sp, "_jira_table_counts", lambda _db: {"bugs": 1})
    monkeypatch.setattr(sp, "_max_metric_snapshot_created_at", lambda _db: None)
    monkeypatch.setattr(sp, "_run_with_session", lambda _sf, fn: fn(None))
    monkeypatch.setattr(
        sp,
        "collect_gitlab_tags_and_releases",
        lambda _db, **_kwargs: 1,
    )
    monkeypatch.setattr(
        sp,
        "collect_jira_production_bugs",
        lambda _db, **_kwargs: 1,
    )
    monkeypatch.setattr(sp, "_map_bugs_to_releases", lambda _db: 0)
    monkeypatch.setattr(sp, "_resolve_mttr_alpha_fix_releases", lambda _db, _config: 0)
    monkeypatch.setattr(
        sp,
        "hydrate_merge_request_jira_ready_for_qa",
        lambda *_a, **_k: 0,
    )
    monkeypatch.setattr(sp, "_compute_lead_post_production", lambda _db, **_: 0)
    monkeypatch.setattr(sp, "_generate_snapshots", lambda _db, _cfg: 0)

    finishes: list[dict[str, object]] = []

    def capture_finish(sf, **kwargs):  # type: ignore[no-untyped-def]
        finishes.append(kwargs)
        return 0

    monkeypatch.setattr(sp, "_finish_nightly_sync_log", capture_finish)

    def boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("webhook unavailable")

    monkeypatch.setattr(sp, "send_webhook_notification", boom)

    with pytest.raises(RuntimeError, match="webhook unavailable"):
        sp.run_nightly_sync(config=ConfigurationSchema(), session_factory=session_factory)

    assert finishes[-1]["status"] == "failed"
    assert "nightly:" in str(finishes[-1]["error_message"] or "")


def test_reconcile_nightly_runs_on_app_startup_marks_stuck_running_as_crashed() -> None:
    maker = _session_maker()
    # Recent: not auto-resolved by the 4h rule in _resolve_orphaned_sync_logs
    started = datetime.now(timezone.utc) - timedelta(hours=1)
    with maker() as db:
        db.add(
            SyncLog(
                id=1,
                source="nightly",
                started_at=started,
                status="running",
                records_processed=0,
                error_message=None,
            )
        )
        db.commit()

    sp.reconcile_nightly_runs_on_app_startup(session_factory=maker)

    with maker() as db:
        row = db.get(SyncLog, 1)
        assert row is not None
        assert row.status == "crashed"
        assert row.finished_at is not None
        assert "restart" in (row.error_message or "").lower()


def test_reconcile_nightly_runs_on_app_startup_skips_interrupt_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DORA_SKIP_STARTUP_SYNC_RECONCILE", "1")
    maker = _session_maker()
    started = datetime.now(timezone.utc) - timedelta(minutes=5)
    with maker() as db:
        db.add(
            SyncLog(
                id=1,
                source="nightly",
                started_at=started,
                status="running",
                records_processed=0,
                error_message=None,
            )
        )
        db.commit()

    sp.reconcile_nightly_runs_on_app_startup(session_factory=maker)

    with maker() as db:
        row = db.get(SyncLog, 1)
        assert row is not None
        assert row.status == "running"
