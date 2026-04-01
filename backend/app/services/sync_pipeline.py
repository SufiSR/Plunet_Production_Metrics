from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.sync_log import SyncLog
from app.services.config_service import load_runtime_config
from app.services.gitlab_release_collector import collect_gitlab_tags_and_releases
from app.services.jira_bug_collector import (
    collect_jira_production_bugs,
    hydrate_merge_request_jira_ready_for_qa,
)
from app.services.snapshot_service import refresh_snapshots

logger = logging.getLogger(__name__)


def _normalize_version_key(value: str) -> set[str]:
    normalized = value.strip().lower()
    if not normalized:
        return set()
    candidates = {normalized}
    if normalized.startswith("v"):
        without_v = normalized[1:]
        if without_v:
            candidates.add(without_v)
    else:
        candidates.add(f"v{normalized}")
    return candidates


def _run_with_session(
    session_factory: Callable[[], Session], fn: Callable[[Session], int]
) -> int:
    with session_factory() as session:
        return fn(session)


def _create_nightly_sync_log(session_factory: Callable[[], Session]) -> int:
    def _create(db: Session) -> int:
        row = SyncLog(
            source="nightly",
            started_at=datetime.now(timezone.utc),  # noqa: UP017
            status="running",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)

    return _run_with_session(session_factory, _create)


def _finish_nightly_sync_log(
    session_factory: Callable[[], Session],
    *,
    log_id: int,
    status: str,
    records_processed: int,
    error_message: str | None,
) -> int:
    def _finish(db: Session) -> int:
        row = db.get(SyncLog, log_id)
        if row is not None:
            row.status = status
            row.finished_at = datetime.now(timezone.utc)  # noqa: UP017
            row.records_processed = records_processed
            row.error_message = error_message
            db.commit()
        return 0

    return _run_with_session(session_factory, _finish)


def _lookback_start_utc(days: int) -> datetime:
    lookback_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    return datetime(
        lookback_date.year,
        lookback_date.month,
        lookback_date.day,
        tzinfo=timezone.utc,
    )


def _map_bugs_to_releases(db: Session) -> int:
    releases = db.execute(select(Release)).scalars().all()
    by_tag: dict[str, list[Release]] = {}
    for release in releases:
        if not release.tag_name:
            continue
        for key in _normalize_version_key(release.tag_name):
            by_tag.setdefault(key, []).append(release)
    processed = 0
    unmatched_versions = 0

    bugs = db.execute(select(ProductionBug)).scalars()
    for bug in bugs:
        db.execute(delete(BugRelease).where(BugRelease.bug_id == bug.id))
        linked_release_ids: set[int] = set()
        affects_versions = [value for value in (bug.affects_versions or []) if value]
        for version in affects_versions:
            candidate_releases: list[Release] = []
            for key in _normalize_version_key(version):
                candidate_releases.extend(by_tag.get(key, []))
            if not candidate_releases:
                unmatched_versions += 1
                continue
            for release in candidate_releases:
                if release.id in linked_release_ids:
                    continue
                linked_release_ids.add(release.id)
                db.add(BugRelease(bug_id=bug.id, release_id=release.id))
                processed += 1
    db.commit()
    logger.info(
        "map_bugs_to_releases completed",
        extra={"links_created": processed, "unmatched_versions": unmatched_versions},
    )
    return processed


