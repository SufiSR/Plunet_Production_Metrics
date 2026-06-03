from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from threading import Lock, Thread
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import SessionDep, require_admin_session
from app.database import SessionLocal
from app.jira_analytics.allocation import rebuild_monthly_allocation
from app.jira_analytics.data_quality import build_data_quality
from app.jira_analytics.data_quality_drilldown import (
    build_data_quality_user_drilldown,
    ignore_data_quality_user,
    unignore_data_quality_user,
)
from app.jira_analytics.drilldown_service import (
    allocation_explain,
    drilldown_issues,
    drilldown_people_worklogs,
    drilldown_topics,
)
from app.jira_analytics.feature_family_hours_service import (
    build_feature_family_hours_drilldown,
    build_feature_family_hours_matrix,
)
from app.jira_analytics.feature_hours_service import (
    build_feature_hours_matrix,
    build_feature_hours_row_drilldown,
)
from app.jira_analytics.feature_investment_audit_service import (
    feature_investment_audit,
    feature_investment_audit_issues,
    feature_investment_audit_worklogs,
    feature_investment_audit_xlsx,
)
from app.jira_analytics.models import JiraWorklog, MonthlyAllocatedEffort, MonthlyTopicEffortBase
from app.jira_analytics.project_scope import apply_worklog_issue_scope
from app.jira_analytics.reports import reports_service as reports
from app.jira_analytics.reports.common import parse_period
from app.models.app_configuration import AppConfiguration
from app.schemas.jira_analytics_reports import (
    AnalyticsReportResponse,
    DataQualityResponse,
    DataQualityUserDrilldownResponse,
    DataQualityUserIgnoreRequest,
    FeatureFamilyHoursDrilldownResponse,
    FeatureFamilyHoursMatrixResponse,
    FeatureHoursDrilldownResponse,
    FeatureHoursMatrixResponse,
)

router = APIRouter()
AdminSessionDep = Annotated[None, Depends(require_admin_session)]

_rebuild_lock = Lock()
_rebuild_status: dict[str, Any] = {
    "state": "idle",
    "started_at": None,
    "finished_at": None,
    "periods": [],
    "topic_rows": 0,
    "allocation_rows": 0,
    "error": None,
}


def _settings_json(db: SessionDep) -> dict:
    app_row = db.get(AppConfiguration, 1)
    if app_row and isinstance(app_row.settings_json, dict):
        return dict(app_row.settings_json)
    return {}


def _period_filters(
    date_from: str | None,
    date_to: str | None,
) -> tuple[date | None, date | None]:
    return parse_period(date_from), parse_period(date_to)


def _default_recent_period(
    date_from: date | None, date_to: date | None, *, months_back: int = 12
) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    to_date = date_to or today
    if date_from:
        return date_from, to_date
    # Keep heavy reports bounded when the caller omits filters.
    from_date = date(to_date.year, to_date.month, 1)
    month = from_date.month - (months_back - 1)
    year = from_date.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1), to_date


def _latest_worklog_month(db: SessionDep) -> date | None:
    latest = db.execute(
        apply_worklog_issue_scope(
            select(func.max(JiraWorklog.started_at)).where(JiraWorklog.started_at.is_not(None))
        )
    ).scalar_one_or_none()
    if latest is None:
        return None
    return date(latest.year, latest.month, 1)


def _current_allocation_summary(db: SessionDep) -> dict[str, Any]:
    periods = db.execute(
        select(MonthlyAllocatedEffort.period_month)
        .distinct()
        .order_by(MonthlyAllocatedEffort.period_month.asc())
    ).scalars().all()
    topic_rows = db.execute(select(func.count()).select_from(MonthlyTopicEffortBase)).scalar_one()
    allocation_rows = db.execute(
        select(func.count()).select_from(MonthlyAllocatedEffort)
    ).scalar_one()
    return {
        "periods": [p.isoformat() for p in periods],
        "topic_rows": int(topic_rows),
        "allocation_rows": int(allocation_rows),
    }


