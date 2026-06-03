from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.hrworks.client import HrworksClient
from app.hrworks.person_mapping import (
    build_hrworks_person_lookup,
    load_jira_users_with_email,
    to_hrworks_person_email,
)
from app.hrworks.periods import MonthWindow, is_person_eligible_for_month, parse_iso_date
from app.jira_analytics.models import HrworksPersonRoster

logger = logging.getLogger(__name__)

MASTER_DATA_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class ParsedHrworksPerson:
    person_id: str
    hrworks_uuid: str | None
    personnel_number: str | None
    business_email: str | None
    first_name: str | None
    last_name: str | None
    join_date: date | None
    leave_date: date | None
    is_active: bool


@dataclass(slots=True)
class RosterRefreshCounts:
    persons_fetched: int = 0
    persons_upserted: int = 0
    persons_removed: int = 0
    mapped_to_jira: int = 0
    skipped_denied: int = 0
    refreshed: bool = False


def parse_master_data_person(raw: dict[str, Any]) -> ParsedHrworksPerson | None:
    person_id = raw.get("personId")
    if not isinstance(person_id, str) or not person_id.strip():
        return None
    join_date = _parse_optional_date(raw.get("joinDate"))
    leave_date = _parse_optional_date(raw.get("leaveDate"))
    email = raw.get("email")
    business_email = email.strip().lower() if isinstance(email, str) and email.strip() else None
    return ParsedHrworksPerson(
        person_id=person_id.strip().lower(),
        hrworks_uuid=_optional_str(raw.get("uuid")),
        personnel_number=_optional_str(raw.get("personnelNumber")),
        business_email=business_email,
        first_name=_optional_str(raw.get("firstName")),
        last_name=_optional_str(raw.get("lastName")),
        join_date=join_date,
        leave_date=leave_date,
        is_active=bool(raw.get("isActive", True)),
    )


def _parse_optional_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return parse_iso_date(value)


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _denied_person_ids(config: ConfigurationSchema) -> set[str]:
    return {item.strip().lower() for item in config.hrworks.denied_person_ids if item.strip()}


def roster_is_stale(db: Session, *, max_age_hours: int) -> bool:
    count = db.execute(select(func.count()).select_from(HrworksPersonRoster)).scalar_one()
    if int(count) == 0:
        return True
    latest = db.execute(select(func.max(HrworksPersonRoster.synced_at))).scalar_one()
    if latest is None:
        return True
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
    return age_hours >= max_age_hours


def refresh_hrworks_person_roster(
    db: Session,
    client: HrworksClient,
    *,
    config: ConfigurationSchema,
    force: bool = False,
) -> RosterRefreshCounts:
    counts = RosterRefreshCounts()
    if not force and not roster_is_stale(db, max_age_hours=config.hrworks.roster_refresh_hours):
        counts.mapped_to_jira = _count_mapped_roster(db)
        counts.persons_fetched = int(
            db.execute(select(func.count()).select_from(HrworksPersonRoster)).scalar_one()
        )
        logger.info(
            "HRworks roster cache still fresh (mapped_to_jira=%s)",
            counts.mapped_to_jira,
        )
        return counts

    sync_started = datetime.now(timezone.utc)
    persons_raw = client.fetch_all_person_master_data(only_active=False)
    counts.persons_fetched = len(persons_raw)
    counts.refreshed = True

    jira_users = load_jira_users_with_email(db)
    jira_lookup = build_hrworks_person_lookup(jira_users)
    denied = _denied_person_ids(config)

    seen_person_ids: set[str] = set()
    for raw in persons_raw:
        if not isinstance(raw, dict):
            continue
        parsed = parse_master_data_person(raw)
        if parsed is None:
            continue
        if parsed.person_id in denied:
            counts.skipped_denied += 1
            continue
        seen_person_ids.add(parsed.person_id)
        jira_user_id = _resolve_jira_user_id(parsed, jira_lookup)
        if jira_user_id is not None:
            counts.mapped_to_jira += 1
        _upsert_roster_row(db, parsed, jira_user_id=jira_user_id, synced_at=sync_started)
        counts.persons_upserted += 1

    if seen_person_ids:
        removed = db.execute(
            delete(HrworksPersonRoster).where(
                HrworksPersonRoster.person_id.not_in(sorted(seen_person_ids))
            )
        )
        counts.persons_removed = int(removed.rowcount or 0)
    db.commit()
    logger.info(
        "HRworks roster refreshed: fetched=%s upserted=%s removed=%s mapped_jira=%s denied=%s",
        counts.persons_fetched,
        counts.persons_upserted,
        counts.persons_removed,
        counts.mapped_to_jira,
        counts.skipped_denied,
    )
    return counts


def _resolve_jira_user_id(
    parsed: ParsedHrworksPerson,
    jira_lookup: dict[str, int],
) -> int | None:
    candidates = [to_hrworks_person_email(parsed.person_id)]
    if parsed.business_email:
        candidates.append(to_hrworks_person_email(parsed.business_email))
    for candidate in candidates:
        user_id = jira_lookup.get(candidate)
        if user_id is not None:
            return user_id
    return None


def _upsert_roster_row(
    db: Session,
    parsed: ParsedHrworksPerson,
    *,
    jira_user_id: int | None,
    synced_at: datetime,
) -> None:
    row = db.execute(
        select(HrworksPersonRoster).where(HrworksPersonRoster.person_id == parsed.person_id)
    ).scalar_one_or_none()
    if row is None:
        row = HrworksPersonRoster(person_id=parsed.person_id)
        db.add(row)
    row.hrworks_uuid = parsed.hrworks_uuid
    row.personnel_number = parsed.personnel_number
    row.business_email = parsed.business_email
    row.first_name = parsed.first_name
    row.last_name = parsed.last_name
    row.join_date = parsed.join_date
    row.leave_date = parsed.leave_date
    row.is_active = parsed.is_active
    row.jira_user_id = jira_user_id
    row.synced_at = synced_at


def _count_mapped_roster(db: Session) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(HrworksPersonRoster)
            .where(HrworksPersonRoster.jira_user_id.is_not(None))
        ).scalar_one()
    )


def load_eligible_sync_targets(
    db: Session,
    month: MonthWindow,
    *,
    config: ConfigurationSchema,
) -> list[tuple[str, int]]:
    """Return (hrworks person_id, jira_user_id) eligible for the given month."""
    denied = _denied_person_ids(config)
    rows = db.execute(
        select(
            HrworksPersonRoster.person_id,
            HrworksPersonRoster.jira_user_id,
            HrworksPersonRoster.join_date,
            HrworksPersonRoster.leave_date,
        ).where(HrworksPersonRoster.jira_user_id.is_not(None))
    ).all()
    targets: list[tuple[str, int]] = []
    for person_id, jira_user_id, join_date, leave_date in rows:
        if person_id in denied:
            continue
        if jira_user_id is None:
            continue
        if not is_person_eligible_for_month(
            join_date=join_date,
            leave_date=leave_date,
            month=month,
        ):
            continue
        targets.append((person_id, int(jira_user_id)))
    return targets


def ensure_hrworks_person_roster(
    db: Session,
    client: HrworksClient,
    *,
    config: ConfigurationSchema,
    force: bool = False,
) -> RosterRefreshCounts:
    return refresh_hrworks_person_roster(db, client, config=config, force=force)
