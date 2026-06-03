from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.jira_analytics.collector import collect_jira_analytics
from app.jira_analytics.feature_membership import refresh_feature_memberships
from app.models.sync_log import SyncLog
from app.services.config_service import load_runtime_config

logger = logging.getLogger(__name__)

PHASES = ("ingestion", "workflow_sync", "feature_membership", "allocation", "complete")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_runtime(*, trigger: str) -> dict[str, Any]:
    now = _utc_now_iso()
    return {
        "current_phase": "queued",
        "phase_started_at": now,
        "trigger": trigger,
        "phases": {
            phase: {
                "status": "pending",
                "message": None,
                "records_processed": {},
                "started_at": None,
                "finished_at": None,
                "duration_seconds": None,
            }
            for phase in PHASES
        },
        "errors": [],
    }


def _transition(
    runtime: dict[str, Any],
    *,
    phase: str,
    status: str,
    message: str | None = None,
    records_processed: dict[str, int] | None = None,
) -> None:
    now = _utc_now_iso()
    runtime["current_phase"] = phase
    runtime["phase_started_at"] = now
    block = runtime["phases"][phase]
    if block.get("started_at") is None:
        block["started_at"] = now
    if status in {"success", "failed", "skipped"}:
        block["finished_at"] = now
        try:
            started = datetime.fromisoformat(str(block["started_at"]).replace("Z", "+00:00"))
            finished = datetime.fromisoformat(now.replace("Z", "+00:00"))
            block["duration_seconds"] = int((finished - started).total_seconds())
        except (TypeError, ValueError):
            block["duration_seconds"] = None
    block["status"] = status
    if message is not None:
        block["message"] = message[:400]
    if records_processed is not None:
        block["records_processed"] = records_processed


def _run_with_session(session_factory: Callable[[], Session], fn: Callable[[Session], int]) -> int:
    with session_factory() as db:
        return fn(db)


