from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.hrworks.collector import collect_hrworks_monthly_hours, resolve_sync_months
from app.hrworks.periods import MonthWindow
from app.models.sync_log import SyncLog
from app.services.config_service import load_runtime_config

logger = logging.getLogger(__name__)

PHASES = ("ingestion", "allocation", "complete")
_PROGRESS_FLUSH_INTERVAL_SECONDS = 2.0


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
            source="hrworks",
            started_at=datetime.now(timezone.utc),
            status="running",
            details_json={"trigger": trigger, "pipeline_runtime": _new_runtime(trigger=trigger)},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    return _run_with_session(session_factory, create)


def _apply_progress(runtime: dict[str, Any], progress: dict[str, Any]) -> None:
    runtime["progress"] = progress
    ingestion = runtime["phases"]["ingestion"]
    if ingestion.get("status") == "running":
        message = progress.get("message")
        if isinstance(message, str) and message.strip():
            ingestion["message"] = message[:400]
        ingestion["records_processed"] = {
            "api_calls": int(progress.get("api_calls") or 0),
            "rows_upserted": int(progress.get("rows_upserted") or 0),
            "months_completed": int(progress.get("months_completed") or 0),
            "months_total": int(progress.get("months_total") or 0),
        }


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


def run_hrworks_sync(
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    config: ConfigurationSchema | None = None,
    access_key: str | None = None,
    secret_access_key: str | None = None,
    trigger: str = "manual",
    incremental: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    months: list[MonthWindow] | None = None,
) -> dict[str, Any]:
    runtime = _new_runtime(trigger=trigger)
    log_id = _create_log(session_factory, trigger=trigger)
    errors: list[str] = []
    records_processed = 0
    started_at = datetime.now(timezone.utc)

    if config is None or access_key is None or secret_access_key is None:
        with session_factory() as db:
            runtime_config = load_runtime_config(db)
        config = config or runtime_config.settings
        access_key = access_key if access_key is not None else runtime_config.hrworks_access_key
        secret_access_key = (
            secret_access_key
            if secret_access_key is not None
            else runtime_config.hrworks_secret_access_key
        )

    try:
        if not (access_key or "").strip() or not (secret_access_key or "").strip():
            raise RuntimeError("HRworks credentials are not configured")

        resolved_months = months or resolve_sync_months(
            config=config,
            incremental=incremental,
            start_date=start_date,
            end_date=end_date,
        )
        runtime["month_windows"] = [
            {"month_start": window.month_start.isoformat(), "month_end": window.month_end.isoformat()}
            for window in resolved_months
        ]

        _transition(
            runtime,
            phase="ingestion",
            status="running",
            message="HRworks monthly hours ingestion started",
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})

        last_progress_flush = 0.0

        def on_progress(progress: dict[str, Any]) -> None:
            nonlocal last_progress_flush
            _apply_progress(runtime, progress)
            now = time.monotonic()
            if now - last_progress_flush >= _PROGRESS_FLUSH_INTERVAL_SECONDS:
                _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})
                last_progress_flush = now

        with session_factory() as db:
            counts = collect_hrworks_monthly_hours(
                db,
                config=config,
                access_key=access_key,
                secret_access_key=secret_access_key,
                months=resolved_months,
                on_progress=on_progress,
            )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})
        records_processed += sum(counts.as_records_processed().values())
        errors.extend(counts.errors)
        if counts.unknown_emails:
            logger.warning(
                "HRworks sync: ignored unexpected working-times keys: %s",
                ", ".join(counts.unknown_emails[:10]),
            )
        _transition(
            runtime,
            phase="ingestion",
            status="success" if not counts.errors else "failed",
            message="HRworks monthly hours ingestion finished",
            records_processed=counts.as_records_processed(),
        )
        _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})

        allocation_months = sorted(counts.months_upserted)
        runtime["allocation_period_months"] = [month.isoformat() for month in allocation_months]
        if counts.errors:
            _transition(
                runtime,
                phase="allocation",
                status="skipped",
                message="Monthly effort allocation skipped because HRworks ingestion had errors",
            )
        elif not allocation_months:
            _transition(
                runtime,
                phase="allocation",
                status="skipped",
                message="Monthly effort allocation skipped because HRworks returned no monthly hour rows",
                records_processed={"periods": 0, "topic_rows": 0, "allocation_rows": 0},
            )
        else:
            _transition(
                runtime,
                phase="allocation",
                status="running",
                message="Monthly effort allocation started",
            )
            _update_log(session_factory, log_id=log_id, details_json={"pipeline_runtime": runtime})
            with session_factory() as db:
                from app.jira_analytics.allocation import rebuild_monthly_allocation

                alloc_result = rebuild_monthly_allocation(db, period_months=allocation_months)
            _transition(
                runtime,
                phase="allocation",
                status="success",
                message="Monthly effort allocation finished",
                records_processed=alloc_result,
            )
    except Exception as exc:
        errors.append(str(exc))
        logger.exception("HRworks sync failed")
        phase = str(runtime.get("current_phase") or "ingestion")
        if phase in PHASES:
            _transition(runtime, phase=phase, status="failed", message=str(exc))

    status = "success" if not errors else "partial_failure" if records_processed else "failed"
    finished_at = datetime.now(timezone.utc)
    _transition(
        runtime,
        phase="complete",
        status="success" if status != "failed" else "failed",
        message="HRworks sync finished",
        records_processed={"total_records_processed": records_processed},
    )
    details_json = {
        "trigger": trigger,
        "incremental": incremental,
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
