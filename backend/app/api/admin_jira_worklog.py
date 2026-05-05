from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, require_admin_session
from app.models.app_configuration import AppConfiguration
from app.schemas.jira_worklog_assignments import WorklogAuthorListItem, WorklogAuthorListResponse
from app.services.jira_worklog_settings import (
    list_distinct_worklog_authors_page,
    pagination_meta,
    read_worklog_denylist_from_settings,
)

router = APIRouter()
AdminSessionDep = Annotated[None, Depends(require_admin_session)]


@router.get("/jira/worklog-authors", response_model=WorklogAuthorListResponse)
def list_jira_worklog_authors(
    _auth: AdminSessionDep,
    db: SessionDep,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> WorklogAuthorListResponse:
    app_row = db.get(AppConfiguration, 1)
    settings_json: dict = (
        dict(app_row.settings_json) if app_row and isinstance(app_row.settings_json, dict) else {}
    )
    denylist = read_worklog_denylist_from_settings(settings_json)
    rows, total = list_distinct_worklog_authors_page(db, denylist=denylist, page=page, size=size)
    meta = pagination_meta(page=page, size=size, total_elements=total)
    return WorklogAuthorListResponse(
        items=[WorklogAuthorListItem(jira_account_id=a, author=n) for a, n in rows],
        page=int(meta["page"]),
        size=int(meta["size"]),
        total_elements=int(meta["total_elements"]),
        total_pages=int(meta["total_pages"]),
        has_next=bool(meta["has_next"]),
        has_previous=bool(meta["has_previous"]),
    )
