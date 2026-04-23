from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.metric_snapshot import MetricSnapshot
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.models.sync_log import SyncLog
from app.services.config_service import load_runtime_config
from app.services.gitlab_release_collector import collect_gitlab_tags_and_releases
from app.services.jira_bug_collector import (
    collect_jira_production_bugs,
    hydrate_merge_request_jira_ready_for_qa,
)
from app.services.snapshot_service import refresh_snapshots
from app.services.webhook_service import build_webhook_payload, send_webhook_notification

logger = logging.getLogger(__name__)

PIPELINE_PHASES: tuple[str, ...] = ("gitlab", "jira", "derivations", "snapshots", "complete")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_pipeline_runtime(*, trigger: str) -> dict[str, Any]:
    now_iso = _utc_now_iso()
    return {
        "current_phase": "queued",
        "phase_started_at": now_iso,
        "trigger": trigger,
        "phases": {
            phase: {
                "status": "pending",
                "message": None,
                "records_processed": {},
                "started_at": None,
                "finished_at": None,
                "duration_seconds": None,
            }
            for phase in PIPELINE_PHASES
        },
        "errors": [],
    }


def _transition_runtime_phase(
    runtime: dict[str, Any],
    *,
    current_phase: str,
    phase: str,
    status: str,
    message: str | None = None,
    records_processed: dict[str, int] | None = None,
) -> None:
    now_iso = _utc_now_iso()
    runtime["current_phase"] = current_phase
    runtime["phase_started_at"] = now_iso
    phases = runtime.setdefault("phases", {})
    phase_block = phases.setdefault(
        phase,
        {
            "status": "pending",
            "message": None,
            "records_processed": {},
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
        },
    )
    previous_started_at = phase_block.get("started_at")
    if status == "running" and previous_started_at is None:
        phase_block["started_at"] = now_iso
    if status in {"success", "failed", "skipped"}:
        if previous_started_at is None:
            phase_block["started_at"] = now_iso
        phase_block["finished_at"] = now_iso
        try:
            started_dt = datetime.fromisoformat(str(phase_block["started_at"]).replace("Z", "+00:00"))
            finished_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
            phase_block["duration_seconds"] = int((finished_dt - started_dt).total_seconds())
        except (ValueError, TypeError):
            phase_block["duration_seconds"] = None
    if message is not None:
        phase_block["message"] = message[:400]
    if records_processed is not None:
        phase_block["records_processed"] = records_processed
    phase_block["status"] = status


def _append_runtime_error(runtime: dict[str, Any], error_message: str) -> None:
    errors = runtime.setdefault("errors", [])
    errors.append(error_message[:400])


def _update_nightly_sync_log_details(
    session_factory: Callable[[], Session],
    *,
    log_id: int,
    details_json: dict[str, Any],
) -> int:
    def _update(db: Session) -> int:
        if db is None:
            return 0
        row = db.get(SyncLog, log_id)
        if row is None:
            return 0
        existing = row.details_json if isinstance(row.details_json, dict) else {}
        merged = {**existing, **details_json}
        row.details_json = merged
        db.commit()
        return 0

    return _run_with_session(session_factory, _update)


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


def _create_nightly_sync_log(
    session_factory: Callable[[], Session],
    *,
    trigger: str = "scheduled",
) -> int:
    def _create(db: Session) -> int:
        started_at = datetime.now(timezone.utc)
        row = SyncLog(
            source="nightly",
            started_at=started_at,
            status="running",
            details_json={
                "trigger": trigger,
                "pipeline_runtime": _new_pipeline_runtime(trigger=trigger),
            },
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
    details_json: dict[str, Any] | None = None,
) -> int:
    def _finish(db: Session) -> int:
        row = db.get(SyncLog, log_id)
        if row is not None:
            row.status = status
            row.finished_at = datetime.now(timezone.utc)
            row.records_processed = records_processed
            row.error_message = error_message
            row.details_json = details_json
            db.commit()
        return 0

    return _run_with_session(session_factory, _finish)


