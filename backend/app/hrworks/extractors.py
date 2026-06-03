from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.hrworks.periods import parse_iso_date


def minutes_to_hours(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        minutes = Decimal(str(value))
    except Exception:
        return Decimal("0")
    return (minutes / Decimal("60")).quantize(Decimal("0.01"))


def parse_working_times_by_email(payload: Any) -> dict[str, list[dict[str, Any]]]:
    """Normalize HRworks working-times payload keyed by lowercased email."""
    grouped: dict[str, list[dict[str, Any]]] = {}

    def _add(email: str, entries: Any) -> None:
        if not isinstance(entries, list):
            return
        key = email.strip().lower()
        if not key:
            return
        bucket = grouped.setdefault(key, [])
        bucket.extend(entry for entry in entries if isinstance(entry, dict))

    if isinstance(payload, dict):
        for email, entries in payload.items():
            if isinstance(email, str):
                _add(email, entries)
        return grouped

    if isinstance(payload, list):
        for block in payload:
            if not isinstance(block, dict):
                continue
            for email, entries in block.items():
                if isinstance(email, str):
                    _add(email, entries)
    return grouped


def extract_month_record(entry: dict[str, Any]) -> tuple[Any, Any, Decimal, Decimal] | None:
    begin_raw = entry.get("beginDate")
    end_raw = entry.get("endDate")
    if not isinstance(begin_raw, str) or not isinstance(end_raw, str):
        return None
    try:
        month_start = parse_iso_date(begin_raw)
        month_end = parse_iso_date(end_raw)
    except ValueError:
        return None
    planned = minutes_to_hours(entry.get("targetWorkingTimeMinutes"))
    clocked = minutes_to_hours(entry.get("workingTimeMinutes"))
    return month_start, month_end, planned, clocked