def _resolve_mttr_alpha_fix_releases(db: Session, config: ConfigurationSchema) -> int:
    processed = 0
    release_by_tag: dict[str, list[tuple[datetime, str]]] = {}
    for tag_name, committed_at in db.execute(select(Release.tag_name, Release.committed_at)).all():
        if not tag_name or committed_at is None:
            continue
        for key in _normalize_version_key(tag_name):
            release_by_tag.setdefault(key, []).append((committed_at, tag_name))
    mr_by_jira_key: dict[str, tuple[datetime | None, str | None]] = {}
    for jira_key, fct_date, fct_tag in db.execute(
        select(
            MergeRequest.jira_key,
            MergeRequest.first_customer_tag_date,
            MergeRequest.first_customer_tag,
        ).where(
            MergeRequest.jira_key.isnot(None),
            MergeRequest.first_customer_tag_date.isnot(None),
        )
    ).all():
        if not jira_key or fct_date is None:
            continue
        current = mr_by_jira_key.get(jira_key)
        if current is None or fct_date < current[0]:
            mr_by_jira_key[jira_key] = (fct_date, fct_tag)

    eligible_priorities = {
        priority.strip().lower()
        for priority in config.jira.mttr_alpha_priorities
        if priority and priority.strip()
    }

    bugs = db.execute(select(ProductionBug)).scalars()
    for bug in bugs:
        bug_priority = (bug.priority or "").lower()
        if not bug.healthy or bug_priority not in eligible_priorities:
            continue

        fix_release_tag = None
        fix_release_date = None
        resolution_path = None
        mr_match = mr_by_jira_key.get(bug.jira_key)
        if mr_match is not None:
            fix_release_date, fix_release_tag = mr_match[0], mr_match[1]
            resolution_path = "mr_jira_key"
        else:
            for version in bug.fix_versions or []:
                candidate_releases: list[tuple[datetime, str]] = []
                for key in _normalize_version_key(version):
                    candidate_releases.extend(release_by_tag.get(key, []))
                for committed_at, tag_name in candidate_releases:
                    if fix_release_date is None or committed_at < fix_release_date:
                        fix_release_tag = tag_name
                        fix_release_date = committed_at
                        resolution_path = "fix_version"

        bug.first_fix_release_tag = fix_release_tag
        bug.first_fix_release_date = fix_release_date
        bug.mttr_alpha_resolution_path = resolution_path
        if (
            fix_release_date is not None
            and bug.jira_created_at_valid
            and bug.created_at is not None
            and bug.created_at <= fix_release_date
        ):
            bug.mttr_alpha_minutes = int((fix_release_date - bug.created_at).total_seconds() // 60)
        else:
            bug.mttr_alpha_minutes = None
        processed += 1

    db.commit()
    return processed


def _compute_lead_post_production(db: Session, *, lookback_days: int) -> int:
    processed = 0
    lookback_start = _lookback_start_utc(lookback_days)
    bug_by_jira_key = {
        bug.jira_key: bug for bug in db.execute(select(ProductionBug)).scalars() if bug.jira_key
    }
    merge_requests = db.execute(
        select(MergeRequest).where(MergeRequest.merged_at >= lookback_start)
    ).scalars()
    for merge_request in merge_requests:
        if not merge_request.jira_key:
            merge_request.lead_post_production_hours = None
            continue
        bug = bug_by_jira_key.get(merge_request.jira_key)
        ready_at = bug.ready_for_qa_at if bug is not None else None
        if ready_at is None:
            ready_at = merge_request.jira_ready_for_qa_at
        if ready_at is None or merge_request.merged_at < ready_at:
            merge_request.lead_post_production_hours = None
            continue
        hours = (merge_request.merged_at - ready_at).total_seconds() / 3600.0
        merge_request.lead_post_production_hours = Decimal(str(hours)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        processed += 1
    db.commit()
    return processed


def _generate_snapshots(db: Session, config: ConfigurationSchema) -> int:
    return refresh_snapshots(db, config=config)


def _notify_webhook(url: str | None, payload: dict[str, str | int]) -> None:
    if not url:
        return
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json=payload)
    except Exception:
        logger.exception("nightly_sync webhook notification failed")


def run_nightly_sync(
    *,
    config: ConfigurationSchema | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> dict[str, str | int]:
    with session_factory() as config_db:
        runtime_config = load_runtime_config(db=config_db)
    effective_config = config or runtime_config.settings
    gitlab_token = runtime_config.gitlab_token
    jira_token = runtime_config.jira_token
    webhook_url = effective_config.notifications.webhook_url
    nightly_log_id = _create_nightly_sync_log(session_factory)

    gitlab_ok = False
    jira_ok = False
    records_processed = 0
    errors: list[str] = []

    try:
        if (gitlab_token or "").strip():
            try:
                records_processed += _run_with_session(
                    session_factory,
                    lambda db: collect_gitlab_tags_and_releases(
                        db,
                        config=effective_config,
                        gitlab_token=gitlab_token,
                    ),
                )
                gitlab_ok = True
            except Exception as exc:
                errors.append(f"gitlab: {exc}")
                logger.exception("nightly_sync gitlab collector failed")
        else:
            msg = "GitLab API token is not configured (GITLAB_TOKEN / GITLAB_API_TOKEN)"
            errors.append(f"gitlab: {msg}")
            logger.error("nightly_sync skipped gitlab: %s", msg)

        if (jira_token or "").strip():
            try:
                records_processed += _run_with_session(
                    session_factory,
                    lambda db: collect_jira_production_bugs(
                        db,
                        config=effective_config,
                        jira_token=jira_token,
                    ),
                )
                jira_ok = True
            except Exception as exc:
                errors.append(f"jira: {exc}")
                logger.exception("nightly_sync jira collector failed")
        else:
            msg = "Jira API token is not configured (JIRA_TOKEN / JIRA_API_TOKEN)"
            errors.append(f"jira: {msg}")
            logger.error("nightly_sync skipped jira: %s", msg)

        if gitlab_ok and jira_ok:
            records_processed += _run_with_session(session_factory, _map_bugs_to_releases)
        elif gitlab_ok or jira_ok:
            logger.info("nightly_sync skipped bug_release mapping due to partial failure")

        if gitlab_ok and jira_ok:
            records_processed += _run_with_session(
                session_factory,
                lambda db: _resolve_mttr_alpha_fix_releases(db, effective_config),
            )
            records_processed += _run_with_session(
                session_factory,
                lambda db: hydrate_merge_request_jira_ready_for_qa(
                    db, config=effective_config, jira_token=jira_token
                ),
            )
            records_processed += _run_with_session(
                session_factory,
                lambda db: _compute_lead_post_production(
                    db, lookback_days=effective_config.backend.lookback_days
                ),
            )
        else:
            logger.info("nightly_sync skipped mttr_alpha, jira_ready_for_qa hydrate, and lead_post_production due to partial failure")

        if gitlab_ok or jira_ok:
            records_processed += _run_with_session(
                session_factory, lambda db: _generate_snapshots(db, effective_config)
            )
        else:
            logger.info("nightly_sync skipped snapshots: both collectors failed or were skipped")

        if gitlab_ok and jira_ok:
            status = "success"
        elif gitlab_ok or jira_ok:
            status = "partial_failure"
        else:
            status = "failed"

        _finish_nightly_sync_log(
            session_factory,
            log_id=nightly_log_id,
            status=status,
            records_processed=records_processed,
            error_message=" | ".join(errors)[:4000] if errors else None,
        )
        payload = {"status": status, "records_processed": records_processed}
        _notify_webhook(webhook_url, payload)
        return payload
    except Exception as exc:
        errors.append(f"nightly: {exc}")
        _finish_nightly_sync_log(
            session_factory,
            log_id=nightly_log_id,
            status="failed",
            records_processed=records_processed,
            error_message=" | ".join(errors)[:4000],
        )
        _notify_webhook(webhook_url, {"status": "failed", "records_processed": records_processed})
        raise
