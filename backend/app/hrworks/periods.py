from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True, slots=True)
class MonthWindow:
    month_start: date
    month_end: date

    @property
    def begin_date(self) -> str:
        return self.month_start.isoformat()

    @property
    def end_date(self) -> str:
        return self.month_end.isoformat()


def _month_end(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value.strip()[:10])


def first_day_of_month(value: date) -> date:
    return date(value.year, value.month, 1)


def current_month_start(*, today: date | None = None) -> date:
    ref = today or datetime.now(timezone.utc).date()
    return date(ref.year, ref.month, 1)


def iter_month_windows(start: date, end: date) -> list[MonthWindow]:
    if end < start:
        return []
    cursor = first_day_of_month(start)
    end_month = first_day_of_month(end)
    windows: list[MonthWindow] = []
    while cursor <= end_month:
        windows.append(
            MonthWindow(
                month_start=cursor,
                month_end=_month_end(cursor.year, cursor.month),
            )
        )
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return windows


HRWORKS_FULL_CALENDAR_YEARS = (2024, 2025)
HRWORKS_FORECAST_MONTHS = 6


def default_hrworks_sync_month_windows(*, today: date | None = None) -> list[MonthWindow]:
    """2024 and 2025, plus current year to date and the rolling forecast window."""
    ref = today or datetime.now(timezone.utc).date()
    seen: set[date] = set()
    windows: list[MonthWindow] = []

    def _append_range(start: date, end: date) -> None:
        for window in iter_month_windows(start, end):
            if window.month_start in seen:
                continue
            seen.add(window.month_start)
            windows.append(window)

    for year in HRWORKS_FULL_CALENDAR_YEARS:
        _append_range(date(year, 1, 1), date(year, 12, 1))
    current_month = first_day_of_month(ref)
    forecast_end = current_month
    for _ in range(HRWORKS_FORECAST_MONTHS):
        if forecast_end.month == 12:
            forecast_end = date(forecast_end.year + 1, 1, 1)
        else:
            forecast_end = date(forecast_end.year, forecast_end.month + 1, 1)
    _append_range(date(ref.year, 1, 1), forecast_end)
    return windows


def is_person_eligible_for_month(
    *,
    join_date: date | None,
    leave_date: date | None,
    month: MonthWindow,
) -> bool:
    """True when employment overlaps the calendar month window."""
    if join_date is not None and join_date > month.month_end:
        return False
    if leave_date is not None and leave_date < month.month_start:
        return False
    return True


def _shift_month_start(month_start: date, *, delta_months: int) -> date:
    """Move month_start by delta_months (negative = earlier)."""
    cursor = month_start
    steps = abs(delta_months)
    for _ in range(steps):
        if delta_months < 0:
            if cursor.month == 1:
                cursor = date(cursor.year - 1, 12, 1)
            else:
                cursor = date(cursor.year, cursor.month - 1, 1)
        else:
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)
    return cursor


def incremental_month_windows(
    *,
    past_months: int = 3,
    forecast_months: int = 6,
    today: date | None = None,
) -> list[MonthWindow]:
    """Rolling HRWorks window: N months before current, current month, M forecast months."""
    current = first_day_of_month(today or datetime.now(timezone.utc).date())
    start = _shift_month_start(current, delta_months=-max(past_months, 0))
    end = _shift_month_start(current, delta_months=max(forecast_months, 0))
    return iter_month_windows(start, end)
