from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CollectorStatusBlock(BaseModel):
    model_config = {"extra": "allow"}

    status: str
    records_processed: dict[str, int] = Field(default_factory=dict)


class LastSyncBlock(BaseModel):
    model_config = {"extra": "allow"}

    started_at: datetime
    finished_at: datetime | None
    duration_seconds: int | None
    status: str
    collectors: dict[str, CollectorStatusBlock]
    snapshots_generated: int
    snapshot_generated_at: datetime | None


class SyncStatusResponse(BaseModel):
    last_sync: LastSyncBlock | None
    last_successful_sync_at: datetime | None
    next_scheduled_sync: datetime | None
    sync_schedule_cron: str
    pipeline_in_progress: bool = False
    pipeline_run_started_at: datetime | None = None
    pipeline_run_trigger: str | None = None
