"""Hard lower bounds for data sync scope (product policy)."""

from __future__ import annotations

from datetime import date, datetime, timezone

# Jira: issues with created < this date are never pulled.
# GitLab: merge requests merged before this date are ignored; MR commits before this
# date do not contribute to first_commit_at.
SYNC_MIN_DATE = date(2024, 1, 1)


def sync_min_datetime_utc() -> datetime:
    return datetime(
        SYNC_MIN_DATE.year,
        SYNC_MIN_DATE.month,
        SYNC_MIN_DATE.day,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )


def sync_min_date_jql() -> str:
    return SYNC_MIN_DATE.strftime("%Y-%m-%d")
