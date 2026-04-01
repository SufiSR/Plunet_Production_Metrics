from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.config_schema import ConfigurationSchema
from app.models.base import Base
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.services.sync_pipeline import (
    _compute_lead_post_production,
    _map_bugs_to_releases,
    _normalize_version_key,
    _resolve_mttr_alpha_fix_releases,
)


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_map_bugs_to_releases_normalizes_version_and_deduplicates_links() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add_all(
            [
                Release(
                    id=11,
                    repository_id=1,
                    tag_name="v10.1.0",
                    customer_release=True,
                    commit_sha="a" * 40,
                    committed_at=_utc(2026, 1, 10),
                ),
                Release(
                    id=12,
                    repository_id=1,
                    tag_name="10.2.0",
                    customer_release=True,
                    commit_sha="b" * 40,
                    committed_at=_utc(2026, 1, 20),
                ),
                ProductionBug(
                    id=21,
                    jira_key="DEVOPS-1",
                    summary="prod bug",
                    healthy=True,
                    priority="Critical",
                    created_at=_utc(2026, 1, 1),
                    affects_versions=["10.1.0", "v10.2.0", "10.2.0", "unknown"],
                ),
            ]
        )
        db.commit()

        processed = _map_bugs_to_releases(db)
        links = db.execute(select(BugRelease)).scalars().all()

    assert processed == 2
    assert len(links) == 2
    assert {(link.bug_id, link.release_id) for link in links} == {(21, 11), (21, 12)}


def test_resolve_mttr_alpha_uses_mr_then_fix_version_with_expected_path_labels() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add_all(
            [
                Release(
                    id=31,
                    repository_id=1,
                    tag_name="v10.5.1",
                    customer_release=True,
                    commit_sha="c" * 40,
                    committed_at=_utc(2026, 2, 5, 12, 0),
                ),
                MergeRequest(
                    id=41,
                    repository_id=1,
                    gitlab_mr_id=9001,
                    target_branch="10.x",
                    created_at=_utc(2026, 1, 5),
                    merged_at=_utc(2026, 1, 8),
                    jira_key="BUG-MR",
                    first_customer_tag="10.4.2",
                    first_customer_tag_date=_utc(2026, 1, 9, 8, 0),
                ),
                ProductionBug(
                    id=51,
                    jira_key="BUG-MR",
                    healthy=True,
                    priority="Critical",
                    created_at=_utc(2026, 1, 1),
                ),
                ProductionBug(
                    id=52,
                    jira_key="BUG-FIX",
                    healthy=True,
                    priority="Blocker",
                    created_at=_utc(2026, 2, 1),
                    fix_versions=["10.5.1"],
                ),
                ProductionBug(
                    id=53,
                    jira_key="BUG-NOT-ELIGIBLE",
                    healthy=True,
                    priority="Major",
                    created_at=_utc(2026, 2, 1),
                    fix_versions=["10.5.1"],
                ),
            ]
        )
        db.commit()

        processed = _resolve_mttr_alpha_fix_releases(db, ConfigurationSchema())
        mr_bug = db.get(ProductionBug, 51)
        fix_bug = db.get(ProductionBug, 52)
        not_eligible_bug = db.get(ProductionBug, 53)

    assert processed == 2
    assert mr_bug is not None
    assert mr_bug.mttr_alpha_resolution_path == "mr_jira_key"
    assert mr_bug.first_fix_release_tag == "10.4.2"
    assert mr_bug.mttr_alpha_minutes == 12000

    assert fix_bug is not None
    assert fix_bug.mttr_alpha_resolution_path == "fix_version"
    assert fix_bug.first_fix_release_tag == "v10.5.1"
    assert fix_bug.mttr_alpha_minutes == 6480

    assert not_eligible_bug is not None
    assert not_eligible_bug.mttr_alpha_resolution_path is None
    assert not_eligible_bug.mttr_alpha_minutes is None


