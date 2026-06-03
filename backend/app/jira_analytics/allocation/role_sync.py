from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.jira_analytics.allocation.role_mapping import allocation_role_for_worklog_role
from app.jira_analytics.models import JiraUser, JiraUserRoleAssignment
from app.schemas.jira_worklog_assignments import JiraWorklogUserAssignment
from app.services.jira_worklog_settings import read_worklog_assignments_from_settings


def sync_role_assignments_from_settings(db: Session, settings_json: dict) -> int:
    """Upsert role assignments from admin worklog user assignments config."""
    assignments = read_worklog_assignments_from_settings(settings_json)
    if not assignments:
        return 0
    today = date.today()
    db.execute(delete(JiraUserRoleAssignment))
    count = 0
    for item in assignments:
        row = _assignment_to_role_row(db, item, today)
        if row is not None:
            db.add(row)
            count += 1
    db.flush()
    return count


def _assignment_to_role_row(
    db: Session,
    item: JiraWorklogUserAssignment,
    valid_from: date,
) -> JiraUserRoleAssignment | None:
    account_id = (item.jira_account_id or "").strip() or None
    author = (item.author or "").strip() or None
    email = ""
    display = author or account_id or "Unknown"
    if account_id:
        user = db.execute(
            select(JiraUser).where(JiraUser.account_id == account_id).limit(1)
        ).scalar_one_or_none()
        if user:
            email = user.email_address or f"{account_id}@unknown.local"
            display = user.display_name or display
        else:
            email = f"{account_id}@unknown.local"
    elif author:
        email = f"{author.lower().replace(' ', '.')}@unknown.local"
    else:
        return None
    team_name = (item.team or "").strip() or None
    return JiraUserRoleAssignment(
        user_account_id=account_id,
        user_email=email,
        display_name=display,
        role_name=allocation_role_for_worklog_role(item.role),
        team_id=team_name,
        team_name=team_name,
        valid_from=valid_from,
        valid_to=None,
        active=True,
    )
