from __future__ import annotations

import logging
from datetime import datetime, timezone
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
from app.services.jira_bug_collector import collect_jira_production_bugs
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


def _map_bugs_to_releases(db: Session) -> int:
    db.execute(delete(BugRelease))
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
    release_by_tag: dict[str, list[Release]] = {}
    for release in db.execute(select(Release)).scalars():
        if not release.tag_name:
            continue
        for key in _normalize_version_key(release.tag_name):
            release_by_tag.setdefault(key, []).append(release)
    mr_by_jira_key: dict[str, MergeRequest] = {}
    for mr in db.execute(select(MergeRequest)).scalars():
        if not mr.jira_key or mr.first_customer_tag_date is None:
            continue
        current = mr_by_jira_key.get(mr.jira_key)
        if current is None or mr.first_customer_tag_date < current.first_customer_tag_date:
            mr_by_jira_key[mr.jira_key] = mr

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
        merge_request = mr_by_jira_key.get(bug.jira_key)
        if merge_request is not None:
            fix_release_tag = merge_request.first_customer_tag
            fix_release_date = merge_request.first_customer_tag_date
            resolution_path = "mr_jira_key"
        else:
            for version in bug.fix_versions or []:
                candidate_releases: list[Release] = []
                for key in _normalize_version_key(version):
                    candidate_releases.extend(release_by_tag.get(key, []))
                for release in candidate_releases:
                    if fix_release_date is None or release.committed_at < fix_release_date:
                        fix_release_tag = release.tag_name
                        fix_release_date = release.committed_at
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


def _compute_lead_post_production(db: Session) -> int:
    processed = 0
    bug_by_jira_key = {
        bug.jira_key: bug for bug in db.execute(select(ProductionBug)).scalars() if bug.jira_key
    }
    for merge_request in db.execute(select(MergeRequest)).scalars():
        if not merge_request.jira_key:
            merge_request.lead_post_production_hours = None
            continue
        bug = bug_by_jira_key.get(merge_request.jira_key)
        if bug is None or bug.ready_for_qa_at is None or merge_request.merged_at < bug.ready_for_qa_at:
            merge_request.lead_post_production_hours = None
            processed += 1
            continue
        hours = (merge_request.merged_at - bug.ready_for_qa_at).total_seconds() / 3600.0
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

        if gitlab_ok and jira_ok:
            records_processed += _run_with_session(session_factory, _map_bugs_to_releases)
        elif gitlab_ok or jira_ok:
            logger.info("nightly_sync skipped bug_release mapping due to partial failure")

        if gitlab_ok and jira_ok:
            records_processed += _run_with_session(
                session_factory,
                lambda db: _resolve_mttr_alpha_fix_releases(db, effective_config),
            )
            records_processed += _run_with_session(session_factory, _compute_lead_post_production)
        else:
            logger.info("nightly_sync skipped mttr_alpha and lead_post_production due to partial failure")

        if gitlab_ok and jira_ok:
            records_processed += _run_with_session(
                session_factory, lambda db: _generate_snapshots(db, effective_config)
            )
        elif gitlab_ok or jira_ok:
            logger.info("nightly_sync skipped snapshots due to partial failure")

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
