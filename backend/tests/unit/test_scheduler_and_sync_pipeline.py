from __future__ import annotations

from app.config_schema import ConfigurationSchema
from app.scheduler import build_scheduler
from app.services import sync_pipeline
from app.services.config_service import RuntimeConfig


def _fake_load_runtime_config(*_args, **_kwargs) -> RuntimeConfig:
    return RuntimeConfig(
        settings=ConfigurationSchema(),
        gitlab_token="test-gitlab-token",
        jira_token="test-jira-token",
    )


def test_build_scheduler_registers_nightly_job_with_configured_cron() -> None:
    config = ConfigurationSchema.model_validate(
        {
            "backend": {"sync_cron_hour": 3, "sync_cron_minute": 45},
        }
    )
    scheduler = build_scheduler(config)
    job = scheduler.get_job("nightly_sync")
    assert job is not None
    assert str(job.trigger) == "cron[hour='3', minute='45']"


def test_run_nightly_sync_executes_required_order_when_both_collectors_succeed(monkeypatch) -> None:
    order: list[str] = []

    monkeypatch.setattr(sync_pipeline, "load_runtime_config", _fake_load_runtime_config)
    monkeypatch.setattr(sync_pipeline, "_create_nightly_sync_log", lambda _sf: 1)
    monkeypatch.setattr(sync_pipeline, "_finish_nightly_sync_log", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sync_pipeline, "_notify_webhook", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sync_pipeline, "_run_with_session", lambda _sf, fn: fn(None))
    monkeypatch.setattr(
        sync_pipeline,
        "collect_gitlab_tags_and_releases",
        lambda _db, **_kwargs: order.append("gitlab") or 10,
    )
    monkeypatch.setattr(
        sync_pipeline,
        "collect_jira_production_bugs",
        lambda _db, **_kwargs: order.append("jira") or 11,
    )
    monkeypatch.setattr(sync_pipeline, "_map_bugs_to_releases", lambda _db: order.append("links") or 12)
    monkeypatch.setattr(
        sync_pipeline,
        "_resolve_mttr_alpha_fix_releases",
        lambda _db, _config: order.append("mttr_alpha") or 13,
    )
    monkeypatch.setattr(
        sync_pipeline, "_compute_lead_post_production", lambda _db: order.append("lead_post_prod") or 14
    )
    monkeypatch.setattr(
        sync_pipeline, "_generate_snapshots", lambda _db, _config: order.append("snapshots") or 15
    )

    payload = sync_pipeline.run_nightly_sync(config=ConfigurationSchema())
    assert payload["status"] == "success"
    assert order == ["gitlab", "jira", "links", "mttr_alpha", "lead_post_prod", "snapshots"]


def test_run_nightly_sync_partial_failure_skips_links_mttr_lead_post_and_snapshots(monkeypatch) -> None:
    order: list[str] = []

    monkeypatch.setattr(sync_pipeline, "load_runtime_config", _fake_load_runtime_config)
    monkeypatch.setattr(sync_pipeline, "_create_nightly_sync_log", lambda _sf: 2)
    monkeypatch.setattr(sync_pipeline, "_finish_nightly_sync_log", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sync_pipeline, "_notify_webhook", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sync_pipeline, "_run_with_session", lambda _sf, fn: fn(None))

    def _gitlab_fail(_db, **_kwargs):
        order.append("gitlab")
        raise RuntimeError("gitlab failed")

    monkeypatch.setattr(sync_pipeline, "collect_gitlab_tags_and_releases", _gitlab_fail)
    monkeypatch.setattr(
        sync_pipeline,
        "collect_jira_production_bugs",
        lambda _db, **_kwargs: order.append("jira") or 7,
    )
    monkeypatch.setattr(sync_pipeline, "_map_bugs_to_releases", lambda _db: order.append("links") or 3)
    monkeypatch.setattr(
        sync_pipeline,
        "_resolve_mttr_alpha_fix_releases",
        lambda _db, _config: order.append("mttr_alpha") or 99,
    )
    monkeypatch.setattr(
        sync_pipeline, "_compute_lead_post_production", lambda _db: order.append("lead_post_prod") or 99
    )
    monkeypatch.setattr(
        sync_pipeline, "_generate_snapshots", lambda _db, _config: order.append("snapshots") or 1
    )

    payload = sync_pipeline.run_nightly_sync(config=ConfigurationSchema())
    assert payload["status"] == "partial_failure"
    assert "links" not in order
    assert "mttr_alpha" not in order
    assert "lead_post_prod" not in order
    assert "snapshots" not in order
    assert order == ["gitlab", "jira"]
