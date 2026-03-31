from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config_schema import ConfigurationSchema
from app.services.sync_pipeline import run_nightly_sync

_scheduler: AsyncIOScheduler | None = None


def build_scheduler(config: ConfigurationSchema) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_nightly_sync,
        trigger=CronTrigger(
            hour=config.backend.sync_cron_hour,
            minute=config.backend.sync_cron_minute,
            timezone="UTC",
        ),
        id="nightly_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_scheduler(config: ConfigurationSchema) -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = build_scheduler(config)
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