def _gitlab_table_counts(db: Session) -> dict[str, int]:
    repos = int(
        db.scalar(select(func.count()).select_from(Repository).where(Repository.active.is_(True)))
        or 0
    )
    releases = int(db.scalar(select(func.count()).select_from(Release)) or 0)
    mrs = int(db.scalar(select(func.count()).select_from(MergeRequest)) or 0)
    enriched = int(
        db.scalar(
            select(func.count()).select_from(MergeRequest).where(MergeRequest.first_commit_at.isnot(None))
        )
        or 0
    )
    return {
        "repositories": repos,
        "releases": releases,
        "merge_requests": mrs,
        "merge_requests_first_commit_enriched": enriched,
    }


def _jira_table_counts(db: Session) -> dict[str, int]:
    bugs = int(db.scalar(select(func.count()).select_from(ProductionBug)) or 0)
    mttr_alpha = int(
        db.scalar(
            select(func.count()).select_from(ProductionBug).where(
                ProductionBug.mttr_alpha_minutes.isnot(None)
            )
        )
        or 0
    )
    return {"bugs": bugs, "mttr_alpha_resolved": mttr_alpha}


def _max_metric_snapshot_created_at(db: Session) -> datetime | None:
    return db.scalar(select(func.max(MetricSnapshot.created_at)))


def _read_nightly_log_started_at(db: Session, log_id: int) -> datetime:
    row = db.get(SyncLog, log_id)
    if row is None or row.started_at is None:
        return datetime.now(timezone.utc)
    return row.started_at


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
    null_count = 0
    lookback_start = _lookback_start_utc(lookback_days)
    bug_by_jira_key = {
        bug.jira_key: bug for bug in db.execute(select(ProductionBug)).scalars() if bug.jira_key
    }
    db.execute(
        update(MergeRequest)
        .where(
            MergeRequest.merged_at >= lookback_start,
            MergeRequest.jira_key.is_(None),
            MergeRequest.lead_post_production_hours.isnot(None),
        )
        .values(lead_post_production_hours=None)
    )
    merge_requests = db.execute(
        select(MergeRequest).where(
            MergeRequest.merged_at >= lookback_start,
            MergeRequest.jira_key.isnot(None),
        )
    ).scalars()
    for merge_request in merge_requests:
        bug = bug_by_jira_key.get(merge_request.jira_key)
        ready_at = bug.ready_for_qa_at if bug is not None else None
        if ready_at is None:
            ready_at = merge_request.jira_ready_for_qa_at
        if ready_at is None or merge_request.merged_at < ready_at:
            merge_request.lead_post_production_hours = None
            null_count += 1
            continue
        hours = (merge_request.merged_at - ready_at).total_seconds() / 3600.0
        merge_request.lead_post_production_hours = Decimal(str(hours)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        processed += 1
    db.commit()
    logger.info(
        "lead_post_production completed",
        extra={"computed": processed, "null_result": null_count},
    )
    return processed


def _generate_snapshots(db: Session, config: ConfigurationSchema) -> int:
    return refresh_snapshots(db, config=config)


def _resolve_orphaned_sync_logs(session_factory: Callable[[], Session]) -> None:
    def _resolve(db: Session) -> int:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=4)
        db.execute(
            update(SyncLog)
            .where(SyncLog.status == "running", SyncLog.started_at < threshold)
            .values(
                status="crashed",
                finished_at=now,
                error_message="Resolved as crashed: process did not complete",
            )
        )
        latest_finished = db.scalar(
            select(func.max(SyncLog.finished_at)).where(
                SyncLog.source == "nightly",
                SyncLog.status != "running",
                SyncLog.finished_at.isnot(None),
            )
        )
        if latest_finished is not None:
            db.execute(
                update(SyncLog)
                .where(
                    SyncLog.source == "nightly",
                    SyncLog.status == "running",
                    SyncLog.started_at < latest_finished,
                )
                .values(
                    status="crashed",
                    finished_at=latest_finished,
                    error_message=(
                        "Stale running entry: a later nightly sync already finished "
                        "(abandoned worker or restart)"
                    ),
                )
            )
        db.commit()
        return 0

    _run_with_session(session_factory, _resolve)