def _run_rebuild_in_background(period_months: list[date] | None) -> None:
    try:
        with SessionLocal() as session:
            result = rebuild_monthly_allocation(session, period_months=period_months)
        with _rebuild_lock:
            _rebuild_status.update(
                {
                    "state": "succeeded",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "periods": result["periods"],
                    "topic_rows": result["topic_rows"],
                    "allocation_rows": result["allocation_rows"],
                    "error": None,
                }
            )
    except Exception as exc:  # pragma: no cover - defensive status reporting
        with _rebuild_lock:
            _rebuild_status.update(
                {
                    "state": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }
            )


@router.get("/feature-hours/matrix", response_model=FeatureHoursMatrixResponse)
def feature_hours_matrix(
    db: SessionDep,
    months: Annotated[int, Query(ge=1, le=36)] = 12,
    role: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
) -> FeatureHoursMatrixResponse:
    role_filter = role.strip() if role and role.strip() else None
    team_filter = team.strip() if team and team.strip() else None
    return build_feature_hours_matrix(
        db,
        settings_json=_settings_json(db),
        months=months,
        role_filter=role_filter,
        team_filter=team_filter,
    )


@router.get("/feature-hours/{row_id}/drilldown", response_model=FeatureHoursDrilldownResponse)
def feature_hours_row_drilldown(
    row_id: str,
    db: SessionDep,
    months: Annotated[int, Query(ge=1, le=36)] = 12,
    role: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
) -> FeatureHoursDrilldownResponse:
    role_filter = role.strip() if role and role.strip() else None
    team_filter = team.strip() if team and team.strip() else None
    payload = build_feature_hours_row_drilldown(
        db,
        settings_json=_settings_json(db),
        row_id=row_id.strip(),
        months=months,
        role_filter=role_filter,
        team_filter=team_filter,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return payload


@router.get("/feature-families/matrix", response_model=FeatureFamilyHoursMatrixResponse)
def feature_family_hours_matrix(
    db: SessionDep,
    months: Annotated[int, Query(ge=1, le=36)] = 12,
    role: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
) -> FeatureFamilyHoursMatrixResponse:
    role_filter = role.strip() if role and role.strip() else None
    team_filter = team.strip() if team and team.strip() else None
    return build_feature_family_hours_matrix(
        db,
        settings_json=_settings_json(db),
        months=months,
        role_filter=role_filter,
        team_filter=team_filter,
    )


@router.get(
    "/feature-families/{family_id}/drilldown",
    response_model=FeatureFamilyHoursDrilldownResponse,
)
def feature_family_hours_drilldown(
    family_id: int,
    db: SessionDep,
    months: Annotated[int, Query(ge=1, le=36)] = 12,
    role: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
) -> FeatureFamilyHoursDrilldownResponse:
    role_filter = role.strip() if role and role.strip() else None
    team_filter = team.strip() if team and team.strip() else None
    payload = build_feature_family_hours_drilldown(
        db,
        settings_json=_settings_json(db),
        family_id=family_id,
        months=months,
        role_filter=role_filter,
        team_filter=team_filter,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Feature family {family_id} not found")
    return payload


@router.get("/data-quality", response_model=DataQualityResponse)
def data_quality(db: SessionDep) -> DataQualityResponse:
    return build_data_quality(db)


@router.get(
    "/data-quality/checks/{check_id}/users",
    response_model=DataQualityUserDrilldownResponse,
)
def data_quality_user_drilldown(
    check_id: str,
    db: SessionDep,
) -> DataQualityUserDrilldownResponse:
    try:
        return build_data_quality_user_drilldown(db, check_id=check_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/data-quality/checks/{check_id}/users/{user_id}/ignore",
    response_model=DataQualityUserDrilldownResponse,
)
def post_data_quality_user_ignore(
    check_id: str,
    user_id: int,
    body: DataQualityUserIgnoreRequest,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> DataQualityUserDrilldownResponse:
    try:
        response = ignore_data_quality_user(
            db,
            check_id=check_id,
            user_id=user_id,
            reason=body.reason,
        )
        db.commit()
        return response
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/data-quality/checks/{check_id}/users/{user_id}/ignore",
    response_model=DataQualityUserDrilldownResponse,
)
def delete_data_quality_user_ignore(
    check_id: str,
    user_id: int,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> DataQualityUserDrilldownResponse:
    try:
        response = unignore_data_quality_user(db, check_id=check_id, user_id=user_id)
        db.commit()
        return response
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/allocation/rebuild")
def rebuild_allocation(
    db: SessionDep,
    period_month: Annotated[str | None, Query()] = None,
    all_periods: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    months: list[date] | None = None
    if period_month:
        months = [parse_period(period_month) or date.today().replace(day=1)]
    elif not all_periods:
        latest = _latest_worklog_month(db)
        months = [latest] if latest else []
    else:
        current = _current_allocation_summary(db)
        with _rebuild_lock:
            if _rebuild_status["state"] == "running":
                return dict(_rebuild_status)
            _rebuild_status.update(
                {
                    "state": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "finished_at": None,
                    "periods": current["periods"],
                    "topic_rows": current["topic_rows"],
                    "allocation_rows": current["allocation_rows"],
                    "error": None,
                }
            )
        Thread(target=_run_rebuild_in_background, args=(None,), daemon=True).start()
        return dict(_rebuild_status)
    return rebuild_monthly_allocation(db, settings_json=_settings_json(db), period_months=months)


@router.get("/allocation/rebuild/status")
def rebuild_allocation_status() -> dict[str, Any]:
    with _rebuild_lock:
        return dict(_rebuild_status)


@router.get("/drilldown/topics", response_model=AnalyticsReportResponse)
def get_drilldown_topics(
    db: SessionDep,
    period_month: Annotated[str | None, Query()] = None,
    topic_type: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    return drilldown_topics(
        db,
        period_month=parse_period(period_month),
        topic_type=topic_type,
        team=team,
        feature_key=feature_key,
    )


@router.get("/drilldown/issues", response_model=AnalyticsReportResponse)
def get_drilldown_issues(
    db: SessionDep,
    period_month: Annotated[str | None, Query()] = None,
    topic_type: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    return drilldown_issues(
        db,
        period_month=parse_period(period_month),
        topic_type=topic_type,
        team=team,
        feature_key=feature_key,
    )


@router.get("/drilldown/people-worklogs", response_model=AnalyticsReportResponse)
def get_drilldown_people_worklogs(
    db: SessionDep,
    period_month: Annotated[str | None, Query()] = None,
    issue_key: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    return drilldown_people_worklogs(
        db,
        period_month=parse_period(period_month),
        issue_key=issue_key,
        feature_key=feature_key,
    )


@router.get("/allocation/explain", response_model=AnalyticsReportResponse)
def get_allocation_explain(
    db: SessionDep,
    period_month: Annotated[str, Query()],
    feature_key: Annotated[str | None, Query()] = None,
    issue_key: Annotated[str | None, Query()] = None,
    person: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    pm = parse_period(period_month)
    if pm is None:
        raise HTTPException(status_code=400, detail="period_month is required")
    return allocation_explain(
        db,
        period_month=pm,
        feature_key=feature_key,
        issue_key=issue_key,
        person=person,
    )


@router.get("/capacity/investment-category", response_model=AnalyticsReportResponse)
def investment_category(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    project_key: Annotated[list[str] | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.investment_category(
        db,
        date_from=f,
        date_to=t,
        team=team,
        project_keys=project_key,
    )


@router.get("/features/cost", response_model=AnalyticsReportResponse)
def features_cost(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.feature_cost(db, date_from=f, date_to=t, team=team, feature_key=feature_key)


@router.get("/features/investment-audit", response_model=AnalyticsReportResponse)
def features_investment_audit(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    family_id: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return feature_investment_audit(
        db,
        date_from=f,
        date_to=t,
        team=team,
        role=role,
        family_id=family_id,
        feature_key=feature_key,
    )


@router.get("/features/investment-audit/drilldown/issues", response_model=AnalyticsReportResponse)
def features_investment_audit_issues(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    period_month: Annotated[str | None, Query()] = None,
    team: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    family_id: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return feature_investment_audit_issues(
        db,
        date_from=f,
        date_to=t,
        period_month=parse_period(period_month),
        team=team,
        role=role,
        family_id=family_id,
        feature_key=feature_key,
    )


@router.get("/features/investment-audit/drilldown/worklogs", response_model=AnalyticsReportResponse)
def features_investment_audit_worklogs(
    db: SessionDep,
    issue_key: Annotated[str, Query()],
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    period_month: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return feature_investment_audit_worklogs(
        db,
        date_from=f,
        date_to=t,
        issue_key=issue_key,
        period_month=parse_period(period_month),
    )


@router.get("/features/investment-audit/export.xlsx")
def features_investment_audit_export(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    family_id: Annotated[str | None, Query()] = None,
    feature_key: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    f, t = _period_filters(date_from, date_to)
    content = feature_investment_audit_xlsx(
        db,
        date_from=f,
        date_to=t,
        team=team,
        role=role,
        family_id=family_id,
        feature_key=feature_key,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="feature-investment-audit.xlsx"',
        },
    )


@router.get("/issues/without-feature", response_model=AnalyticsReportResponse)
def issues_without_feature(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    project_key: Annotated[list[str] | None, Query()] = None,
    min_hours: Annotated[float, Query()] = 0,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.issues_without_feature(
        db,
        date_from=f,
        date_to=t,
        team=team,
        project_keys=project_key,
        min_hours=min_hours,
    )


@router.get("/features/investment-ranking", response_model=AnalyticsReportResponse)
def features_investment_ranking(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.investment_ranking(db, date_from=f, date_to=t, team=team, limit=limit)


@router.get("/work-allocation/heatmap", response_model=AnalyticsReportResponse)
def work_allocation_heatmap(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    mode: Annotated[str, Query()] = "combined",
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.work_allocation_heatmap(db, date_from=f, date_to=t, team=team, mode=mode)


@router.get("/teams/planned-vs-unplanned", response_model=AnalyticsReportResponse)
def teams_planned_vs_unplanned(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.planned_vs_unplanned(db, date_from=f, date_to=t, team=team)


@router.get("/teams/availability-vs-booked", response_model=AnalyticsReportResponse)
def teams_availability_vs_booked(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.availability_vs_booked(db, date_from=f, date_to=t, team=team)


@router.get("/teams/capacity-forecast", response_model=AnalyticsReportResponse)
def teams_capacity_forecast(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.capacity_forecast(db, date_from=f, date_to=t, team=team)


@router.get("/teams/real-interruption-ratio", response_model=AnalyticsReportResponse)
def teams_real_interruption_ratio(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.real_interruption_ratio(db, date_from=f, date_to=t, team=team)


@router.get("/features/lifecycle", response_model=AnalyticsReportResponse)
def features_lifecycle(
    db: SessionDep,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    return reports.feature_lifecycle(db, team=team)


@router.get("/features/promised-vs-actual", response_model=AnalyticsReportResponse)
def features_promised_vs_actual(
    db: SessionDep,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    return reports.promised_vs_actual(db, team=team)


@router.get("/features/idea-aging", response_model=AnalyticsReportResponse)
def features_idea_aging(
    db: SessionDep,
    min_age_days: Annotated[int, Query()] = 0,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    return reports.idea_aging(db, min_age_days=min_age_days, team=team)


@router.get("/workflow/status-waiting-time", response_model=AnalyticsReportResponse)
def workflow_status_waiting(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    project_key: Annotated[list[str] | None, Query()] = None,
    include_other_workflows: Annotated[bool, Query(alias="includeOtherWorkflows")] = False,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    f, t = _default_recent_period(f, t, months_back=12)
    return reports.status_waiting_time(
        db,
        date_from=f,
        date_to=t,
        project_keys=project_key,
        include_other_workflows=include_other_workflows,
    )


@router.get("/workflow/active-vs-passive", response_model=AnalyticsReportResponse)
def workflow_active_vs_passive(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    issue_type: Annotated[str | None, Query(alias="issueType")] = None,
    workflow: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.active_vs_passive(
        db,
        date_from=f,
        date_to=t,
        team=team,
        issue_type=issue_type,
        workflow=workflow,
    )


@router.get("/workflow/active-vs-passive-trend", response_model=AnalyticsReportResponse)
def workflow_active_vs_passive_trend(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
    workflow: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    f, t = reports.bound_quarter_period(f, t)
    return reports.active_vs_passive_trend(
        db,
        date_from=f,
        date_to=t,
        team=team,
        workflow=workflow,
    )


@router.get("/workflow/thrashing", response_model=AnalyticsReportResponse)
def workflow_thrashing(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    min_score: Annotated[float, Query()] = 0,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.workflow_thrashing(db, date_from=f, date_to=t, min_score=min_score)


@router.get("/teams/throughput-stability", response_model=AnalyticsReportResponse)
def teams_throughput(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    f, t = _default_recent_period(f, t, months_back=12)
    return reports.throughput_stability(db, date_from=f, date_to=t)


@router.get("/risks/single-contributor", response_model=AnalyticsReportResponse)
def risks_bus_factor(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.bus_factor(db, date_from=f, date_to=t, team=team)


@router.get("/customers/effort", response_model=AnalyticsReportResponse)
def customers_effort(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    customer: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.customer_effort(db, date_from=f, date_to=t, customer=customer)


@router.get("/product/investment-by-theme", response_model=AnalyticsReportResponse)
def product_investment_by_theme(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    return reports.investment_by_theme(db, date_from=f, date_to=t)


@router.get("/features/risk", response_model=AnalyticsReportResponse)
def features_risk(db: SessionDep) -> AnalyticsReportResponse:
    return reports.feature_risk(db)


@router.get("/executive/engineering-health", response_model=AnalyticsReportResponse)
def executive_engineering_health(
    db: SessionDep,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    team: Annotated[str | None, Query()] = None,
) -> AnalyticsReportResponse:
    f, t = _period_filters(date_from, date_to)
    f, t = _default_recent_period(f, t, months_back=3)
    return reports.engineering_health(db, date_from=f, date_to=t, team=team)


@router.get("/product/roadmap-reliability", response_model=AnalyticsReportResponse)
def product_roadmap_reliability(db: SessionDep) -> AnalyticsReportResponse:
    return reports.roadmap_reliability(db)


@router.get("/release/done-vs-released", response_model=AnalyticsReportResponse)
def release_done_vs_released(db: SessionDep) -> AnalyticsReportResponse:
    return reports.release_quality(db)


@router.get("/release/quality-correlation", response_model=AnalyticsReportResponse)
def release_quality_correlation(db: SessionDep) -> AnalyticsReportResponse:
    return reports.release_quality(db)


@router.get("/quality/failure-correlation", response_model=AnalyticsReportResponse)
def quality_failure_correlation(db: SessionDep) -> AnalyticsReportResponse:
    return reports.workflow_thrashing(db, min_score=5)


@router.get("/features/size-vs-speed", response_model=AnalyticsReportResponse)
def features_size_vs_speed(db: SessionDep) -> AnalyticsReportResponse:
    return reports.size_vs_speed(db)