def test_compute_lead_post_production_handles_valid_and_invalid_intervals() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add_all(
            [
                ProductionBug(
                    id=61,
                    jira_key="BUG-LEAD-OK",
                    healthy=True,
                    priority="Critical",
                    created_at=_utc(2026, 2, 1),
                    ready_for_qa_at=_utc(2026, 2, 3, 9, 0),
                ),
                ProductionBug(
                    id=62,
                    jira_key="BUG-LEAD-INVALID",
                    healthy=True,
                    priority="Critical",
                    created_at=_utc(2026, 2, 1),
                    ready_for_qa_at=_utc(2026, 2, 4, 9, 0),
                ),
                MergeRequest(
                    id=71,
                    repository_id=1,
                    gitlab_mr_id=8001,
                    target_branch="10.x",
                    created_at=_utc(2026, 2, 1),
                    merged_at=_utc(2026, 2, 3, 15, 30),
                    jira_key="BUG-LEAD-OK",
                ),
                MergeRequest(
                    id=72,
                    repository_id=1,
                    gitlab_mr_id=8002,
                    target_branch="10.x",
                    created_at=_utc(2026, 2, 1),
                    merged_at=_utc(2026, 2, 4, 8, 0),
                    jira_key="BUG-LEAD-INVALID",
                ),
            ]
        )
        db.commit()

        processed = _compute_lead_post_production(db, lookback_days=730)
        mr_ok = db.get(MergeRequest, 71)
        mr_invalid = db.get(MergeRequest, 72)

    assert processed == 1
    assert mr_ok is not None
    assert float(mr_ok.lead_post_production_hours) == 6.5
    assert mr_invalid is not None
    assert mr_invalid.lead_post_production_hours is None


def test_resolve_mttr_alpha_picks_earliest_mr_tag_date_for_same_jira_key() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add_all(
            [
                MergeRequest(
                    id=81,
                    repository_id=1,
                    gitlab_mr_id=7001,
                    target_branch="10.x",
                    created_at=_utc(2026, 2, 1),
                    merged_at=_utc(2026, 2, 2),
                    jira_key="BUG-DUP-MR",
                    first_customer_tag="10.6.1",
                    first_customer_tag_date=_utc(2026, 2, 10),
                ),
                MergeRequest(
                    id=82,
                    repository_id=1,
                    gitlab_mr_id=7002,
                    target_branch="10.x",
                    created_at=_utc(2026, 2, 1),
                    merged_at=_utc(2026, 2, 2),
                    jira_key="BUG-DUP-MR",
                    first_customer_tag="10.6.0",
                    first_customer_tag_date=_utc(2026, 2, 8),
                ),
                ProductionBug(
                    id=83,
                    jira_key="BUG-DUP-MR",
                    healthy=True,
                    priority="Critical",
                    created_at=_utc(2026, 2, 1),
                ),
            ]
        )
        db.commit()

        _resolve_mttr_alpha_fix_releases(db, ConfigurationSchema())
        bug = db.get(ProductionBug, 83)

    assert bug is not None
    assert bug.first_fix_release_tag == "10.6.0"
    assert bug.first_fix_release_date is not None
    assert bug.first_fix_release_date.date().isoformat() == "2026-02-08"
    assert bug.mttr_alpha_resolution_path == "mr_jira_key"


def test_compute_lead_post_production_clears_stale_value_when_jira_key_missing() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="repo",
                path="operations/dora-metrics",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        stale = MergeRequest(
            id=91,
            repository_id=1,
            gitlab_mr_id=6001,
            target_branch="10.x",
            created_at=_utc(2026, 2, 1),
            merged_at=_utc(2026, 2, 2),
            jira_key=None,
            lead_post_production_hours=1.23,
        )
        db.add(stale)
        db.commit()

        _compute_lead_post_production(db, lookback_days=730)
        refreshed = db.get(MergeRequest, 91)

    assert refreshed is not None
    assert refreshed.lead_post_production_hours is None


def test_normalize_version_key_ignores_empty_bare_v_variant() -> None:
    assert _normalize_version_key("v") == {"v"}
