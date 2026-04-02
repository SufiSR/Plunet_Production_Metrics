from __future__ import annotations

from datetime import date, datetime, timezone

from app.services.sync_data_floor import SYNC_MIN_DATE, sync_min_date_jql, sync_min_datetime_utc


def test_sync_min_date_is_2024_01_01() -> None:
    assert SYNC_MIN_DATE == date(2024, 1, 1)
    assert sync_min_date_jql() == "2024-01-01"


def test_sync_min_datetime_utc_midnight() -> None:
    dt = sync_min_datetime_utc()
    assert dt == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