def _create_log(session_factory: Callable[[], Session], *, trigger: str) -> int:
    def create(db: Session) -> int:
        row = SyncLog(
            source="jira_analytics",
            started_at=datetime.now(timezone.utc),
            status="running",
            details_json={"trigger": trigger, "pipeline_runtime": _new_runtime(trigger=trigger)},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    return _run_with_session(session_factory, create)


def _update_log(
    session_factory: Callable[[], Session],
    *,
    log_id: int,
    details_json: dict[str, Any],
) -> int:
    def update(db: Session) -> int:
        row = db.get(SyncLog, log_id)
        if row is None:
            return 0
        existing = row.details_json if isinstance(row.details_json, dict) else {}
        row.details_json = {**existing, **details_json}
        db.commit()
        return 0

    return _run_with_session(session_factory, update)


def _finish_log(
    session_factory: Callable[[], Session],
    *,
    log_id: int,
    status: str,
    records_processed: int,
    error_message: str | None,
    details_json: dict[str, Any],
) -> int:
    def finish(db: Session) -> int:
        row = db.get(SyncLog, log_id)
        if row is None:
            return 0
        row.status = status
        row.finished_at = datetime.now(timezone.utc)
        row.records_processed = records_processed
        row.error_message = error_message
        row.details_json = details_json
        db.commit()
        return 0

    return _run_with_session(session_factory, finish)


def run_jira_analytics_sync(
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    config: ConfigurationSchema | None = None,
    jira_token: str | None = None,
    jira_user_email: str | None = None,
    trigger: str = "manual",
    jql: str | None = None,
    lookback_days: int | None = None,
) -> dict[str, Any]:
    runtime = _new_runtime(trigger=trigger)
    log_id = _create_log(session_factory, trigger=trigger)
    errors: list[str] = []
    records_processed = 0
    started_at = datetime.now(timezone.utc)
    if config is None or jira_token is None:
        with session_factory() as db:
            runtime_config = load_runtime_config(db)
        config = config or runtime_config.settings
        jira_token = jira_token if jira_token is not None else runtime_config.jira_token
        jira_user_email = (
            jira_user_email if jira_user_email is not None else runtime_config.jira_user_email
        )

    try:
        if not (jira_token or "").strip():
            raise RuntimeError("Jira token is not configured")
        _transition(
            runtime, phase="ingestion", status="running", message="Jira analytics ingestion started"
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})
        effective_lookback = (
            lookback_days if lookback_days is not None else config.jira_analytics.scheduled_lookback_days
        )
        _update_log(
            session_factory,
            log_id=log_id,
            details_json={
                "updated_after_days": effective_lookback,
                "pipeline_runtime": runtime,
            },
        )
        with session_factory() as db:
            counts = collect_jira_analytics(
                db,
                config=config,
                jira_token=jira_token,
                jira_user_email=jira_user_email,
                jql=jql,
                lookback_days=lookback_days,
            )
        records_processed += sum(counts.as_records_processed().values())
        errors.extend(counts.errors)
        _transition(
            runtime,
            phase="ingestion",
            status="success" if not counts.errors else "failed",
            message="Jira analytics ingestion finished",
            records_processed=counts.as_records_processed(),
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})

        _transition(
            runtime,
            phase="workflow_sync",
            status="running",
            message="Jira workflow definitions sync started",
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})
        with session_factory() as db:
            from app.jira_analytics.client import JiraAnalyticsClient
            from app.jira_analytics.workflow.workflow_sync import sync_jira_workflows

            with JiraAnalyticsClient(
                config.jira.base_url,
                jira_token,
                user_email=jira_user_email,
            ) as client:
                workflow_counts = sync_jira_workflows(db, client)
                db.commit()
        records_processed += sum(workflow_counts.as_records_processed().values())
        errors.extend(workflow_counts.errors)
        _transition(
            runtime,
            phase="workflow_sync",
            status="success" if not workflow_counts.errors else "failed",
            message="Jira workflow definitions sync finished",
            records_processed=workflow_counts.as_records_processed(),
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})

        _transition(
            runtime,
            phase="feature_membership",
            status="running",
            message="Feature membership derivation started",
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})
        with session_factory() as db:
            membership_counts = refresh_feature_memberships(db)
        membership_processed = {
            "roots_upserted": membership_counts.roots_upserted,
            "memberships_written": membership_counts.memberships_written,
        }
        records_processed += sum(membership_processed.values())
        _transition(
            runtime,
            phase="feature_membership",
            status="success",
            message="Feature membership derivation finished",
            records_processed=membership_processed,
        )
        if not errors:
            _transition(
                runtime,
                phase="allocation",
                status="running",
                message="Monthly effort allocation started",
            )
            with session_factory() as db:
                from app.jira_analytics.allocation import rebuild_monthly_allocation
                from app.models.app_configuration import AppConfiguration

                app_row = db.get(AppConfiguration, 1)
                settings = (
                    dict(app_row.settings_json)
                    if app_row and isinstance(app_row.settings_json, dict)
                    else {}
                )
                alloc_result = rebuild_monthly_allocation(db, settings_json=settings)
            _transition(
                runtime,
                phase="allocation",
                status="success",
                message="Monthly effort allocation finished",
                records_processed=alloc_result,
            )
    except Exception as exc:
        errors.append(str(exc))
        logger.exception("jira analytics sync failed")
        phase = str(runtime.get("current_phase") or "ingestion")
        if phase in PHASES:
            _transition(runtime, phase=phase, status="failed", message=str(exc))

    status = "success" if not errors else "partial_failure" if records_processed else "failed"
    finished_at = datetime.now(timezone.utc)
    _transition(
        runtime,
        phase="complete",
        status="success" if status != "failed" else "failed",
        message="Jira analytics sync finished",
        records_processed={"total_records_processed": records_processed},
    )
    details_json = {
        "trigger": trigger,
        "updated_after_days": lookback_days if lookback_days is not None else config.jira_analytics.scheduled_lookback_days,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "duration_seconds": int((finished_at - started_at).total_seconds()),
        "status": status,
        "pipeline_runtime": runtime,
    }
    _finish_log(
        session_factory,
        log_id=log_id,
        status=status,
        records_processed=records_processed,
        error_message=" | ".join(errors)[:4000] if errors else None,
        details_json=details_json,
    )
    return details_json
