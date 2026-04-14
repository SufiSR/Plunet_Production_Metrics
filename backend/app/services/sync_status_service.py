from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.models.sync_log import SyncLog
from app.scheduler import get_scheduler
from app.schemas.sync_status import (
    CollectorStatusBlock,
    LastSyncBlock,
    PipelinePhaseBlock,
    PipelineRuntimeBlock,
    SyncStatusResponse,
)


def _map_run_status(raw: str) -> str:
    return {
        "success": "SUCCESS",
        "partial_failure": "PARTIAL_FAILURE",
        "failed": "FAILED",
        "crashed": "FAILED",
        "running": "FAILED",
    }.get(raw, "FAILED")


def _parse_iso_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            cleaned = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def _default_runtime(trigger: str | None = None) -> PipelineRuntimeBlock:
    now = datetime.now(timezone.utc)
    phase_names = ("gitlab", "jira", "derivations", "snapshots", "complete")
    phases = {
        phase: PipelinePhaseBlock(
            status="pending",
            message=None,
            records_processed={},
            started_at=None,
            finished_at=None,
            duration_seconds=None,
        )
        for phase in phase_names
    }
    if trigger:
        phases["complete"].message = f"Triggered by {trigger}"
    return PipelineRuntimeBlock(
        current_phase="queued",
        phase_started_at=now,
        phases=phases,
        errors=[],
    )


def _parse_pipeline_runtime(details: dict[str, Any], *, trigger: str | None) -> PipelineRuntimeBlock:
    runtime_raw = details.get("pipeline_runtime")
    if not isinstance(runtime_raw, dict):
        return _default_runtime(trigger)

    phase_names = ("gitlab", "jira", "derivations", "snapshots", "complete")
    phases_raw = runtime_raw.get("phases") if isinstance(runtime_raw.get("phases"), dict) else {}
    phases: dict[str, PipelinePhaseBlock] = {}
    for name in phase_names:
        block = phases_raw.get(name)
        if isinstance(block, dict):
            rec = block.get("records_processed")
            phases[name] = PipelinePhaseBlock(
                status=str(block.get("status") or "pending"),
                message=str(block.get("message")) if isinstance(block.get("message"), str) else None,
                records_processed=rec if isinstance(rec, dict) else {},
                started_at=_parse_iso_dt(block.get("started_at")),
                finished_at=_parse_iso_dt(block.get("finished_at")),
                duration_seconds=(
                    int(block.get("duration_seconds"))
                    if isinstance(block.get("duration_seconds"), int)
                    else None
                ),
            )
            continue
        phases[name] = PipelinePhaseBlock(
            status="pending",
            message=None,
            records_processed={},
            started_at=None,
            finished_at=None,
            duration_seconds=None,
        )

    errors_raw = runtime_raw.get("errors")
    errors = [str(err) for err in errors_raw if isinstance(err, str)] if isinstance(errors_raw, list) else []

    return PipelineRuntimeBlock(
        current_phase=str(runtime_raw.get("current_phase") or "queued"),
        phase_started_at=(
            _parse_iso_dt(runtime_raw.get("phase_started_at"))
            or _parse_iso_dt(details.get("started_at"))
            or datetime.now(timezone.utc)
        ),
        phases=phases,
        errors=errors,
    )


