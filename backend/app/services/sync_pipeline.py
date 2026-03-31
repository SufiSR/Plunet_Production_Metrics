from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import load_configuration
from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.sync_log import SyncLog
from app.services.gitlab_release_collector import collect_gitlab_tags_and_releases
from app.services.jira_bug_collector import collect_jira_production_bugs

logger = logging.getLogger(__name__)


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
    by_tag = {release.tag_name.lower(): release for release in releases if release.tag_name}
    processed = 0

    bugs = db.execute(select(ProductionBug)).scalars()
    for bug in bugs:
        affects_versions = [value.lower() for value in (bug.affects_versions or [])]
        for version in affects_versions:
            release = by_tag.get(version)
            if release is None:
                continue
            db.add(BugRelease(bug_id=bug.id, release_id=release.id))
            processed += 1
    db.commit()
    return processed


def _resolve_mttr_alpha_fix_releases(db: Session) -> int:
    processed = 0
    release_by_tag = {
        release.tag_name.lower(): release
        for release in db.execute(select(Release)).scalars()
        if release.tag_name
    }
    mr_by_jira_key = {
        mr.jira_key: mr for mr in db.execute(select(MergeRequest)).scalars() if mr.jira_key
    }

    bugs = db.execute(select(ProductionBug)).scalars()
    for bug in bugs:
        if not bug.healthy or bug.priority not in {"Critical", "Blocker"}:
            continue

        fix_release_tag = None
        fix_release_date = None
        resolution_path = None
        merge_request = mr_by_jira_key.get(bug.jira_key)
        if merge_request and merge_request.first_customer_tag_date is not None:
            fix_release_tag = merge_request.first_customer_tag
            fix_release_date = merge_request.first_customer_tag_date
            resolution_path = "mr"
        else:
            for version in bug.fix_versions or []:
                release = release_by_tag.get(version.lower()) or release_by_tag.get(
                    version.lower().lstrip("v")
                )
                if release is None:
                    continue
                if fix_release_date is None or release.committed_at < fix_release_date:
                    fix_release_tag = release.tag_name
                    fix_release_date = release.committed_at
                    resolution_path = "fix_version"

        bug.first_fix_release_tag = fix_release_tag
        bug.first_fix_release_date = fix_release_date
        bug.mttr_alpha_resolution_path = resolution_path
        if fix_release_date is not None and bug.created_at <= fix_release_date:
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


def _generate_snapshots(_: Session) -> int:
    # Story 9 owns snapshot metric content. Scheduler story guarantees orchestration hook and policy.
    return 0


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
    effective_config = config or load_configuration()
    gitlab_token = os.getenv("GITLAB_TOKEN", "")
    jira_token = os.getenv("JIRA_TOKEN", "")
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

        if gitlab_ok or jira_ok:
            records_processed += _run_with_session(session_factory, _map_bugs_to_releases)

        if gitlab_ok and jira_ok:
            records_processed += _run_with_session(session_factory, _resolve_mttr_alpha_fix_releases)
            records_processed += _run_with_session(session_factory, _compute_lead_post_production)
        else:
            logger.info("nightly_sync skipped mttr_alpha and lead_post_production due to partial failure")

        if gitlab_ok or jira_ok:
            records_processed += _run_with_session(session_factory, _generate_snapshots)

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
