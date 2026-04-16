from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import RuntimeSettingsDep, SessionDep
from app.models.release import Release
from app.models.repository import Repository
from app.schemas.metrics import CurrentMetricsResponse, HistoryResponse, PeriodType
from app.schemas.releases import (
    CustomerReleaseDrilldownItem,
    CustomerReleaseDrilldownListResponse,
    FailedCustomerReleaseDrilldownItem,
    FailedCustomerReleaseDrilldownListResponse,
    OffsetPagination,
    ReleaseMergeRequestListResponse,
    ReleaseMergeRequestRow,
    ReleaseProductionBugListResponse,
    ReleaseProductionBugRow,
    ReleaseTimelineItem,
    ReleaseTimelineResponse,
)
from app.services.metrics_public_service import (
    build_current_metrics_response,
    build_history_response,
)
from app.services.release_drilldown_service import (
    build_gitlab_compare_url,
    build_jira_browse_url,
    count_customer_releases,
    count_failed_customer_releases,
    count_merge_requests_for_release,
    count_merge_requests_with_jira_key,
    count_production_bugs_for_customer_release,
    find_previous_customer_release,
    get_customer_release_or_none,
    list_customer_releases_page,
    list_failed_customer_releases_page,
    list_merge_requests_for_release_page,
    list_production_bugs_for_customer_release_page,
)

router = APIRouter()


def _offset_pagination(*, page: int, size: int, total: int) -> OffsetPagination:
    total_pages = (total + size - 1) // size if total > 0 else 0
    return OffsetPagination(
        page=page,
        size=size,
        total_elements=total,
        total_pages=total_pages,
        has_next=(page + 1) * size < total,
        has_previous=page > 0,
    )


@router.get("/current", response_model=CurrentMetricsResponse)
def get_metrics_current(
    db: SessionDep,
    period_type: PeriodType = PeriodType.WEEK,
) -> CurrentMetricsResponse:
    return build_current_metrics_response(db, repository_id=None, period_type=period_type.value)


@router.get("/history", response_model=HistoryResponse)
def get_metrics_history(
    db: SessionDep,
    period_type: PeriodType = PeriodType.WEEK,
    from_: Annotated[
        date | None,
        Query(alias="from", description="Start date (ISO); default 12 weeks before `to`"),
    ] = None,
    to: Annotated[
        date | None,
        Query(description="End date (ISO); default today UTC"),
    ] = None,
    repository_id: Annotated[int | None, Query()] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> HistoryResponse:
    if to is None:
        to = datetime.now(timezone.utc).date()
    if from_ is None:
        from_ = to - timedelta(weeks=12)
    if from_ > to:
        raise HTTPException(status_code=400, detail="Parameter 'from' must be on or before 'to'")
    return build_history_response(
        db,
        period_type=period_type,
        from_date=from_,
        to_date=to,
        repository_id=repository_id,
        page=page,
        size=size,
    )


@router.get("/repository/{repository_id}", response_model=CurrentMetricsResponse)
def get_metrics_for_repository(
    repository_id: int,
    db: SessionDep,
    period_type: PeriodType = PeriodType.WEEK,
) -> CurrentMetricsResponse:
    repo = db.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail=f"Repository with id {repository_id} not found",
        )
    return build_current_metrics_response(
        db, repository_id=repository_id, period_type=period_type.value
    )


@router.get("/releases/timeline", response_model=ReleaseTimelineResponse)
def get_release_timeline(
    db: SessionDep,
    min_major: Annotated[int, Query(ge=0, le=99)] = 8,
    repository_id: Annotated[int | None, Query()] = None,
    include_non_customer: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=10, le=5000)] = 2000,
) -> ReleaseTimelineResponse:
    q = (
        select(Release, Repository)
        .join(Repository, Repository.id == Release.repository_id)
        .where(Release.version_major.is_not(None))
        .where(Release.version_major >= min_major)
        .order_by(Release.committed_at.asc())
        .limit(limit)
    )
    if repository_id is not None:
        q = q.where(Release.repository_id == repository_id)
    if not include_non_customer:
        q = q.where(Release.customer_release.is_(True))

    rows = db.execute(q).all()
    items = [
        ReleaseTimelineItem(
            repository_id=int(release.repository_id),
            repository_path=repo.path,
            tag_name=release.tag_name,
            committed_at=release.committed_at,
            customer_release=bool(release.customer_release),
            version_major=release.version_major,
            version_minor=release.version_minor,
            version_patch=release.version_patch,
        )
        for release, repo in rows
    ]
    return ReleaseTimelineResponse(items=items, total=len(items))