def reconcile_nightly_runs_on_app_startup(
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Reconcile `sync_log` so the UI and scheduler match reality after a process start.

    Orphan resolution (``_resolve_orphaned_sync_logs``) normally runs only when
    :func:`run_nightly_sync` starts, so a crash mid-sync can leave a row stuck in
    ``status=running`` until the next run—making restarts look like a sync is still
    in progress. We run the same time-based and duplicate-finish cleanup on every
    app boot, then (unless disabled) mark any *remaining* ``nightly``+``running``
    rows as interrupted: a fresh process is not still executing a prior in-memory
    pipeline in the typical single-server deployment.

    Set ``DORA_SKIP_STARTUP_SYNC_RECONCILE=1`` (or ``true``) to skip the final
    "mark still-running" step when multiple backend instances share the database.
    """
    _resolve_orphaned_sync_logs(session_factory)
    if (os.getenv("DORA_SKIP_STARTUP_SYNC_RECONCILE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return

    def _mark_interrupted(db: Session) -> int:
        now = datetime.now(timezone.utc)
        result = db.execute(
            update(SyncLog)
            .where(SyncLog.source == "nightly", SyncLog.status == "running")
            .values(
                status="crashed",
                finished_at=now,
                error_message=(
                    "Interrupted: server or worker restarted before the pipeline finished "
                    "(startup reconciliation)"
                ),
            )
        )
        if result.rowcount and int(result.rowcount) > 0:
            logger.info(
                "startup_sync_reconciliation marked %s stuck nightly run(s) as crashed",
                result.rowcount,
            )
        db.commit()
        return 0

    _run_with_session(session_factory, _mark_interrupted)


def run_nightly_sync(
    *,
    config: ConfigurationSchema | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    trigger: str = "scheduled",
) -> dict[str, str | int]:
    logger.info("sync_pipeline starting trigger=%s", trigger)
    _resolve_orphaned_sync_logs(session_factory)
    with session_factory() as config_db:
        runtime_config = load_runtime_config(db=config_db)
    effective_config = config or runtime_config.settings
    gitlab_token = runtime_config.gitlab_token
    jira_token = runtime_config.jira_token
    jira_user_email = runtime_config.jira_user_email
    webhook_url = effective_config.notifications.webhook_url
    nightly_log_id = _create_nightly_sync_log(session_factory, trigger=trigger)
    pipeline_runtime = _new_pipeline_runtime(trigger=trigger)
    _update_nightly_sync_log_details(
        session_factory,
        log_id=nightly_log_id,
        details_json={"pipeline_runtime": pipeline_runtime},
    )
    logger.info(
        "sync_pipeline sync_log_id=%s trigger=%s phase=collectors (gitlab, jira)",
        nightly_log_id,
        trigger,
    )

    gitlab_ok = False
    jira_ok = False
    records_processed = 0
    snapshots_written = 0
    errors: list[str] = []

    try:
        _transition_runtime_phase(
            pipeline_runtime,
            current_phase="gitlab",
            phase="gitlab",
            status="running",
            message="GitLab collector started",
        )
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )
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
                _transition_runtime_phase(
                    pipeline_runtime,
                    current_phase="gitlab",
                    phase="gitlab",
                    status="success",
                    message="GitLab collector finished",
                )
            except Exception as exc:
                errors.append(f"gitlab: {exc}")
                _append_runtime_error(pipeline_runtime, f"gitlab: {exc}")
                _transition_runtime_phase(
                    pipeline_runtime,
                    current_phase="gitlab",
                    phase="gitlab",
                    status="failed",
                    message="GitLab collector failed",
                )
                logger.exception("nightly_sync gitlab collector failed")
        else:
            msg = "GitLab API token is not configured (GITLAB_TOKEN / GITLAB_API_TOKEN)"
            errors.append(f"gitlab: {msg}")
            _append_runtime_error(pipeline_runtime, f"gitlab: {msg}")
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="gitlab",
                phase="gitlab",
                status="skipped",
                message="GitLab collector skipped: token missing",
            )
            logger.error("nightly_sync skipped gitlab: %s", msg)
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )

        logger.info(
            "sync_pipeline sync_log_id=%s trigger=%s phase=gitlab_done ok=%s",
            nightly_log_id,
            trigger,
            gitlab_ok,
        )

        _transition_runtime_phase(
            pipeline_runtime,
            current_phase="jira",
            phase="jira",
            status="running",
            message="Jira collector started",
        )
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )
        if (jira_token or "").strip():
            logger.info(
                "sync_pipeline sync_log_id=%s trigger=%s phase=jira_start "
                "(paginated JQL search then per-issue changelog/worklogs; may take minutes)",
                nightly_log_id,
                trigger,
            )
            try:
                records_processed += _run_with_session(
                    session_factory,
                    lambda db: collect_jira_production_bugs(
                        db,
                        config=effective_config,
                        jira_token=jira_token,
                        jira_user_email=jira_user_email,
                    ),
                )
                jira_ok = True
                _transition_runtime_phase(
                    pipeline_runtime,
                    current_phase="jira",
                    phase="jira",
                    status="success",
                    message="Jira collector finished",
                )
            except Exception as exc:
                errors.append(f"jira: {exc}")
                _append_runtime_error(pipeline_runtime, f"jira: {exc}")
                _transition_runtime_phase(
                    pipeline_runtime,
                    current_phase="jira",
                    phase="jira",
                    status="failed",
                    message="Jira collector failed",
                )
                logger.exception("nightly_sync jira collector failed")
        else:
            msg = "Jira API token is not configured (JIRA_TOKEN / JIRA_API_TOKEN)"
            errors.append(f"jira: {msg}")
            _append_runtime_error(pipeline_runtime, f"jira: {msg}")
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="jira",
                phase="jira",
                status="skipped",
                message="Jira collector skipped: token missing",
            )
            logger.error("nightly_sync skipped jira: %s", msg)
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )

        logger.info(
            "sync_pipeline sync_log_id=%s trigger=%s phase=jira_done ok=%s",
            nightly_log_id,
            trigger,
            jira_ok,
        )

        derivation_errors: list[str] = []
        if gitlab_ok and jira_ok:
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="derivations",
                phase="derivations",
                status="running",
                message="Derivation steps running",
            )
        else:
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="derivations",
                phase="derivations",
                status="skipped",
                message="Skipped because both collectors are not successful",
            )
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )

        if gitlab_ok and jira_ok:
            try:
                records_processed += _run_with_session(session_factory, _map_bugs_to_releases)
            except Exception as exc:
                derivation_errors.append(f"map_bugs_to_releases: {exc}")
                logger.exception("nightly_sync map_bugs_to_releases failed")
        elif gitlab_ok or jira_ok:
            logger.info("nightly_sync skipped bug_release mapping due to partial failure")

        if gitlab_ok and jira_ok:
            try:
                records_processed += _run_with_session(
                    session_factory,
                    lambda db: _resolve_mttr_alpha_fix_releases(db, effective_config),
                )
            except Exception as exc:
                derivation_errors.append(f"mttr_alpha: {exc}")
                logger.exception("nightly_sync mttr_alpha resolution failed")
            try:
                records_processed += _run_with_session(
                    session_factory,
                    lambda db: hydrate_merge_request_jira_ready_for_qa(
                        db,
                        config=effective_config,
                        jira_token=jira_token,
                        jira_user_email=jira_user_email,
                    ),
                )
            except Exception as exc:
                derivation_errors.append(f"hydrate_jira_rfq: {exc}")
                logger.exception("nightly_sync jira_ready_for_qa hydration failed")
            try:
                records_processed += _run_with_session(
                    session_factory,
                    lambda db: _compute_lead_post_production(
                        db, lookback_days=effective_config.backend.lookback_days
                    ),
                )
            except Exception as exc:
                derivation_errors.append(f"lead_post_production: {exc}")
                logger.exception("nightly_sync lead_post_production failed")
        else:
            logger.info(
                "nightly_sync skipped mttr_alpha, jira_ready_for_qa hydrate, "
                "and lead_post_production due to partial failure"
            )

        errors.extend(derivation_errors)
        if gitlab_ok and jira_ok:
            if derivation_errors:
                _append_runtime_error(pipeline_runtime, "; ".join(derivation_errors))
                _transition_runtime_phase(
                    pipeline_runtime,
                    current_phase="derivations",
                    phase="derivations",
                    status="failed",
                    message="One or more derivation steps failed",
                )
            else:
                _transition_runtime_phase(
                    pipeline_runtime,
                    current_phase="derivations",
                    phase="derivations",
                    status="success",
                    message="Derivation steps finished",
                )
            _update_nightly_sync_log_details(
                session_factory,
                log_id=nightly_log_id,
                details_json={"pipeline_runtime": pipeline_runtime},
            )

        if gitlab_ok or jira_ok:
            if derivation_errors:
                logger.warning(
                    "nightly_sync generating snapshots despite derivation errors: %s",
                    "; ".join(derivation_errors),
                )
            logger.info(
                "sync_pipeline sync_log_id=%s trigger=%s phase=snapshots",
                nightly_log_id,
                trigger,
            )
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="snapshots",
                phase="snapshots",
                status="running",
                message="Snapshot generation started",
            )
            _update_nightly_sync_log_details(
                session_factory,
                log_id=nightly_log_id,
                details_json={"pipeline_runtime": pipeline_runtime},
            )
            snapshots_written = _run_with_session(
                session_factory, lambda db: _generate_snapshots(db, effective_config)
            )
            records_processed += snapshots_written
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="snapshots",
                phase="snapshots",
                status="success",
                message="Snapshot generation finished",
                records_processed={"snapshots_generated": snapshots_written},
            )
        else:
            logger.info("nightly_sync skipped snapshots: both collectors failed or were skipped")
            _transition_runtime_phase(
                pipeline_runtime,
                current_phase="snapshots",
                phase="snapshots",
                status="skipped",
                message="Skipped because both collectors failed or were skipped",
            )
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )

        if gitlab_ok and jira_ok:
            status = "success"
        elif gitlab_ok or jira_ok:
            status = "partial_failure"
        else:
            status = "failed"

        gitlab_records: dict[str, int] = {}
        if (gitlab_token or "").strip():
            gitlab_records = _run_with_session(session_factory, _gitlab_table_counts)
        jira_records: dict[str, int] = {}
        if (jira_token or "").strip():
            jira_records = _run_with_session(session_factory, _jira_table_counts)

        snapshot_generated_at: datetime | None = None
        if snapshots_written > 0:
            snapshot_generated_at = _run_with_session(
                session_factory, _max_metric_snapshot_created_at
            )

        started_at = _run_with_session(
            session_factory,
            lambda db: _read_nightly_log_started_at(db, nightly_log_id),
        )
        finished_at = datetime.now(timezone.utc)
        duration_seconds = int((finished_at - started_at).total_seconds())

        details_json: dict[str, Any] = {
            "trigger": trigger,
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
            "duration_seconds": duration_seconds,
            "status": status,
            "collectors": {
                "gitlab": {
                    "status": "SUCCESS" if gitlab_ok else "FAILED",
                    "records_processed": gitlab_records,
                },
                "jira": {
                    "status": "SUCCESS" if jira_ok else "FAILED",
                    "records_processed": jira_records,
                },
            },
            "snapshots_generated": snapshots_written,
            "snapshot_generated_at": (
                snapshot_generated_at.isoformat().replace("+00:00", "Z")
                if snapshot_generated_at
                else None
            ),
            "pipeline_runtime": pipeline_runtime,
        }
        _transition_runtime_phase(
            pipeline_runtime,
            current_phase="finished",
            phase="complete",
            status="success" if status != "failed" else "failed",
            message="Pipeline finished",
            records_processed={"total_records_processed": records_processed},
        )
        details_json["pipeline_runtime"] = pipeline_runtime

        _finish_nightly_sync_log(
            session_factory,
            log_id=nightly_log_id,
            status=status,
            records_processed=records_processed,
            error_message=" | ".join(errors)[:4000] if errors else None,
            details_json=details_json,
        )
        logger.info(
            "sync_pipeline finished sync_log_id=%s trigger=%s status=%s records_processed=%s snapshots=%s",
            nightly_log_id,
            trigger,
            status,
            records_processed,
            snapshots_written,
        )
        event = {
            "success": "SYNC_SUCCESS",
            "partial_failure": "SYNC_PARTIAL_FAILURE",
            "failed": "SYNC_COMPLETE_FAILURE",
        }[status]
        payload = build_webhook_payload(
            event=event,
            status=status,
            trigger=trigger,
            records_processed=records_processed,
            details_json=details_json,
            errors=errors,
        )
        delivered = send_webhook_notification(webhook_url, payload)
        if webhook_url and not delivered:
            logger.error("nightly_sync webhook notification failed")
        return payload
    except Exception as exc:
        errors.append(f"nightly: {exc}")
        _append_runtime_error(pipeline_runtime, f"nightly: {exc}")
        _transition_runtime_phase(
            pipeline_runtime,
            current_phase="failed",
            phase="complete",
            status="failed",
            message="Pipeline crashed",
        )
        _update_nightly_sync_log_details(
            session_factory,
            log_id=nightly_log_id,
            details_json={"pipeline_runtime": pipeline_runtime},
        )
        finished_at = datetime.now(timezone.utc)

        started_at_exc = _run_with_session(
            session_factory,
            lambda db: _read_nightly_log_started_at(db, nightly_log_id),
        )
        duration_exc = int((finished_at - started_at_exc).total_seconds())
        failure_details: dict[str, Any] = {
            "trigger": trigger,
            "started_at": started_at_exc.isoformat().replace("+00:00", "Z"),
            "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
            "duration_seconds": duration_exc,
            "status": "failed",
            "collectors": {
                "gitlab": {"status": "FAILED", "records_processed": {}},
                "jira": {"status": "FAILED", "records_processed": {}},
            },
            "snapshots_generated": 0,
            "snapshot_generated_at": None,
            "pipeline_runtime": pipeline_runtime,
        }
        _finish_nightly_sync_log(
            session_factory,
            log_id=nightly_log_id,
            status="failed",
            records_processed=records_processed,
            error_message=" | ".join(errors)[:4000],
            details_json=failure_details,
        )
        logger.error(
            "sync_pipeline crashed sync_log_id=%s trigger=%s",
            nightly_log_id,
            trigger,
            exc_info=True,
        )
        payload = build_webhook_payload(
            event="SYNC_COMPLETE_FAILURE",
            status="failed",
            trigger=trigger,
            records_processed=records_processed,
            details_json=failure_details,
            errors=errors,
        )
        delivered = send_webhook_notification(webhook_url, payload)
        if webhook_url and not delivered:
            logger.error("nightly_sync webhook notification failed")
        raise
