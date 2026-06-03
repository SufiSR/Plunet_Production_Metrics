from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.issue_worklog import IssueWorklog
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.schemas.releases import ReleaseWorklogHoursByRole, ReleaseWorklogHoursResponse, ReleaseWorklogTeamHoursRow
from app.services.jira_user_assignments import list_assignments_maps, reporting_excluded_account_ids


def _seconds_as_hours(seconds: int) -> float:
    return round(seconds / 3600.0, 4)


def _worklog_rows_for_release_tag(
    db: Session, *, repository_id: int, tag_name: str, deny_ids: frozenset[str]
) -> list[tuple[int, str | None, str | None]]:
    wl_time = IssueWorklog.time_spent_seconds
    wl_aid = IssueWorklog.jira_account_id
    wl_author = IssueWorklog.author
    q = (
        select(wl_time, wl_aid, wl_author)
        .select_from(IssueWorklog)
        .join(ProductionBug, ProductionBug.id == IssueWorklog.bug_id)
        .where(
            ProductionBug.id.in_(
                select(ProductionBug.id)
                .select_from(ProductionBug)
                .join(MergeRequest, MergeRequest.jira_key == ProductionBug.jira_key)
                .where(
                    MergeRequest.repository_id == repository_id,
                    MergeRequest.first_customer_tag == tag_name,
                    MergeRequest.jira_key.is_not(None),
                )
                .distinct()
            )
        )
    )
    if deny_ids:
        q = q.where(
            (wl_aid.is_(None)) | (~wl_aid.in_(tuple(deny_ids))),
        )
    return [(int(r[0]), r[1], r[2]) for r in db.execute(q).all()]


def build_release_worklog_hours_response(
    db: Session,
    *,
    repository_id: int,
    tag_name: str,
    settings_json: dict[str, Any],
) -> ReleaseWorklogHoursResponse | None:
    rel = db.execute(
        select(Release.id).where(
            Release.repository_id == repository_id,
            Release.tag_name == tag_name,
        )
    ).scalar_one_or_none()
    if rel is None:
        return None

    del settings_json
    deny_ids = reporting_excluded_account_ids(db)
    by_account, by_author = list_assignments_maps(db)

    rows = _worklog_rows_for_release_tag(
        db, repository_id=repository_id, tag_name=tag_name, deny_ids=deny_ids
    )

    pm_s = dev_s = qa_s = sup_s = unmapped_role_s = 0
    team_seconds: dict[str, int] = {}
    unmapped_team_s = 0
    total_s = 0

    for spent, acc_id, author in rows:
        total_s += spent
        role: str | None = None
        team: str | None = None
        if acc_id:
            key = acc_id.strip()
            pair = by_account.get(key)
            if pair:
                role, team = pair
        if role is None and author:
            pair = by_author.get(author.strip().lower())
            if pair:
                role, team = pair

        if role == "pm":
            pm_s += spent
        elif role == "dev":
            dev_s += spent
        elif role == "qa":
            qa_s += spent
        elif role == "sup":
            sup_s += spent
        else:
            unmapped_role_s += spent

        if team:
            team_seconds[team] = team_seconds.get(team, 0) + spent
        else:
            unmapped_team_s += spent

    team_rows = [
        ReleaseWorklogTeamHoursRow(team=name, hours=_seconds_as_hours(sec))
        for name, sec in sorted(team_seconds.items(), key=lambda x: (-x[1], x[0]))
    ]

    return ReleaseWorklogHoursResponse(
        repository_id=repository_id,
        tag_name=tag_name,
        hours_by_role=ReleaseWorklogHoursByRole(
            pm=_seconds_as_hours(pm_s),
            dev=_seconds_as_hours(dev_s),
            qa=_seconds_as_hours(qa_s),
            sup=_seconds_as_hours(sup_s),
            unmapped=_seconds_as_hours(unmapped_role_s),
        ),
        hours_by_team=team_rows,
        unmapped_team_hours=_seconds_as_hours(unmapped_team_s),
        total_hours=_seconds_as_hours(total_s),
    )
