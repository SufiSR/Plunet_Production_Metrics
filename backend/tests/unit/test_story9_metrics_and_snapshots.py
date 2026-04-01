from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config_schema import ConfigurationSchema
from app.models.base import Base
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.metric_snapshot import MetricSnapshot
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.services.metric_service import (
    calculate_change_failure_rate,
    calculate_period_metrics,
    classify_performance_level,
)
from app.services.snapshot_service import refresh_snapshots


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_calculate_period_metrics_returns_expected_values() -> None:
    with _session() as db:
        db.add(Repository(id=1, gitlab_id=101, name="repo", path="ops/repo", default_branch="main", active=True))
        r1 = Release(
            id=1,
            repository_id=1,
            tag_name="v10.0.0",
            customer_release=True,
            commit_sha="a" * 40,
            committed_at=_utc(2026, 4, 6, 8, 0),
        )
        r2 = Release(
            id=2,
            repository_id=1,
            tag_name="v10.0.1",
            customer_release=True,
            commit_sha="b" * 40,
            committed_at=_utc(2026, 4, 7, 8, 0),
        )
        db.add_all([r1, r2])
        db.add(
            ProductionBug(
                id=10,
                jira_key="BUG-1",
                healthy=True,
                jira_created_at_valid=True,
                priority="Critical",
                created_at=_utc(2026, 4, 1),
                first_fix_release_date=_utc(2026, 4, 7, 8, 0),
                mttr_alpha_minutes=180,
            )
        )
        db.add(BugRelease(bug_id=10, release_id=2))
        db.add_all(
            [
                MergeRequest(
                    id=100,
                    repository_id=1,
                    gitlab_mr_id=11,
                    target_branch="main",
                    created_at=_utc(2026, 4, 1),
                    merged_at=_utc(2026, 4, 2),
                    first_customer_tag_date=_utc(2026, 4, 6, 8, 0),
                    lead_time_hours=Decimal("10.0"),
                    release_wait_time_hours=Decimal("2.0"),
                    lead_post_production_hours=Decimal("1.5"),
                ),
                MergeRequest(
                    id=101,
                    repository_id=1,
                    gitlab_mr_id=12,
                    target_branch="main",
                    created_at=_utc(2026, 4, 2),
                    merged_at=_utc(2026, 4, 3),
                    first_customer_tag_date=_utc(2026, 4, 7, 8, 0),
                    lead_time_hours=Decimal("14.0"),
                    release_wait_time_hours=Decimal("4.0"),
                    lead_post_production_hours=Decimal("2.5"),
                ),
            ]
        )
        db.commit()

        values = calculate_period_metrics(
            db,
            period_start=datetime(2026, 4, 6, tzinfo=timezone.utc).date(),
            period_end=datetime(2026, 4, 12, tzinfo=timezone.utc).date(),
            repository_id=1,
        )

    assert values.deployment_freq == Decimal("2.0000")
    assert values.lead_time_minutes == 720
    assert values.release_wait_median_minutes == 180
    assert values.change_failure_rate == Decimal("0.5000")
    assert values.mttr_alpha_minutes == 180
    assert values.lead_post_production_median_minutes == 120


def test_change_failure_rate_handles_no_releases_without_division_by_zero() -> None:
    with _session() as db:
        db.add(Repository(id=1, gitlab_id=101, name="repo", path="ops/repo", default_branch="main", active=True))
        db.commit()
        rate = calculate_change_failure_rate(
            db,
            start_dt=_utc(2026, 4, 1),
            end_dt=_utc(2026, 4, 2),
            repository_id=1,
        )
    assert rate == Decimal("0")


def test_refresh_snapshots_writes_rows_for_all_period_types() -> None:
    with _session() as db:
        db.add(Repository(id=1, gitlab_id=101, name="repo", path="ops/repo", default_branch="main", active=True))
        db.add(
            Release(
                id=1,
                repository_id=1,
                tag_name="v10.0.0",
                customer_release=True,
                commit_sha="a" * 40,
                committed_at=_utc(2026, 4, 2, 8, 0),
            )
        )
        db.commit()

        config = ConfigurationSchema.model_validate({"backend": {"lookback_days": 15}})
        written = refresh_snapshots(db, config=config, now=_utc(2026, 4, 15))

        rows = db.execute(select(MetricSnapshot)).scalars().all()
        types = {row.period_type for row in rows}

    assert written > 0
    assert len(rows) == written
    assert {"WEEK", "MONTH", "QUARTER"}.issubset(types)


def test_refresh_snapshots_uses_database_assigned_ids() -> None:
    with _session() as db:
        db.add(Repository(id=1, gitlab_id=101, name="repo", path="ops/repo", default_branch="main", active=True))
        db.add(
            Release(
                id=1,
                repository_id=1,
                tag_name="v10.0.0",
                customer_release=True,
                commit_sha="a" * 40,
                committed_at=_utc(2026, 4, 2, 8, 0),
            )
        )
        db.commit()

        config = ConfigurationSchema.model_validate({"backend": {"lookback_days": 15}})
        written = refresh_snapshots(db, config=config, now=_utc(2026, 4, 15))
        rows = db.execute(select(MetricSnapshot)).scalars().all()

    assert written == len(rows)
    ids = [row.id for row in rows]
    assert all(i is not None and i > 0 for i in ids)
    assert len(ids) == len(set(ids))


def test_merge_request_uses_updated_at_for_local_row_lifecycle() -> None:
    with _session() as db:
        db.add(Repository(id=1, gitlab_id=101, name="repo", path="ops/repo", default_branch="main", active=True))
        mr = MergeRequest(
            id=200,
            repository_id=1,
            gitlab_mr_id=99,
            target_branch="main",
            created_at=_utc(2026, 4, 1),  # GitLab event timestamp
            merged_at=_utc(2026, 4, 2),
        )
        db.add(mr)
        db.commit()
        db.refresh(mr)

    assert mr.updated_at is not None


def test_classify_performance_level_uses_worst_metric() -> None:
    level = classify_performance_level(
        deployment_freq_per_week=10.0,
        lead_time_minutes=45,
        change_failure_rate=0.20,
        mttr_minutes=30,
    )
    assert level == "LOW"