def build_sync_status_response(
    db: Session,
    *,
    config: ConfigurationSchema,
) -> SyncStatusResponse:
    running_row = db.scalars(
        select(SyncLog)
        .where(SyncLog.source == "nightly", SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .limit(1)
    ).first()
    if running_row is not None:
        latest_finished_any = db.scalar(
            select(func.max(SyncLog.finished_at)).where(
                SyncLog.source == "nightly",
                SyncLog.status != "running",
                SyncLog.finished_at.isnot(None),
            )
        )
        if latest_finished_any is not None and running_row.started_at < latest_finished_any:
            running_row = None
    pipeline_in_progress = running_row is not None
    pipeline_run_started_at = running_row.started_at if running_row else None
    pipeline_run_trigger: str | None = None
    if running_row is not None and isinstance(running_row.details_json, dict):
        raw_t = running_row.details_json.get("trigger")
        if isinstance(raw_t, str):
            pipeline_run_trigger = raw_t
    pipeline_runtime: PipelineRuntimeBlock | None = None
    if running_row is not None and isinstance(running_row.details_json, dict):
        pipeline_runtime = _parse_pipeline_runtime(
            running_row.details_json,
            trigger=pipeline_run_trigger,
        )

    row = db.scalars(
        select(SyncLog)
        .where(SyncLog.source == "nightly", SyncLog.status != "running")
        .order_by(SyncLog.started_at.desc())
        .limit(1)
    ).first()

    last_successful = db.scalar(
        select(SyncLog.finished_at)
        .where(
            SyncLog.source == "nightly",
            SyncLog.status.in_(("success", "partial_failure")),
            SyncLog.finished_at.isnot(None),
        )
        .order_by(SyncLog.finished_at.desc())
        .limit(1)
    )

    cron = f"{config.backend.sync_cron_minute} {config.backend.sync_cron_hour} * * *"

    scheduler = get_scheduler()
    next_run: datetime | None = None
    if scheduler is not None and scheduler.running:
        job = scheduler.get_job("nightly_sync")
        if job is not None and job.next_run_time is not None:
            nrt = job.next_run_time
            if nrt.tzinfo is None:
                nrt = nrt.replace(tzinfo=timezone.utc)
            next_run = nrt.astimezone(timezone.utc)

    if row is None:
        return SyncStatusResponse(
            last_sync=None,
            last_successful_sync_at=last_successful,
            next_scheduled_sync=next_run,
            sync_schedule_cron=cron,
            pipeline_in_progress=pipeline_in_progress,
            pipeline_run_started_at=pipeline_run_started_at,
            pipeline_run_trigger=pipeline_run_trigger,
            pipeline_runtime=pipeline_runtime,
        )

    details = row.details_json if isinstance(row.details_json, dict) else {}
    collectors_raw = details.get("collectors")
    collectors: dict[str, CollectorStatusBlock] = {}
    if isinstance(collectors_raw, dict):
        for key in ("gitlab", "jira"):
            block = collectors_raw.get(key)
            if isinstance(block, dict):
                rec = block.get("records_processed")
                collectors[key] = CollectorStatusBlock(
                    status=str(block.get("status") or "FAILED"),
                    records_processed=rec if isinstance(rec, dict) else {},
                )
            else:
                collectors[key] = CollectorStatusBlock(status="FAILED", records_processed={})
    else:
        collectors = {
            "gitlab": CollectorStatusBlock(status="FAILED", records_processed={}),
            "jira": CollectorStatusBlock(status="FAILED", records_processed={}),
        }

    started_at = row.started_at
    finished_at = row.finished_at
    if started_at is None:
        started_at = datetime.now(timezone.utc)
    duration_seconds: int | None = None
    if finished_at is not None:
        duration_seconds = int((finished_at - started_at).total_seconds())
    elif isinstance(details.get("duration_seconds"), int):
        duration_seconds = details["duration_seconds"]

    snap_at = _parse_iso_dt(details.get("snapshot_generated_at"))
    snaps = details.get("snapshots_generated")
    if not isinstance(snaps, int):
        snaps = 0

    err_msg = row.error_message if isinstance(row.error_message, str) else None
    if err_msg is not None and not err_msg.strip():
        err_msg = None

    last_block = LastSyncBlock(
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        status=_map_run_status(row.status),
        collectors=collectors,
        snapshots_generated=int(snaps),
        snapshot_generated_at=snap_at,
        error_message=err_msg,
    )

    return SyncStatusResponse(
        last_sync=last_block,
        last_successful_sync_at=last_successful,
        next_scheduled_sync=next_run,
        sync_schedule_cron=cron,
        pipeline_in_progress=pipeline_in_progress,
        pipeline_run_started_at=pipeline_run_started_at,
        pipeline_run_trigger=pipeline_run_trigger,
        pipeline_runtime=pipeline_runtime,
    )
