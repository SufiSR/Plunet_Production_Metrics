from __future__ import annotations

import logging
import threading
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select

from app.api.deps import SessionDep, require_admin_session
from app.hrworks.sync_pipeline import run_hrworks_sync
from app.models.sync_log import SyncLog

logger = logging.getLogger(__name__)

router = APIRouter()

AdminSessionDep = Annotated[None, Depends(require_admin_session)]


def _run_manual_hrworks_sync_in_thread(*, incremental: bool) -> None:
    try:
        run_hrworks_sync(trigger="manual", incremental=incremental)
    except Exception:
        logger.exception("manual HRworks sync background thread failed")


@router.post("/hrworks/sync/trigger", status_code=202)
def trigger_manual_hrworks_sync(
    _auth: AdminSessionDep,
    incremental: bool = False,
) -> JSONResponse:
    """Fire off a manual HRworks sync in the background and return immediately."""
    logger.info("admin requested manual HRworks sync (incremental=%s)", incremental)
    thread = threading.Thread(
        target=lambda: _run_manual_hrworks_sync_in_thread(incremental=incremental),
        name="manual-hrworks-sync",
        daemon=True,
    )
    thread.start()
    return JSONResponse(status_code=202, content={"detail": "HRworks sync triggered"})


@router.get("/hrworks/sync/latest")
def latest_hrworks_sync(
    _auth: AdminSessionDep,
    db: SessionDep,
) -> dict[str, Any]:
    row = db.execute(
        select(SyncLog)
        .where(SyncLog.source == "hrworks")
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
