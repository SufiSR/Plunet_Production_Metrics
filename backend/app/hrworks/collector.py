from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.hrworks.client import HrworksClient
from app.hrworks.extractors import extract_month_record, parse_working_times_by_email
from app.hrworks.periods import (
    MonthWindow,
    current_month_start,
    default_hrworks_sync_month_windows,
    incremental_month_windows,
    iter_month_windows,
)
from app.hrworks.person_mapping import hrworks_response_email_matches_person
from app.hrworks.roster import ensure_hrworks_person_roster, load_eligible_sync_targets
from app.jira_analytics.models import HrworksPersonRoster, JiraUserMonthlyHrworksHours
from app.services.collector_progress_log import log_every_n

logger = logging.getLogger(__name__)

HrworksProgressCallback = Callable[[dict[str, Any]], None]

PROGRESS_PERSON_STEP = 5


@dataclass(slots=True)
class HrworksCounts:
    users_seen: int = 0
    months_seen: int = 0
    api_calls: int = 0
    rows_upserted: int = 0
    rows_skipped: int = 0
    roster_persons: int = 0
    roster_mapped_jira: int = 0
    roster_refreshed: bool = False
    person_month_skips: int = 0
    months_upserted: set[date] = field(default_factory=set)
    unknown_emails: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_records_processed(self) -> dict[str, int]:
        return {
            "users_seen": self.users_seen,
            "months_seen": self.months_seen,
            "api_calls": self.api_calls,
            "rows_upserted": self.rows_upserted,
            "rows_skipped": self.rows_skipped,
            "roster_persons": self.roster_persons,
            "roster_mapped_jira": self.roster_mapped_jira,
            "roster_refreshed": int(self.roster_refreshed),
            "person_month_skips": self.person_month_skips,
            "months_upserted": len(self.months_upserted),
            "unknown_emails": len(self.unknown_emails),
            "errors": len(self.errors),
        }


def resolve_sync_months(
    *,
    config: ConfigurationSchema,
    incremental: bool,
    start_date: date | None,
    end_date: date | None,
) -> list[MonthWindow]:
    if start_date is not None:
        return iter_month_windows(start_date, end_date or current_month_start())
    if incremental:
        return incremental_month_windows(
            past_months=config.hrworks.incremental_months_back,
            forecast_months=config.hrworks.incremental_forecast_months,
        )
    return default_hrworks_sync_month_windows()


def _emit_progress(
    on_progress: HrworksProgressCallback | None,
    *,
    counts: HrworksCounts,
    message: str,
    **fields: Any,
) -> None:
    if on_progress is None:
        return
    snapshot = {
        "message": message,
        "api_calls": counts.api_calls,
        "rows_upserted": counts.rows_upserted,
        "rows_skipped": counts.rows_skipped,
        "roster_persons": counts.roster_persons,
        "roster_mapped_jira": counts.roster_mapped_jira,
        **fields,
    }
    on_progress(snapshot)


