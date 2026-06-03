from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func, select

from app.api.deps import SessionDep, require_admin_session
from app.database import SessionLocal
from app.jira_analytics.allocation import rebuild_monthly_allocation
from app.jira_analytics.models import JiraWorklog, MonthlyAllocatedEffort, MonthlyTopicEffortBase
from app.jira_analytics.project_scope import apply_worklog_issue_scope
from app.jira_analytics.sync_pipeline import run_jira_analytics_sync
from app.models.app_configuration import AppConfiguration
from app.models.sync_log import SyncLog

logger = logging.getLogger(__name__)

router = APIRouter()

AdminSessionDep = Annotated[None, Depends(require_admin_session)]

_allocation_rebuild_lock = threading.Lock()
_allocation_rebuild_status: dict[str, Any] = {
    "state": "idle",
    "started_at": None,
    "finished_at": None,
    "periods": [],
    "topic_rows": 0,
    "allocation_rows": 0,
    "error": None,
    "message": None,
}


def _run_manual_jira_analytics_sync_in_thread(*, updated_after_days: int | None) -> None:
    try:
        run_jira_analytics_sync(trigger="manual", lookback_days=updated_after_days)
    except Exception:
        logger.exception("manual jira analytics sync background thread failed")


def _settings_json(db: SessionDep) -> dict[str, Any]:
    app_row = db.get(AppConfiguration, 1)
    return dict(app_row.settings_json) if app_row and isinstance(app_row.settings_json, dict) else {}


def _parse_period_month(period_month: str) -> date:
    try:
        parsed = date.fromisoformat(period_month[:10])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_month must be an ISO date, for example 2026-05-01",
        ) from exc
    return date(parsed.year, parsed.month, 1)


def _current_allocation_summary(db: SessionDep) -> dict[str, Any]:
    periods = db.execute(
        select(MonthlyAllocatedEffort.period_month)
        .distinct()
        .order_by(MonthlyAllocatedEffort.period_month.asc())
    ).scalars().all()
    topic_rows = db.execute(select(func.count()).select_from(MonthlyTopicEffortBase)).scalar_one()
    allocation_rows = db.execute(select(func.count()).select_from(MonthlyAllocatedEffort)).scalar_one()
    return {
        "periods": [p.isoformat() for p in periods],
        "topic_rows": int(topic_rows),
        "allocation_rows": int(allocation_rows),
    }


def _distinct_worklog_period_count(db: SessionDep) -> int:
    rows = db.execute(
        apply_worklog_issue_scope(
            select(JiraWorklog.started_at).where(JiraWorklog.started_at.is_not(None)).distinct()
        )
    ).scalars().all()
    return len({date(row.year, row.month, 1) for row in rows if row is not None})


def _run_allocation_rebuild_in_thread() -> None:
    try:
        with SessionLocal() as session:
            result = rebuild_monthly_allocation(session, settings_json=_settings_json(session))
        with _allocation_rebuild_lock:
            _allocation_rebuild_status.update(
                {
                    "state": "succeeded",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "periods": result["periods"],
                    "topic_rows": result["topic_rows"],
                    "allocation_rows": result["allocation_rows"],
                    "error": None,
                    "message": (
                        f"Rebuilt {result['allocation_rows']} allocation row"
                        f"{'' if result['allocation_rows'] == 1 else 's'} across "
                        f"{len(result['periods'])} month{'' if len(result['periods']) == 1 else 's'}."
                    ),
                }
            )
    except Exception as exc:  # pragma: no cover - defensive status reporting
        logger.exception("manual jira analytics allocation rebuild failed")
        with _allocation_rebuild_lock:
            _allocation_rebuild_status.update(
                {
                    "state": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                    "message": "Allocation rebuild failed.",
                }
            )


@router.post("/jira-analytics/sync/trigger", status_code=202)
def trigger_manual_jira_analytics_sync(
    _auth: AdminSessionDep,
    updated_after_days: int | None = Query(
        default=None,
        ge=1,
        le=3650,
        description="Only ingest issues updated in the last N days (JQL updated >=). Omit to use scheduled default from config.",
    ),
) -> JSONResponse:
    """Fire off a manual Jira analytics sync in the background and return immediately."""
    logger.info(
        "admin requested manual jira analytics sync (updated_after_days=%s)",
        updated_after_days,
    )
    thread = threading.Thread(
        target=lambda: _run_manual_jira_analytics_sync_in_thread(updated_after_days=updated_after_days),
        name="manual-jira-analytics-sync",
        daemon=True,
    )
    thread.start()
    detail = "Jira analytics sync triggered"
    if updated_after_days is not None:
        detail = f"Jira analytics sync triggered (updated >= -{updated_after_days}d)"
    return JSONResponse(status_code=202, content={"detail": detail, "updated_after_days": updated_after_days})


@router.get("/jira-analytics/sync/latest")
def latest_jira_analytics_sync(
    _auth: AdminSessionDep,
    db: SessionDep,
) -> dict[str, Any]:
    row = db.execute(
        select(SyncLog)
        .where(SyncLog.source == "jira_analytics")
        .order_by(desc(SyncLog.started_at))
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return {"status": None, "sync_log": None}
    return {
        "status": row.status,
        "sync_log": {
            "id": row.id,
            "source": row.source,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "records_processed": row.records_processed,
            "error_message": row.error_message,
            "details_json": row.details_json,
        },
    }


@router.post("/jira-analytics/rebuild-allocation")
def rebuild_allocation_admin(
    _auth: AdminSessionDep,
    db: SessionDep,
    period_month: str | None = None,
) -> Any:
    months = None
    if period_month:
        months = [_parse_period_month(period_month)]
        result = rebuild_monthly_allocation(db, settings_json=_settings_json(db), period_months=months)
        return {"state": "succeeded", **result}

    current = _current_allocation_summary(db)
    worklog_period_count = _distinct_worklog_period_count(db)
    with _allocation_rebuild_lock:
        if _allocation_rebuild_status["state"] == "running":
            return dict(_allocation_rebuild_status)
        _allocation_rebuild_status.update(
            {
                "state": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
                "periods": current["periods"],
                "topic_rows": current["topic_rows"],
                "allocation_rows": current["allocation_rows"],
                "error": None,
                "message": f"Allocation rebuild started for {worklog_period_count} month{'' if worklog_period_count == 1 else 's'}.",
            }
        )
    threading.Thread(
        target=_run_allocation_rebuild_in_thread,
        name="manual-jira-analytics-allocation-rebuild",
        daemon=True,
    ).start()
    return JSONResponse(status_code=202, content=dict(_allocation_rebuild_status))


@router.get("/jira-analytics/rebuild-allocation/status")
def rebuild_allocation_admin_status(
    _auth: AdminSessionDep,
) -> dict[str, Any]:
    with _allocation_rebuild_lock:
        return dict(_allocation_rebuild_status)
