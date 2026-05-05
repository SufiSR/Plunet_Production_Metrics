from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bug_release import BugRelease
from app.models.issue_worklog import IssueWorklog
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.schemas.jira_worklog_assignments import JiraWorklogUserAssignment
from app.schemas.releases import ReleaseWorklogHoursByRole, ReleaseWorklogHoursResponse, ReleaseWorklogTeamHoursRow
from app.services.jira_worklog_settings import read_worklog_assignments_from_settings, read_worklog_denylist_from_settings


def _seconds_as_hours(seconds: int) -> float:
    return round(seconds / 3600.0, 4)


def _assignment_map(assignments: list[JiraWorklogUserAssignment]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for a in assignments:
        out[a.jira_account_id.strip()] = (a.role, a.team.strip())
    return out


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
        .join(BugRelease, BugRelease.bug_id == ProductionBug.id)
        .join(Release, Release.id == BugRelease.release_id)
        .where(
            Release.repository_id == repository_id,
            Release.tag_name == tag_name,
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

    deny_raw = read_worklog_denylist_from_settings(settings_json)
    deny_ids = frozenset(deny_raw)
    assignments = read_worklog_assignments_from_settings(settings_json)
    by_account = _assignment_map(assignments)

    rows = _worklog_rows_for_release_tag(
        db, repository_id=repository_id, tag_name=tag_name, deny_ids=deny_ids
    )

    pm_s = dev_s = qa_s = unmapped_role_s = 0
    team_seconds: dict[str, int] = {}
    unmapped_team_s = 0
    total_s = 0

    for spent, acc_id, _author in rows:
        total_s += spent
        role: str | None = None
        team: str | None = None
        if acc_id:
            key = acc_id.strip()
            pair = by_account.get(key)
            if pair:
                role, team = pair

        if role == "pm":
            pm_s += spent
        elif role == "dev":
            dev_s += spent
        elif role == "qa":
            qa_s += spent
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
            unmapped=_seconds_as_hours(unmapped_role_s),
        ),
        hours_by_team=team_rows,
        unmapped_team_hours=_seconds_as_hours(unmapped_team_s),
        total_hours=_seconds_as_hours(total_s),
    )