@router.get("/releases/customer/drilldown", response_model=CustomerReleaseDrilldownListResponse)
def list_customer_release_drilldown(
    db: SessionDep,
    repository_id: Annotated[int | None, Query(description="Limit to one repository")] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CustomerReleaseDrilldownListResponse:
    if repository_id is not None:
        repo = db.get(Repository, repository_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not found")
    total = count_customer_releases(db, repository_id=repository_id)
    rows = list_customer_releases_page(db, repository_id=repository_id, page=page, size=size)
    items = [
        CustomerReleaseDrilldownItem(
            repository_id=r.repository_id,
            repository_path=r.repository_path,
            tag_name=r.tag_name,
            committed_at=r.committed_at,
            version_major=r.version_major,
            version_minor=r.version_minor,
            version_patch=r.version_patch,
            lane=r.lane,
            mr_count=r.mr_count,
        )
        for r in rows
    ]
    return CustomerReleaseDrilldownListResponse(
        items=items,
        pagination=_offset_pagination(page=page, size=size, total=total),
    )


@router.get("/releases/customer/merge-requests", response_model=ReleaseMergeRequestListResponse)
def list_merge_requests_for_customer_release(
    db: SessionDep,
    settings: RuntimeSettingsDep,
    repository_id: Annotated[int, Query(description="Repository id")],
    tag_name: Annotated[
        str,
        Query(min_length=1, max_length=255, description="Customer release tag"),
    ],
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ReleaseMergeRequestListResponse:
    rel = get_customer_release_or_none(db, repository_id=repository_id, tag_name=tag_name)
    if rel is None:
        raise HTTPException(
            status_code=404,
            detail="Customer release not found for repository (or repository inactive)",
        )
    prev_rel = find_previous_customer_release(
        db, repository_id=repository_id, committed_at=rel.committed_at
    )
    prev_tag = prev_rel.tag_name if prev_rel is not None else None
    repo = db.get(Repository, repository_id)
    compare_url: str | None = None
    if prev_tag and settings.gitlab.base_url and repo is not None and repo.path:
        compare_url = build_gitlab_compare_url(
            base_url=settings.gitlab.base_url,
            project_path=repo.path,
            from_tag=prev_tag,
            to_tag=tag_name,
        )
    jira_mr_total = count_merge_requests_with_jira_key(
        db, repository_id=repository_id, tag_name=tag_name
    )
    total = count_merge_requests_for_release(db, repository_id=repository_id, tag_name=tag_name)
    rows = list_merge_requests_for_release_page(
        db, repository_id=repository_id, tag_name=tag_name, page=page, size=size
    )
    items = [
        ReleaseMergeRequestRow(
            gitlab_mr_id=r.gitlab_mr_id,
            title=r.title,
            target_branch=r.target_branch,
            merged_at=r.merged_at,
            lead_time_hours=r.lead_time_hours,
            release_wait_time_hours=r.release_wait_time_hours,
            jira_key=r.jira_key,
        )
        for r in rows
    ]
    return ReleaseMergeRequestListResponse(
        repository_id=repository_id,
        tag_name=tag_name,
        items=items,
        pagination=_offset_pagination(page=page, size=size, total=total),
        previous_customer_tag=prev_tag,
        gitlab_compare_url=compare_url,
        mr_with_jira_key_count=jira_mr_total,
    )


@router.get(
    "/releases/customer/failed-drilldown",
    response_model=FailedCustomerReleaseDrilldownListResponse,
)
def list_failed_customer_release_drilldown(
    db: SessionDep,
    repository_id: Annotated[int | None, Query(description="Limit to one repository")] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FailedCustomerReleaseDrilldownListResponse:
    if repository_id is not None:
        repo = db.get(Repository, repository_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not found")
    total = count_failed_customer_releases(db, repository_id=repository_id)
    rows = list_failed_customer_releases_page(
        db, repository_id=repository_id, page=page, size=size
    )
    items = [
        FailedCustomerReleaseDrilldownItem(
            repository_id=r.repository_id,
            repository_path=r.repository_path,
            tag_name=r.tag_name,
            committed_at=r.committed_at,
            version_major=r.version_major,
            version_minor=r.version_minor,
            version_patch=r.version_patch,
            lane=r.lane,
            mr_count=r.mr_count,
            issue_count=r.issue_count,
        )
        for r in rows
    ]
    return FailedCustomerReleaseDrilldownListResponse(
        items=items,
        pagination=_offset_pagination(page=page, size=size, total=total),
    )


@router.get(
    "/releases/customer/failed/issues",
    response_model=ReleaseProductionBugListResponse,
)
def list_production_bugs_for_failed_customer_release(
    db: SessionDep,
    settings: RuntimeSettingsDep,
    repository_id: Annotated[int, Query(description="Repository id")],
    tag_name: Annotated[
        str,
        Query(min_length=1, max_length=255, description="Customer release tag"),
    ],
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ReleaseProductionBugListResponse:
    rel = get_customer_release_or_none(db, repository_id=repository_id, tag_name=tag_name)
    if rel is None:
        raise HTTPException(
            status_code=404,
            detail="Customer release not found for repository (or repository inactive)",
        )
    total = count_production_bugs_for_customer_release(
        db, repository_id=repository_id, tag_name=tag_name
    )
    rows = list_production_bugs_for_customer_release_page(
        db, repository_id=repository_id, tag_name=tag_name, page=page, size=size
    )
    jira_base = (settings.jira.base_url or "").strip()
    items = [
        ReleaseProductionBugRow(
            jira_key=r.jira_key,
            summary=r.summary,
            status=r.status,
            priority=r.priority,
            healthmemo=r.healthmemo,
            jira_browse_url=(
                build_jira_browse_url(base_url=jira_base, jira_key=r.jira_key)
                if jira_base
                else None
            ),
        )
        for r in rows
    ]
    return ReleaseProductionBugListResponse(
        repository_id=repository_id,
        tag_name=tag_name,
        items=items,
        pagination=_offset_pagination(page=page, size=size, total=total),
    )
