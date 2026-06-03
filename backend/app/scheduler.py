from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.hrworks.sync_pipeline import run_hrworks_sync
from app.jira_analytics.sync_pipeline import run_jira_analytics_sync
from app.services.config_service import load_runtime_config
from app.services.sync_pipeline import run_nightly_sync

_scheduler: BackgroundScheduler | None = None


def _run_scheduled_jira_analytics_sync() -> None:
    with SessionLocal() as db:
        runtime = load_runtime_config(db)
    run_jira_analytics_sync(
        config=runtime.settings,
        jira_token=runtime.jira_token,
        jira_user_email=runtime.jira_user_email,
        trigger="scheduled",
        lookback_days=runtime.settings.jira_analytics.scheduled_lookback_days,
    )


def build_scheduler(config: ConfigurationSchema) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
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
    scheduler.add_job(
        lambda: run_hrworks_sync(trigger="scheduled", incremental=True),
        trigger=CronTrigger(
            day_of_week=config.hrworks.sync_cron_day_of_week,
            hour=config.hrworks.sync_cron_hour,
            minute=config.hrworks.sync_cron_minute,
            timezone="UTC",
        ),
        id="hrworks_weekly_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_scheduled_jira_analytics_sync,
        trigger=CronTrigger(
            hour=config.jira_analytics.sync_cron_hour,
            minute=config.jira_analytics.sync_cron_minute,
            timezone="UTC",
        ),
        id="jira_analytics_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_scheduler(config: ConfigurationSchema) -> BackgroundScheduler:
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


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def reschedule_nightly_sync(config: ConfigurationSchema) -> None:
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        return
    scheduler.reschedule_job(
        "nightly_sync",
        trigger=CronTrigger(
            hour=config.backend.sync_cron_hour,
            minute=config.backend.sync_cron_minute,
            timezone="UTC",
        ),
    )


def reschedule_hrworks_sync(config: ConfigurationSchema) -> None:
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        return
    scheduler.reschedule_job(
        "hrworks_weekly_sync",
        trigger=CronTrigger(
            day_of_week=config.hrworks.sync_cron_day_of_week,
            hour=config.hrworks.sync_cron_hour,
            minute=config.hrworks.sync_cron_minute,
            timezone="UTC",
        ),
    )


def reschedule_jira_analytics_sync(config: ConfigurationSchema) -> None:
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        return
    scheduler.reschedule_job(
        "jira_analytics_sync",
        trigger=CronTrigger(
            hour=config.jira_analytics.sync_cron_hour,
            minute=config.jira_analytics.sync_cron_minute,
            timezone="UTC",
        ),
    )


def reschedule_all_schedulers(config: ConfigurationSchema) -> None:
    reschedule_nightly_sync(config)
    reschedule_hrworks_sync(config)
    reschedule_jira_analytics_sync(config)
