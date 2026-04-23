"""On-demand lead time breakdown by target branch and feature vs patch stream (DEVOPS-510)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.models.merge_request import MergeRequest
from app.models.repository import Repository
from app.services.metric_service import (
    _lead_time_mr_filters_for_repos,
    period_metric_bounds,
)


@dataclass(frozen=True)
class _MrLeadRow:
    target_branch: str
    lead_time_hours: Decimal | None
    release_wait_time_hours: Decimal | None
    first_customer_tag_date: datetime


def primary_feature_branch(config: ConfigurationSchema) -> str:
    branches = [b.strip() for b in config.gitlab.target_branches if b and str(b).strip()]
    if branches:
        return branches[0]
    return "master"


def change_stream_for_target_branch(
    target_branch: str, config: ConfigurationSchema
) -> str:
    """feature = primary line; patch = other configured lines; other = rest."""
    primary = primary_feature_branch(config)
    allowed = {b.strip() for b in config.gitlab.target_branches if b and str(b).strip()}
    allowed |= {b.strip() for b in config.gitlab.additional_merge_target_branches if b and str(b).strip()}
    tb = (target_branch or "").strip()
    if tb == primary:
        return "feature"
    if tb in allowed:
        return "patch"
    return "other"


def _median_minutes_from_hours(values: list[Decimal | None]) -> int | None:
    filtered = [float(v) * 60.0 for v in values if v is not None]
    if not filtered:
        return None
    return int(Decimal(str(median(filtered))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _median_dev_review_minutes_from_rows(
    rows: list[_MrLeadRow],
) -> int | None:
    dev: list[float] = []
    for r in rows:
        if r.lead_time_hours is None or r.release_wait_time_hours is None:
            continue
        delta = float(r.lead_time_hours) - float(r.release_wait_time_hours)
        if delta >= 0:
            dev.append(delta * 60.0)
    if not dev:
        return None
    return int(Decimal(str(median(dev))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _median_release_wait_from_rows(
    rows: list[_MrLeadRow],
) -> int | None:
    return _median_minutes_from_hours([r.release_wait_time_hours for r in rows])


def active_repository_ids(
    session: Session, *, repository_id: int | None
) -> list[int]:
    if repository_id is not None:
        return [repository_id]
    return [
        int(r[0])
        for r in session.execute(
            select(Repository.id).where(Repository.active.is_(True))
        ).all()
    ]


def fetch_lead_cohort_rows(
    session: Session,
    *,
    period_start: date,
    period_end: date,
    repository_ids: list[int],
    config: ConfigurationSchema,
) -> list[_MrLeadRow]:
    start_dt, end_dt = period_metric_bounds(period_start, period_end)
    if not repository_ids:
        return []
    flt = _lead_time_mr_filters_for_repos(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_ids=repository_ids,
        config=config,
    )
    rows = session.execute(
        select(
            MergeRequest.target_branch,
            MergeRequest.lead_time_hours,
            MergeRequest.release_wait_time_hours,
            MergeRequest.first_customer_tag_date,
        ).where(MergeRequest.lead_time_hours.is_not(None), *flt)
    ).all()
    out: list[_MrLeadRow] = []
    for tb, lt, rw, tag in rows:
        out.append(
            _MrLeadRow(
                target_branch=str(tb),
                lead_time_hours=lt,
                release_wait_time_hours=rw,
                first_customer_tag_date=tag,
            )
        )
    return out


def _window_bounds(w_start: date, w_end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(w_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(w_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


def fetch_lead_cohort_rows_range(
    session: Session,
    *,
    min_period_start: date,
    max_period_end: date,
    repository_ids: list[int],
    config: ConfigurationSchema,
) -> list[_MrLeadRow]:
    if not repository_ids:
        return []
    a = datetime.combine(min_period_start, time.min, tzinfo=timezone.utc)
    b = datetime.combine(max_period_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    flt = _lead_time_mr_filters_for_repos(
        start_dt=a,
        end_dt=b,
        repository_ids=repository_ids,
        config=config,
    )
    rows = session.execute(
        select(
            MergeRequest.target_branch,
            MergeRequest.lead_time_hours,
            MergeRequest.release_wait_time_hours,
            MergeRequest.first_customer_tag_date,
        ).where(MergeRequest.lead_time_hours.is_not(None), *flt)
    ).all()
    out: list[_MrLeadRow] = []
    for tb, lt, rw, tag in rows:
        out.append(
            _MrLeadRow(
                target_branch=str(tb),
                lead_time_hours=lt,
                release_wait_time_hours=rw,
                first_customer_tag_date=tag,
            )
        )
    return out


def _tag_in_window(tag: datetime, period_start: date, period_end: date) -> bool:
    t = tag
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    s, e = _window_bounds(period_start, period_end)
    return s <= t < e


def group_rows_by_period(
    rows: list[_MrLeadRow], period_start: date, period_end: date
) -> list[_MrLeadRow]:
    return [r for r in rows if _tag_in_window(r.first_customer_tag_date, period_start, period_end)]


def lead_time_bucket_dict(
    rows: list[_MrLeadRow],
    *,
    mode: str,
    config: ConfigurationSchema,
) -> dict[str, dict[str, int | None]]:
    """Keys -> {median_lead_time_minutes, sample_count, dev_review_median_minutes, release_wait_median_minutes}."""
    if mode == "branch":
        by_key: dict[str, list[_MrLeadRow]] = {}
        for r in rows:
            by_key.setdefault(r.target_branch, []).append(r)
        keys_sorted = sorted(by_key.keys(), key=lambda b: (b != primary_feature_branch(config), b))
    else:
        by_key = {"feature": [], "patch": [], "other": []}
        for r in rows:
            s = change_stream_for_target_branch(r.target_branch, config)
            by_key[s].append(r)
        keys_sorted = ["feature", "patch"]
        if by_key["other"]:
            keys_sorted.append("other")

    out: dict[str, dict[str, int | None]] = {}
    for k in keys_sorted:
        g = by_key.get(k) or []
        n = len(g)
        med = _median_minutes_from_hours([x.lead_time_hours for x in g]) if g else None
        dev_m = _median_dev_review_minutes_from_rows(g) if g else None
        rw_m = _median_release_wait_from_rows(g) if g else None
        out[k] = {
            "median_lead_time_minutes": med,
            "sample_count": n,
            "dev_review_median_minutes": dev_m,
            "release_wait_median_minutes": rw_m,
        }
    return out
