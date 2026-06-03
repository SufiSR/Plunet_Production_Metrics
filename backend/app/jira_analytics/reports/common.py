from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jira_analytics.models import MonthlyAllocatedEffort, MonthlyTopicEffortBase
from app.jira_analytics.project_scope import scope_monthly_allocated_effort


def parse_period(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    return date.fromisoformat(value.strip()[:10])


def allocated_query(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
    feature_key: str | None,
):
    stmt = select(MonthlyAllocatedEffort)
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    if team:
        stmt = stmt.where(MonthlyAllocatedEffort.team_name == team)
    if feature_key:
        stmt = stmt.where(MonthlyAllocatedEffort.feature_key == feature_key)
    return scope_monthly_allocated_effort(stmt)


def sum_hours(rows: list) -> float:
    return float(sum(Decimal(r.hours) for r in rows))