def collect_hrworks_monthly_hours(
    db: Session,
    *,
    config: ConfigurationSchema,
    access_key: str,
    secret_access_key: str,
    months: list[MonthWindow],
    on_progress: HrworksProgressCallback | None = None,
) -> HrworksCounts:
    counts = HrworksCounts()
    months_total = len(months)

    with HrworksClient(
        config.hrworks.base_url,
        access_key,
        secret_access_key,
    ) as client:
        _emit_progress(
            on_progress,
            counts=counts,
            step="roster",
            message="Refreshing HRWorks person roster…",
            months_total=months_total,
            months_completed=0,
        )
        logger.info("HRworks sync: refreshing person roster")
        roster_counts = ensure_hrworks_person_roster(db, client, config=config)
        counts.roster_persons = roster_counts.persons_fetched
        counts.roster_mapped_jira = roster_counts.mapped_to_jira
        counts.roster_refreshed = roster_counts.refreshed
        logger.info(
            "HRworks sync: roster ready (persons=%s mapped_to_jira=%s refreshed=%s)",
            counts.roster_persons,
            counts.roster_mapped_jira,
            counts.roster_refreshed,
        )
        _emit_progress(
            on_progress,
            counts=counts,
            step="roster",
            message=(
                f"Roster ready — {counts.roster_mapped_jira} people mapped to Jira "
                f"({counts.roster_persons} in HRWorks)."
            ),
            months_total=months_total,
            months_completed=0,
        )

        mapped_roster_size = int(
            db.execute(
                select(func.count())
                .select_from(HrworksPersonRoster)
                .where(HrworksPersonRoster.jira_user_id.is_not(None))
            ).scalar_one()
        )

        for month_index, month in enumerate(months):
            counts.months_seen += 1
            targets = load_eligible_sync_targets(db, month, config=config)
            persons_total = len(targets)
            counts.users_seen = max(counts.users_seen, len(targets))
            counts.person_month_skips += max(mapped_roster_size - len(targets), 0)

            logger.info(
                "HRworks sync: month %s/%s %s (%s eligible people)",
                month_index + 1,
                months_total,
                month.begin_date,
                persons_total,
            )
            _emit_progress(
                on_progress,
                counts=counts,
                step="ingesting",
                message=f"Month {month_index + 1}/{months_total}: {month.begin_date} — starting {persons_total} people",
                months_total=months_total,
                months_completed=month_index,
                current_month=month.begin_date,
                persons_in_month_total=persons_total,
                persons_in_month_done=0,
            )

            for person_index, (hrworks_person_id, user_id) in enumerate(targets, start=1):
                log_every_n(
                    logger,
                    prefix=f"HRworks sync {month.begin_date}",
                    index=person_index,
                    total=persons_total,
                    step=PROGRESS_PERSON_STEP,
                )
                if (
                    person_index == 1
                    or person_index % PROGRESS_PERSON_STEP == 0
                    or person_index == persons_total
                ):
                    _emit_progress(
                        on_progress,
                        counts=counts,
                        step="ingesting",
                        message=(
                            f"Month {month_index + 1}/{months_total}: {month.begin_date} — "
                            f"person {person_index}/{persons_total}"
                        ),
                        months_total=months_total,
                        months_completed=month_index,
                        current_month=month.begin_date,
                        persons_in_month_total=persons_total,
                        persons_in_month_done=person_index,
                    )
                try:
                    payload = client.fetch_working_times(
                        begin_date=month.begin_date,
                        end_date=month.end_date,
                        person_emails=[hrworks_person_id],
                    )
                    counts.api_calls += 1
                except Exception as exc:
                    counts.errors.append(
                        f"{month.begin_date}: failed for {hrworks_person_id}: {exc}"
                    )
                    logger.exception(
                        "HRworks working-times failed for %s (%s)",
                        month.begin_date,
                        hrworks_person_id,
                    )
                    continue

                grouped = parse_working_times_by_email(payload)
                for email, entries in grouped.items():
                    if not hrworks_response_email_matches_person(email, hrworks_person_id):
                        if email not in counts.unknown_emails:
                            counts.unknown_emails.append(email)
                        continue
                    for entry in entries:
                        parsed = extract_month_record(entry)
                        if parsed is None:
                            counts.rows_skipped += 1
                            continue
                        month_start, month_end, planned, clocked = parsed
                        row = db.execute(
                            select(JiraUserMonthlyHrworksHours).where(
                                JiraUserMonthlyHrworksHours.jira_user_id == user_id,
                                JiraUserMonthlyHrworksHours.month_start == month_start,
                            )
                        ).scalar_one_or_none()
                        if row is None:
                            row = JiraUserMonthlyHrworksHours(
                                jira_user_id=user_id,
                                month_start=month_start,
                            )
                            db.add(row)
                        row.month_end = month_end
                        row.planned_working_hours = planned
                        row.clocked_working_hours = clocked
                        counts.rows_upserted += 1
                        counts.months_upserted.add(month_start)
                db.commit()

            _emit_progress(
                on_progress,
                counts=counts,
                step="ingesting",
                message=f"Finished month {month.begin_date} ({month_index + 1}/{months_total})",
                months_total=months_total,
                months_completed=month_index + 1,
                current_month=month.begin_date,
                persons_in_month_total=persons_total,
                persons_in_month_done=persons_total,
            )

    _emit_progress(
        on_progress,
        counts=counts,
        step="done",
        message="HRWorks ingestion loop complete",
        months_total=months_total,
        months_completed=months_total,
    )
    logger.info(
        "HRworks sync finished collection (api_calls=%s rows_upserted=%s errors=%s)",
        counts.api_calls,
        counts.rows_upserted,
        len(counts.errors),
    )
    return counts
