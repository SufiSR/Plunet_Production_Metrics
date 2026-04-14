from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CollectorStatusBlock(BaseModel):
    model_config = {"extra": "allow"}

    status: str
    records_processed: dict[str, int] = Field(default_factory=dict)


class PipelinePhaseBlock(BaseModel):
    model_config = {"extra": "allow"}

    status: str
    message: str | None = None
    records_processed: dict[str, int] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None


class PipelineRuntimeBlock(BaseModel):
    model_config = {"extra": "allow"}

    current_phase: str
    phase_started_at: datetime | None = None
    phases: dict[str, PipelinePhaseBlock] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class LastSyncBlock(BaseModel):
    model_config = {"extra": "allow"}

    started_at: datetime
    finished_at: datetime | None
    duration_seconds: int | None
    status: str
    collectors: dict[str, CollectorStatusBlock]
    snapshots_generated: int
    snapshot_generated_at: datetime | None
    error_message: str | None = None


class SyncStatusResponse(BaseModel):
    last_sync: LastSyncBlock | None
    last_successful_sync_at: datetime | None
    next_scheduled_sync: datetime | None
    sync_schedule_cron: str
    pipeline_in_progress: bool = False
    pipeline_run_started_at: datetime | None = None
    pipeline_run_trigger: str | None = None
    pipeline_runtime: PipelineRuntimeBlock | None = None
