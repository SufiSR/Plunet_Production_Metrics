from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.jira_analytics.allocation.role_mapping import HEATMAP_ROLES
from app.jira_analytics.extractors import option_values, text_value
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraIssueStatusTransition,
    JiraProject,
    JiraUser,
    JiraUserMonthlyHrworksHours,
    JiraUserRoleAssignment,
    JiraWorkflow,
    JiraWorklog,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.team_names import normalized_team_name as _normalized_team_name
from app.jira_analytics.project_scope import (
    EXCLUDED_PROJECT_KEYS,
    apply_feature_root_scope,
    apply_issue_scope,
    apply_worklog_issue_scope,
    filter_excluded_keys,
    scope_monthly_allocated_effort,
    scope_monthly_topic_effort,
)
from app.jira_analytics.reports.common import allocated_query
from app.jira_analytics.workflow.status_intervals import build_status_intervals
from app.jira_analytics.workflow.status_waiting import (
    available_status_waiting_projects,
    build_status_waiting_sections,
    projects_for_workflow,
)
from app.jira_analytics.workflow.status_waiting_catalog import (
    MAIN_WORKFLOW_SPECS,
    MainWorkflowSpec,
    issue_type_eligible_for_main_spec,
    issue_type_matches_catalog_option,
    workflow_matches_main_spec,
)
from app.jira_analytics.workflow.thrash import thrash_by_issue
from app.jira_analytics.workflow.workflow_resolution import (
    load_workflows_by_id,
    resolve_workflow_ids_for_issues,
)
from app.jira_analytics.workflow.workflow_sync import scoped_workflow_ids
from app.models.release import Release
from app.schemas.jira_analytics_reports import AnalyticsReportResponse
from app.services.jira_user_assignments import get_assignment_for_allocated_source

logger = logging.getLogger(__name__)

FLOW_REPORT_YEARS = (2024, 2025, 2026)
ISSUE_ID_CHUNK_SIZE = 1000
DEFAULT_TREND_QUARTERS = 4
MAX_TREND_QUARTERS = 12
FLOW_YEARLY_AVERAGE_TEAMS = ("Team World", "Team Tantrum", "Cosmic Coders", "CoP")
FLOW_YEARLY_AVERAGE_TEAM_ORDER = {
    team: index for index, team in enumerate(FLOW_YEARLY_AVERAGE_TEAMS)
}
ROADMAP_RELIABILITY_HIDDEN_STATUSES = {"planned", "rejected", "new"}
ACTIVE_PASSIVE_STATUS_BUCKETS = {
    "plunet_cloud": {
        "in preparation": "Product Queue",
        "backlog": None,
        "description update": "Product Queue",
        "refinement": "Product Queue",
        "ready for development": "Dev Queue",
        "development": "Active Work",
        "waiting for input": "Product Queue",
        "ready for code review": "Dev Queue",
        "code review": "Active Work",
        "ready for qa": "QA Queue",
        "test": "Active Work",
        "testing blocked": "Product Queue",
        "ready to merge": "Dev Queue",
        "merging": "Active Work",
        "reopened": "Dev Queue",
    },
    "standard_plunet": {
        "backlog": None,
        "assigned - ready to start": "Dev Queue",
        "in progress": "Active Work",
        "reopened": "Dev Queue",
        "solved - ready for approval": "Product Queue",
        "waiting for input": "Product Queue",
        "ready for code review": "Dev Queue",
        "code review": "Active Work",
        "ready for qa": "QA Queue",
        "test": "Active Work",
    },
}
INTERRUPTION_TOPIC_TYPES = {"tech_support", "unassigned_bug", "issue_without_feature"}
INTERRUPTION_ACTIVE_STATUSES = {"in progress", "development"}
REAL_INTERRUPTION_TEAMS = ("Team Tantrum", "Team World", "Cosmic Coders")
ENGINEERING_HEALTH_FOCUSED_TEAMS = ("Team Tantrum", "Team World", "Cosmic Coders")
ENGINEERING_HEALTH_OPTIONAL_TEAMS = ("FreeDevs",)
ENGINEERING_HEALTH_MAX_FLOW_COHORT_ISSUES = 8_000
CAPACITY_FORECAST_TEAMS = ("Team Tantrum", "Team World", "Cosmic Coders", "FreeDevs")
THROUGHPUT_REPORT_EXCLUDED_TEAMS = frozenset({"unknown", "legacy"})
CAPACITY_ROLE_BUCKETS = {"Developer": "Development", "QA": "QA"}
ENGINEERING_HEALTH_WEIGHTS = {
    "flow_efficiency": 0.25,
    "focus_health": 0.20,
    "interruption_health": 0.20,
    "execution_predictability": 0.20,
    "work_shape_health": 0.15,
}
ENGINEERING_HEALTH_COMPONENT_LABELS = {
    "flow_efficiency": "Flow efficiency",
    "focus_health": "Roadmap focus",
    "interruption_health": "Interruption pressure",
    "execution_predictability": "Throughput predictability",
    "work_shape_health": "Work shape risk",
}
INTERRUPTION_RECENT_START_DAYS = 56
INTERRUPTION_RECENT_BUG_START_DAYS = 112
INTERRUPTION_ACTIVITY_DAYS = 28
INTERRUPTION_ACTIVITY_FIELDS = {
    "comment",
    "description",
    "customfield_10180",
    "customfield_10181",
    "customfield_10182",
    "customers",
    "customer",
}
PRIORITY_RANKS = {
    "blocker": 5,
    "highest": 5,
    "critical": 5,
    "urgent": 5,
    "major": 4,
    "high": 4,
    "medium": 3,
    "normal": 3,
    "minor": 2,
    "low": 2,
    "lowest": 1,
    "trivial": 1,
}


@dataclass(frozen=True, slots=True)
class _ContributorTeam:
    team: str
    role_bucket: str
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class _IssueTeamAttribution:
    team: str
    confidence: str
    detail: str


def investment_category(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
    project_keys: list[str] | None,
) -> AnalyticsReportResponse:
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    stmt = select(MonthlyAllocatedEffort).where(
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated"))
    )
    if period_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= period_from)
    if period_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= period_to)
    if team:
        stmt = _filter_allocated_effort_by_assignment_team(stmt, team)
    if project_keys:
        stmt = stmt.join(JiraIssue, JiraIssue.id == MonthlyAllocatedEffort.issue_id).join(
            JiraProject, JiraProject.id == JiraIssue.project_id
        )
        stmt = stmt.where(JiraProject.key.in_(project_keys))
    stmt = scope_monthly_allocated_effort(stmt)
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in db.execute(stmt).scalars().all():
        month = row.period_month.isoformat()
        cat = _investment_category(row.topic_type)
        by_month[month][cat] += float(row.hours)
    series = []
    for month in sorted(by_month.keys()):
        series.append(
            {"period": month, **{cat: round(hours, 2) for cat, hours in by_month[month].items()}}
        )
    return AnalyticsReportResponse(
        filters={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "team": team,
            "project_keys": project_keys or [],
            "available_teams": _available_assignment_teams(
                db,
                date_from=period_from,
                date_to=period_to,
                project_keys=project_keys,
            ),
            "available_projects": _available_worklog_projects(
                db,
                date_from=period_from,
                date_to=period_to,
                team=team,
            ),
        },
        series=series,
    )


def _investment_category(topic_type: str) -> str:
    mapping = {
        "feature": "feature",
        "tech_support": "support",
        "unassigned_bug": "bugs_without_feature",
        "issue_without_feature": "small_improvements",
        "shared_overhead": "shared_overhead",
        "unclassified": "unclassified",
    }
    return mapping.get(topic_type, "unclassified")


def _filter_allocated_effort_by_assignment_team(stmt, team: str):
    return stmt.where(
        MonthlyAllocatedEffort.source_user_email.in_(
            select(JiraUserRoleAssignment.user_account_id).where(
                JiraUserRoleAssignment.active.is_(True),
                JiraUserRoleAssignment.team_name == team,
                JiraUserRoleAssignment.valid_from <= MonthlyAllocatedEffort.period_month,
                (JiraUserRoleAssignment.valid_to.is_(None))
                | (JiraUserRoleAssignment.valid_to >= MonthlyAllocatedEffort.period_month),
            )
        )
        | MonthlyAllocatedEffort.source_user_email.in_(
            select(JiraUserRoleAssignment.user_email).where(
                JiraUserRoleAssignment.active.is_(True),
                JiraUserRoleAssignment.team_name == team,
                JiraUserRoleAssignment.valid_from <= MonthlyAllocatedEffort.period_month,
                (JiraUserRoleAssignment.valid_to.is_(None))
                | (JiraUserRoleAssignment.valid_to >= MonthlyAllocatedEffort.period_month),
            )
        )
    )


def _allocated_effort_filter_base(date_from: date | None, date_to: date | None):
    stmt = select(MonthlyAllocatedEffort).where(
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated"))
    )
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    return scope_monthly_allocated_effort(stmt)


def _monthly_period_bounds(
    date_from: date | None,
    date_to: date | None,
) -> tuple[date | None, date | None]:
    """Monthly allocation is worklog-derived, so include the full month touched by a day filter."""
    period_from = date(date_from.year, date_from.month, 1) if date_from else None
    period_to = date(date_to.year, date_to.month, 1) if date_to else None
    return period_from, period_to


def _available_assignment_teams(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    project_keys: list[str] | None,
    role_names: frozenset[str] | None = None,
) -> list[str]:
    stmt = select(JiraUserRoleAssignment.team_name).select_from(MonthlyAllocatedEffort)
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    stmt = stmt.where(
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated"))
    )
    stmt = stmt.join(
        JiraUserRoleAssignment,
        (
            (JiraUserRoleAssignment.user_account_id == MonthlyAllocatedEffort.source_user_email)
            | (JiraUserRoleAssignment.user_email == MonthlyAllocatedEffort.source_user_email)
        )
        & (JiraUserRoleAssignment.active.is_(True))
        & (JiraUserRoleAssignment.valid_from <= MonthlyAllocatedEffort.period_month)
        & (
            (JiraUserRoleAssignment.valid_to.is_(None))
            | (JiraUserRoleAssignment.valid_to >= MonthlyAllocatedEffort.period_month)
        ),
    )
    if role_names:
        stmt = stmt.where(JiraUserRoleAssignment.role_name.in_(role_names))
    if project_keys:
        stmt = stmt.join(JiraIssue, JiraIssue.id == MonthlyAllocatedEffort.issue_id).join(
            JiraProject, JiraProject.id == JiraIssue.project_id
        )
        stmt = stmt.where(JiraProject.key.in_(project_keys))
    stmt = scope_monthly_allocated_effort(stmt)
    rows = (
        db.execute(stmt.where(JiraUserRoleAssignment.team_name.is_not(None)).distinct())
        .scalars()
        .all()
    )
    return sorted({team for team in rows if team})


def _available_worklog_projects(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
) -> list[dict[str, str | None]]:
    stmt = (
        select(JiraProject.key, JiraProject.name)
        .select_from(MonthlyAllocatedEffort)
        .join(JiraIssue, JiraIssue.id == MonthlyAllocatedEffort.issue_id)
        .join(JiraProject, JiraProject.id == JiraIssue.project_id)
    )
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    stmt = stmt.where(
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated"))
    )
    if team:
        stmt = _filter_allocated_effort_by_assignment_team(stmt, team)
    stmt = scope_monthly_allocated_effort(stmt)
    rows = db.execute(stmt.distinct().order_by(JiraProject.key)).all()
    return [{"key": key, "name": name} for key, name in rows if key]


def feature_cost(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
    feature_key: str | None,
) -> AnalyticsReportResponse:
    stmt = allocated_query(
        db,
        date_from=date_from,
        date_to=date_to,
        team=team,
        feature_key=feature_key,
    )
    stmt = stmt.where(MonthlyAllocatedEffort.topic_type == "feature")
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    names: dict[str, str] = {}
    for row in db.execute(stmt).scalars().all():
        key = row.feature_key or "unknown"
        names[key] = row.feature_name or key
        if row.allocation_kind == "direct_worklog":
            role = row.source_role_name or "Developer"
            grouped[key][f"direct_{role}"] += float(row.hours)
        elif row.allocation_kind == "indirect_allocated":
            grouped[key][f"allocated_{row.source_role_name}"] += float(row.hours)
        grouped[key]["total"] += float(row.hours)
    table = [
        {
            "feature": names[k],
            "feature_key": k,
            **{rk: round(rv, 2) for rk, rv in v.items()},
        }
        for k, v in sorted(grouped.items(), key=lambda x: -x[1].get("total", 0))
    ]
    return AnalyticsReportResponse(filters={}, table=table)


def issues_without_feature(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
    project_keys: list[str] | None = None,
    min_hours: float = 0,
) -> AnalyticsReportResponse:
    stmt = (
        select(MonthlyTopicEffortBase, JiraProject.key, JiraProject.name)
        .join(JiraIssue, JiraIssue.id == MonthlyTopicEffortBase.issue_id)
        .outerjoin(JiraProject, JiraProject.id == JiraIssue.project_id)
        .where(MonthlyTopicEffortBase.feature_root_id.is_(None))
    )
    if date_from:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month <= date_to)
    if team:
        stmt = stmt.where(MonthlyTopicEffortBase.team_name == team)
    if project_keys:
        stmt = stmt.where(JiraProject.key.in_(project_keys))
    stmt = scope_monthly_topic_effort(stmt)
    by_issue: dict[str, dict] = {}
    for row, project_key, project_name in db.execute(stmt).all():
        prev = by_issue.get(row.issue_key, {"hours": 0.0, "contributors": set()})
        prev["hours"] += float(row.direct_hours)
        if row.display_name:
            prev["contributors"].add(row.display_name)
        prev["issue_type"] = row.issue_type_name
        prev["team"] = row.team_name
        prev["summary"] = row.summary
        prev["project_key"] = project_key
        prev["project_name"] = project_name
        by_issue[row.issue_key] = prev
    table = []
    for key, v in by_issue.items():
        hours = v["hours"]
        if hours < min_hours:
            continue
        flags = []
        if hours > 40:
            flags.append("missing_feature_high_effort")
        if len(v["contributors"]) > 3:
            flags.append("missing_feature_many_people")
        table.append(
            {
                "issue_key": key,
                "issue_title": v.get("summary"),
                "project_key": v.get("project_key"),
                "project_name": v.get("project_name"),
                "type": v.get("issue_type"),
                "team": v.get("team"),
                "hours": round(hours, 2),
                "contributors": len(v["contributors"]),
                "flags": flags,
            }
        )
    table.sort(key=lambda x: -x["hours"])
    return AnalyticsReportResponse(
        filters={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "team": team,
            "project_keys": project_keys or [],
            "available_projects": _available_without_feature_projects(
                db,
                date_from=date_from,
                date_to=date_to,
                team=team,
            ),
        },
        table=table,
    )


def _available_without_feature_projects(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
) -> list[dict[str, str | None]]:
    stmt = (
        select(JiraProject.key, JiraProject.name)
        .select_from(MonthlyTopicEffortBase)
        .join(JiraIssue, JiraIssue.id == MonthlyTopicEffortBase.issue_id)
        .outerjoin(JiraProject, JiraProject.id == JiraIssue.project_id)
        .where(MonthlyTopicEffortBase.feature_root_id.is_(None))
        .where(JiraProject.key.is_not(None))
    )
    if date_from:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month <= date_to)
    if team:
        stmt = stmt.where(MonthlyTopicEffortBase.team_name == team)
    stmt = scope_monthly_topic_effort(stmt)
    rows = db.execute(stmt.distinct().order_by(JiraProject.key)).all()
    return [{"key": key, "name": name} for key, name in rows if key]


def investment_ranking(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
    limit: int = 50,
) -> AnalyticsReportResponse:
    stmt = allocated_query(
        db,
        date_from=date_from,
        date_to=date_to,
        team=team,
        feature_key=None,
    ).where(MonthlyAllocatedEffort.topic_type == "feature")
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_month: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    names: dict[str, str] = {}
    statuses = _feature_statuses(db)

    for row in db.execute(stmt).scalars().all():
        key = row.feature_key or "unknown"
        names[key] = row.feature_name or key
        bucket = _investment_role_bucket(row.allocation_kind, row.source_role_name)
        hours = float(row.hours)
        if bucket:
            grouped[key][bucket] += hours
            by_month[(key, row.period_month.isoformat())][bucket] += hours
        grouped[key]["total"] += hours
        by_month[(key, row.period_month.isoformat())]["total"] += hours

    table = []
    for rank, (key, values) in enumerate(
        sorted(grouped.items(), key=lambda x: -x[1].get("total", 0))[:limit],
        start=1,
    ):
        table.append(
            {
                "feature": names.get(key, key),
                "feature_key": key,
                "status": statuses.get(key, "planned"),
                "direct_dev": round(values.get("direct_dev", 0), 2),
                "direct_qa": round(values.get("direct_qa", 0), 2),
                "direct_ux": round(values.get("direct_ux", 0), 2),
                "product_overhead": round(values.get("product_overhead", 0), 2),
                "dev_overhead": round(values.get("dev_overhead", 0), 2),
                "total": round(values.get("total", 0), 2),
                "rank": rank,
            }
        )

    visible_features = {row["feature_key"] for row in table}
    series = [
        {
            "feature": names.get(feature_key, feature_key),
            "feature_key": feature_key,
            "period": period,
            "direct_dev": round(values.get("direct_dev", 0), 2),
            "direct_qa": round(values.get("direct_qa", 0), 2),
            "direct_ux": round(values.get("direct_ux", 0), 2),
            "product_overhead": round(values.get("product_overhead", 0), 2),
            "dev_overhead": round(values.get("dev_overhead", 0), 2),
            "total": round(values.get("total", 0), 2),
        }
        for (feature_key, period), values in sorted(by_month.items(), key=lambda item: item[0])
        if feature_key in visible_features
    ]
    return AnalyticsReportResponse(filters={}, table=table, series=series)


def _feature_statuses(db: Session) -> dict[str, str]:
    rows = db.execute(
        apply_feature_root_scope(
            apply_issue_scope(
                select(JiraFeatureRoot, JiraIssue, JiraIssueDetail)
                .join(JiraIssue, JiraIssue.id == JiraFeatureRoot.root_issue_id)
                .outerjoin(JiraIssueDetail, JiraIssueDetail.issue_id == JiraIssue.id)
            )
        )
    ).all()
    return {
        root.root_key: _investment_status(issue, detail)
        for root, issue, detail in rows
    }


def _investment_status(issue: JiraIssue, detail: JiraIssueDetail | None) -> str:
    status = (issue.status_name or "").strip().lower()
    category = (issue.status_category_key or issue.status_category_name or "").strip().lower()
    delivery_status = ((detail.delivery_status if detail else None) or "").strip().lower()
    if (
        issue.resolved_at_jira
        or (detail and detail.actual_end)
        or category == "done"
        or any(token in status for token in ("done", "closed", "resolved", "released", "shipped"))
        or any(
            token in delivery_status
            for token in ("done", "closed", "resolved", "released", "shipped")
        )
    ):
        return "done"
    if (
        detail
        and detail.actual_start
        or category in {"indeterminate", "in progress"}
        or any(
            token in status or token in delivery_status
            for token in ("progress", "running", "development", "doing", "review", "qa", "test")
        )
    ):
        return "running"
    return "planned"


def _investment_role_bucket(allocation_kind: str | None, role_name: str | None) -> str | None:
    role = (role_name or "").strip().lower()
    if allocation_kind == "direct_worklog":
        if role in {"developer", "dev", "software engineer", "engineer"} or "developer" in role:
            return "direct_dev"
        if role in {"qa", "quality assurance", "tester"} or "qa" in role or "test" in role:
            return "direct_qa"
        if role in {"ux", "user experience", "designer", "product designer"} or "ux" in role:
            return "direct_ux"
    if allocation_kind == "indirect_allocated":
        if role in {"po", "pm"} or "product owner" in role or "product manager" in role:
            return "product_overhead"
        if "architect" in role or "head of dev" in role or "head of development" in role:
            return "dev_overhead"
    return None


def work_allocation_heatmap(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
    mode: str = "combined",
) -> AnalyticsReportResponse:
    del mode  # legacy query param; heatmap always uses direct + indirect topic allocation
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    stmt = _allocated_effort_filter_base(period_from, period_to)
    assignment_cache: dict[tuple[str, date], JiraUserRoleAssignment | None] = {}
    topic_sort_keys: dict[str, tuple[int, str]] = {}
    matrix: dict[str, dict[str, dict[str, dict[str, float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    )
    for row in db.execute(stmt).scalars().all():
        if row.source_role_name not in HEATMAP_ROLES:
            continue
        if row.allocation_kind == "shared_overhead" or row.topic_type == "shared_overhead":
            continue
        cache_key = (row.source_user_email, row.period_month)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=row.source_user_email,
                display_name=row.source_display_name,
                as_of=row.period_month,
            )
        assignment = assignment_cache[cache_key]
        team_name = _normalized_team_name(assignment.team_name if assignment else None)
        if team and team_name != team:
            continue
        topic = _heatmap_topic_label(row)
        topic_sort_keys[topic] = _heatmap_topic_sort_key(row)
        person = row.source_display_name or "Unknown"
        matrix[team_name][topic][person][row.source_role_name] += float(row.hours)

    flat_table: list[dict[str, object]] = []
    series: list[dict[str, object]] = []
    for team_name in sorted(matrix.keys(), key=_team_sort_key):
        topics_map = matrix[team_name]
        topic_entries: list[dict[str, object]] = []
        team_role_hours: dict[str, float] = defaultdict(float)
        for topic in sorted(
            topics_map.keys(),
            key=lambda label: topic_sort_keys.get(label, (99, label.lower())),
        ):
            people_map = topics_map[topic]
            people: list[dict[str, object]] = []
            topic_role_hours: dict[str, float] = defaultdict(float)
            for person, role_hours in sorted(
                people_map.items(),
                key=lambda item: (-sum(item[1].values()), item[0].lower()),
            ):
                person_dev, person_qa, person_total = _heatmap_role_hour_totals(role_hours)
                if person_total <= 0:
                    continue
                for role, hours in role_hours.items():
                    topic_role_hours[role] += hours
                people.append(
                    {
                        "person": person,
                        "hours": round(person_total, 2),
                        "dev_hours": round(person_dev, 2),
                        "qa_hours": round(person_qa, 2),
                    }
                )
            if not people:
                continue
            topic_dev, topic_qa, topic_total = _heatmap_role_hour_totals(topic_role_hours)
            for role, hours in topic_role_hours.items():
                team_role_hours[role] += hours
            topic_entries.append(
                {
                    "topic": topic,
                    "people": people,
                    **_heatmap_role_hours_payload(topic_dev, topic_qa),
                }
            )
            for entry in people:
                flat_table.append(
                    {
                        "team": team_name,
                        "topic": topic,
                        "person": entry["person"],
                        "hours": entry["hours"],
                        "dev_hours": entry["dev_hours"],
                        "qa_hours": entry["qa_hours"],
                    }
                )
        if topic_entries:
            team_dev, team_qa, _team_total = _heatmap_role_hour_totals(team_role_hours)
            series.append(
                {
                    "team": team_name,
                    "topics": topic_entries,
                    **_heatmap_role_hours_payload(team_dev, team_qa),
                }
            )
    flat_table.sort(key=lambda row: (-float(row["hours"]), str(row["team"]).lower()))
    return AnalyticsReportResponse(
        filters={
            "roles": sorted(HEATMAP_ROLES),
            "available_teams": _teams_from_active_assignments(db, role_names=HEATMAP_ROLES),
        },
        series=series,
        table=flat_table[:2000],
    )


def _teams_from_active_assignments(
    db: Session,
    *,
    role_names: frozenset[str] | None = None,
) -> list[str]:
    stmt = (
        select(JiraUserRoleAssignment.team_name)
        .where(JiraUserRoleAssignment.active.is_(True))
        .where(JiraUserRoleAssignment.team_name.is_not(None))
        .distinct()
    )
    if role_names:
        stmt = stmt.where(JiraUserRoleAssignment.role_name.in_(role_names))
    rows = db.execute(stmt).scalars().all()
    return sorted({team for team in rows if team}, key=_team_sort_key)


def _heatmap_role_hour_totals(role_hours: dict[str, float]) -> tuple[float, float, float]:
    dev = float(role_hours.get("Developer", 0))
    qa = float(role_hours.get("QA", 0))
    return dev, qa, dev + qa


def _heatmap_role_hours_payload(dev_hours: float, qa_hours: float) -> dict[str, float]:
    return {
        "dev_hours": round(dev_hours, 2),
        "qa_hours": round(qa_hours, 2),
        "total_hours": round(dev_hours + qa_hours, 2),
    }


def _heatmap_topic_label(row: MonthlyAllocatedEffort) -> str:
    topic_type = (row.topic_type or "").strip()
    if topic_type == "issue_without_feature":
        return "Issue Without Feature"
    if topic_type == "unassigned_bug":
        return "Unassigned Bugs"
    if topic_type == "tech_support":
        return "Tech Support"
    feature_key = (row.feature_key or "").strip()
    if feature_key:
        feature_name = (row.feature_name or "").strip()
        return f"{feature_key} — {feature_name}" if feature_name else feature_key
    return (topic_type or "unclassified").replace("_", " ").title()


def _heatmap_topic_sort_key(row: MonthlyAllocatedEffort) -> tuple[int, str]:
    topic_type = (row.topic_type or "").strip()
    if topic_type == "issue_without_feature":
        return (0, "issue without feature")
    if topic_type == "unassigned_bug":
        return (1, "unassigned bugs")
    if topic_type == "tech_support":
        return (2, "tech support")
    feature_key = (row.feature_key or "").strip().upper()
    label = _heatmap_topic_label(row).lower()
    if topic_type == "feature" and feature_key.startswith("PMGT-"):
        return (3, label)
    if topic_type == "feature":
        return (4, label)
    return (5, label)


def planned_vs_unplanned(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
) -> AnalyticsReportResponse:
    planned_types = {"feature"}
    unplanned_types = {"tech_support", "unassigned_bug", "issue_without_feature"}
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    stmt = _allocated_effort_filter_base(period_from, period_to)
    assignment_cache: dict[tuple[str, date], JiraUserRoleAssignment | None] = {}
    by_team_month: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    all_months: set[str] = set()
    all_teams: set[str] = set()

    for row in db.execute(stmt).scalars().all():
        if row.source_role_name not in HEATMAP_ROLES:
            continue
        if row.allocation_kind == "shared_overhead" or row.topic_type == "shared_overhead":
            continue
        cache_key = (row.source_user_email, row.period_month)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=row.source_user_email,
                display_name=row.source_display_name,
                as_of=row.period_month,
            )
        assignment = assignment_cache[cache_key]
        team_name = _normalized_team_name(assignment.team_name if assignment else None)
        if team and team_name != team:
            continue
        month = row.period_month.isoformat()
        key = (team_name, month)
        if row.topic_type in planned_types:
            by_team_month[key]["roadmap_hours"] += float(row.hours)
        elif row.topic_type in unplanned_types:
            by_team_month[key]["continuous_improvement_hours"] += float(row.hours)
        all_months.add(month)
        all_teams.add(team_name)

    table = []
    by_period_team_focus: dict[tuple[str, str], float] = {}
    for (team_name, month), values in by_team_month.items():
        roadmap_hours = values.get("roadmap_hours", 0.0)
        continuous_improvement_hours = values.get("continuous_improvement_hours", 0.0)
        total_focus_hours = roadmap_hours + continuous_improvement_hours
        roadmap_focus = (roadmap_hours / total_focus_hours) if total_focus_hours > 0 else None
        table.append(
            {
                "team": team_name,
                "month": month,
                "roadmap_hours": round(roadmap_hours, 2),
                "continuous_improvement_hours": round(continuous_improvement_hours, 2),
                "roadmap_focus": round(roadmap_focus, 4) if roadmap_focus is not None else None,
            }
        )
        by_period_team_focus[(month, team_name)] = (
            round(roadmap_focus, 4) if roadmap_focus is not None else 0.0
        )
    table.sort(key=lambda row: (str(row["month"]), str(row["team"]).lower()), reverse=True)

    ordered_months = sorted(all_months)
    ordered_teams = sorted(all_teams, key=_team_sort_key)
    series = []
    for month in ordered_months:
        row: dict[str, object] = {"period": month}
        for team_name in ordered_teams:
            row[team_name] = by_period_team_focus.get((month, team_name), 0.0)
        series.append(row)

    return AnalyticsReportResponse(
        filters={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "team": team,
            "available_teams": ordered_teams,
        },
        table=table,
        series=series,
    )


def availability_vs_booked(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
) -> AnalyticsReportResponse:
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    team_filter = _normalized_team_name(team) if team else None
    cells: dict[tuple[str, str, str], dict[str, object]] = {}
    all_months: set[str] = set()
    all_teams: set[str] = set()
    assignment_cache: dict[tuple[str, str | None, date], JiraUserRoleAssignment | None] = {}

    def assignment_for(
        *,
        source_user_email: str,
        display_name: str | None,
        as_of: date,
    ) -> JiraUserRoleAssignment | None:
        cache_key = (source_user_email, display_name, as_of)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=source_user_email,
                display_name=display_name,
                as_of=as_of,
            )
        return assignment_cache[cache_key]

    def cell_for(
        *,
        team_name: str,
        month: str,
        person_key: str,
        person: str,
        role: str | None,
    ) -> dict[str, object]:
        key = (team_name, month, person_key)
        if key not in cells:
            cells[key] = {
                "team": team_name,
                "month": month,
                "person": person,
                "role": role,
                "available_hours": 0.0,
                "clocked_hours": 0.0,
                "logged_hours": 0.0,
            }
        elif role and not cells[key].get("role"):
            cells[key]["role"] = role
        all_months.add(month)
        all_teams.add(team_name)
        return cells[key]

    hrworks_stmt = select(JiraUserMonthlyHrworksHours, JiraUser).join(
        JiraUser,
        JiraUser.id == JiraUserMonthlyHrworksHours.jira_user_id,
    )
    if period_from:
        hrworks_stmt = hrworks_stmt.where(JiraUserMonthlyHrworksHours.month_start >= period_from)
    if period_to:
        hrworks_stmt = hrworks_stmt.where(JiraUserMonthlyHrworksHours.month_start <= period_to)

    for hours_row, user in db.execute(hrworks_stmt).all():
        source_key = user.account_id or user.email_address or user.display_name
        assignment = assignment_for(
            source_user_email=source_key,
            display_name=user.display_name,
            as_of=hours_row.month_start,
        )
        if not assignment or assignment.role_name not in HEATMAP_ROLES:
            continue
        team_name = _normalized_team_name(assignment.team_name)
        if team_filter and team_name != team_filter:
            continue
        month = hours_row.month_start.isoformat()
        person_key = str(
            assignment.jira_user_id or user.id or assignment.user_account_id or source_key
        )
        person = assignment.display_name or user.display_name or "Unknown"
        cell = cell_for(
            team_name=team_name,
            month=month,
            person_key=person_key,
            person=person,
            role=assignment.role_name,
        )
        cell["available_hours"] = float(cell["available_hours"]) + float(
            hours_row.planned_working_hours
        )
        cell["clocked_hours"] = float(cell["clocked_hours"]) + float(
            hours_row.clocked_working_hours
        )

    topic_stmt = select(MonthlyTopicEffortBase).where(
        MonthlyTopicEffortBase.role_name.in_(HEATMAP_ROLES)
    )
    if period_from:
        topic_stmt = topic_stmt.where(MonthlyTopicEffortBase.period_month >= period_from)
    if period_to:
        topic_stmt = topic_stmt.where(MonthlyTopicEffortBase.period_month <= period_to)
    topic_stmt = scope_monthly_topic_effort(topic_stmt)

    for row in db.execute(topic_stmt).scalars().all():
        source_key = row.user_account_id or row.display_name or "unknown"
        assignment = assignment_for(
            source_user_email=source_key,
            display_name=row.display_name,
            as_of=row.period_month,
        )
        if not assignment or assignment.role_name not in HEATMAP_ROLES:
            continue
        team_name = _normalized_team_name(assignment.team_name)
        if team_filter and team_name != team_filter:
            continue
        month = row.period_month.isoformat()
        person_key = str(assignment.jira_user_id or assignment.user_account_id or source_key)
        person = assignment.display_name or row.display_name or "Unknown"
        cell = cell_for(
            team_name=team_name,
            month=month,
            person_key=person_key,
            person=person,
            role=assignment.role_name or row.role_name,
        )
        cell["logged_hours"] = float(cell["logged_hours"]) + float(row.direct_hours)

    table: list[dict[str, object]] = []
    by_month_team: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    people_by_month_team: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    total_available = 0.0
    total_clocked = 0.0
    total_logged = 0.0
    missing_hrworks_people: set[tuple[str, str, str]] = set()
    team_available_totals: dict[str, float] = defaultdict(float)
    for values in cells.values():
        team_available_totals[str(values["team"])] += float(values["available_hours"])

    for (_team_name, _month, _person_key), values in sorted(
        cells.items(),
        key=lambda item: (
            str(item[1]["month"]),
            _team_sort_key(str(item[1]["team"])),
            str(item[1]["person"]).lower(),
        ),
    ):
        if team_available_totals[str(values["team"])] <= 0:
            continue
        available = float(values["available_hours"])
        logged = float(values["logged_hours"])
        clocked = float(values["clocked_hours"])
        remaining = available - logged
        ratio = (logged / available) if available > 0 else None
        payload = {
            "month": values["month"],
            "team": values["team"],
            "person": values["person"],
            "role": values["role"],
            "available_hours": round(available, 2),
            "clocked_hours": round(clocked, 2),
            "logged_hours": round(logged, 2),
            "remaining_hours": round(remaining, 2),
            "utilization_ratio": round(ratio, 4) if ratio is not None else None,
        }
        table.append(payload)
        key = (str(values["month"]), str(values["team"]))
        by_month_team[key]["available_hours"] += available
        by_month_team[key]["clocked_hours"] += clocked
        by_month_team[key]["logged_hours"] += logged
        people_by_month_team[key].append(payload)
        total_available += available
        total_clocked += clocked
        total_logged += logged
        if available <= 0 and logged > 0:
            missing_hrworks_people.add(
                (str(values["month"]), str(values["team"]), str(values["person"]))
            )

    table.sort(
        key=lambda row: (str(row["month"]), str(row["team"]).lower(), str(row["person"]).lower()),
        reverse=True,
    )

    ordered_months = sorted({month for month, _team_name in by_month_team})
    ordered_teams = sorted(
        {team_name for _month, team_name in by_month_team},
        key=_team_sort_key,
    )
    series: list[dict[str, object]] = []
    for month in ordered_months:
        series_row: dict[str, object] = {"period": month, "teams": []}
        teams_payload: list[dict[str, object]] = []
        for team_name in ordered_teams:
            totals = by_month_team.get((month, team_name))
            if not totals:
                series_row[f"{team_name}__logged_hours"] = 0.0
                series_row[f"{team_name}__remaining_hours"] = 0.0
                series_row[f"{team_name}__available_hours"] = 0.0
                series_row[f"{team_name}__utilization_ratio"] = None
                continue
            available = totals.get("available_hours", 0.0)
            logged = totals.get("logged_hours", 0.0)
            clocked = totals.get("clocked_hours", 0.0)
            remaining = available - logged
            ratio = (logged / available) if available > 0 else None
            team_payload = {
                "team": team_name,
                "month": month,
                "available_hours": round(available, 2),
                "clocked_hours": round(clocked, 2),
                "logged_hours": round(logged, 2),
                "remaining_hours": round(remaining, 2),
                "utilization_ratio": round(ratio, 4) if ratio is not None else None,
                "people": sorted(
                    people_by_month_team[(month, team_name)],
                    key=lambda person: (
                        -float(person["logged_hours"]),
                        str(person["person"]).lower(),
                    ),
                ),
            }
            teams_payload.append(team_payload)
            series_row[f"{team_name}__logged_hours"] = round(logged, 2)
            series_row[f"{team_name}__remaining_hours"] = round(max(remaining, 0.0), 2)
            series_row[f"{team_name}__available_hours"] = round(available, 2)
            series_row[f"{team_name}__utilization_ratio"] = (
                round(ratio, 4) if ratio is not None else None
            )
        series_row["teams"] = teams_payload
        series.append(series_row)

    total_ratio = (total_logged / total_available) if total_available > 0 else None
    return AnalyticsReportResponse(
        filters={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "team": team_filter,
            "roles": sorted(HEATMAP_ROLES),
            "available_teams": list(CAPACITY_FORECAST_TEAMS),
            "chart_teams": ordered_teams,
        },
        summary={
            "available_hours": round(total_available, 2),
            "clocked_hours": round(total_clocked, 2),
            "logged_hours": round(total_logged, 2),
            "remaining_hours": round(total_available - total_logged, 2),
            "utilization_ratio": round(total_ratio, 4) if total_ratio is not None else None,
            "missing_hrworks_people": len(missing_hrworks_people),
        },
        table=table[:5000],
        series=series,
    )


def capacity_forecast(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
) -> AnalyticsReportResponse:
    period_from, period_to = _capacity_forecast_period(date_from, date_to)
    months = _month_start_dates(period_from, period_to)
    periods = [month.isoformat() for month in months]
    team_filter = _normalized_team_name(team) if team else None
    selected_teams = [
        team_name
        for team_name in CAPACITY_FORECAST_TEAMS
        if team_filter is None or team_name == team_filter
    ]

    person_rows: dict[tuple[str, str, str], dict[str, object]] = {}
    totals: dict[tuple[str, str, str], float] = defaultdict(float)

    def person_key_for(assignment: JiraUserRoleAssignment, fallback: object | None = None) -> str:
        return str(
            assignment.jira_user_id
            or assignment.user_account_id
            or assignment.user_email
            or fallback
            or assignment.display_name
        )

    def role_bucket(role: str | None) -> str | None:
        return CAPACITY_ROLE_BUCKETS.get((role or "").strip())

    def row_for(
        *,
        team_name: str,
        bucket: str,
        person_key: str,
        person: str,
        role: str,
    ) -> dict[str, object]:
        key = (team_name, bucket, person_key)
        if key not in person_rows:
            person_rows[key] = {
                "team": team_name,
                "role_bucket": bucket,
                "role": role,
                "person_key": person_key,
                "person": person,
                "hours_by_period": {period: 0.0 for period in periods},
                "total_hours": 0.0,
            }
        return person_rows[key]

    assignments = db.execute(
        select(JiraUserRoleAssignment).where(
            JiraUserRoleAssignment.active.is_(True),
            JiraUserRoleAssignment.role_name.in_(HEATMAP_ROLES),
            JiraUserRoleAssignment.valid_from <= period_to,
            (JiraUserRoleAssignment.valid_to.is_(None))
            | (JiraUserRoleAssignment.valid_to >= period_from),
        )
    ).scalars().all()
    for assignment in assignments:
        team_name = _normalized_team_name(assignment.team_name)
        if team_name not in selected_teams:
            continue
        bucket = role_bucket(assignment.role_name)
        if bucket is None:
            continue
        person_key = person_key_for(assignment)
        for month in months:
            if not _assignment_valid_for_month(assignment, month):
                continue
            row_for(
                team_name=team_name,
                bucket=bucket,
                person_key=person_key,
                person=assignment.display_name,
                role=assignment.role_name,
            )

    hrworks_stmt = select(JiraUserMonthlyHrworksHours, JiraUser).join(
        JiraUser,
        JiraUser.id == JiraUserMonthlyHrworksHours.jira_user_id,
    )
    hrworks_stmt = hrworks_stmt.where(
        JiraUserMonthlyHrworksHours.month_start >= period_from,
        JiraUserMonthlyHrworksHours.month_start <= period_to,
    )

    for hours_row, user in db.execute(hrworks_stmt).all():
        source_key = user.account_id or user.email_address or user.display_name
        assignment = get_assignment_for_allocated_source(
            db,
            source_user_email=source_key,
            display_name=user.display_name,
            as_of=hours_row.month_start,
        )
        if assignment is None:
            continue
        team_name = _normalized_team_name(assignment.team_name)
        if team_name not in selected_teams:
            continue
        bucket = role_bucket(assignment.role_name)
        if bucket is None:
            continue
        month = date(hours_row.month_start.year, hours_row.month_start.month, 1)
        period = month.isoformat()
        if period not in periods:
            continue
        hours = float(hours_row.planned_working_hours)
        person_key = person_key_for(assignment, user.id)
        row = row_for(
            team_name=team_name,
            bucket=bucket,
            person_key=person_key,
            person=assignment.display_name or user.display_name or "Unknown",
            role=assignment.role_name,
        )
        hours_by_period = row["hours_by_period"]
        if isinstance(hours_by_period, dict):
            hours_by_period[period] = round(float(hours_by_period.get(period, 0.0)) + hours, 2)
        row["total_hours"] = round(float(row["total_hours"]) + hours, 2)
        totals[(team_name, period, bucket)] += hours

    table = sorted(
        person_rows.values(),
        key=lambda row: (
            _team_sort_key(str(row["team"])),
            0 if row["role_bucket"] == "Development" else 1,
            str(row["person"]).lower(),
        ),
    )

    series: list[dict[str, object]] = []
    for period in periods:
        series_row: dict[str, object] = {"period": period, "teams": []}
        team_payloads: list[dict[str, object]] = []
        for team_name in selected_teams:
            development = totals.get((team_name, period, "Development"), 0.0)
            qa = totals.get((team_name, period, "QA"), 0.0)
            total = development + qa
            series_row[f"{team_name}__development_hours"] = round(development, 2)
            series_row[f"{team_name}__qa_hours"] = round(qa, 2)
            series_row[f"{team_name}__total_hours"] = round(total, 2)
            team_payloads.append(
                {
                    "team": team_name,
                    "month": period,
                    "development_hours": round(development, 2),
                    "qa_hours": round(qa, 2),
                    "total_hours": round(total, 2),
                }
            )
        series_row["teams"] = team_payloads
        series.append(series_row)

    development_total = sum(
        value for (_team_name, _period, bucket), value in totals.items() if bucket == "Development"
    )
    qa_total = sum(
        value for (_team_name, _period, bucket), value in totals.items() if bucket == "QA"
    )
    return AnalyticsReportResponse(
        filters={
            "from": period_from.isoformat(),
            "to": period_to.isoformat(),
            "team": team_filter,
            "periods": periods,
            "roles": ["Development", "QA"],
            "available_teams": selected_teams,
            "chart_teams": [team_name for team_name in selected_teams if team_name != "FreeDevs"],
            "explanation": (
                "Capacity means available working hours from HRWorks, already reduced "
                "by out-of-office."
            ),
        },
        summary={
            "available_hours": round(development_total + qa_total, 2),
            "development_hours": round(development_total, 2),
            "qa_hours": round(qa_total, 2),
            "months": len(periods),
            "teams": len(selected_teams),
            "people": len(table),
        },
        table=table,
        series=series,
    )


def real_interruption_ratio(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None,
) -> AnalyticsReportResponse:
    team_filter = _normalized_team_name(team) if team else None
    if team_filter and team_filter not in REAL_INTERRUPTION_TEAMS:
        team_filter = None
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    start_events = _latest_active_start_by_issue(
        db,
        date_from=date_from,
        date_to=date_to,
    )
    if not start_events:
        return AnalyticsReportResponse(
            filters=_real_interruption_filters(date_from=date_from, date_to=date_to, team=team_filter),
            table=[],
            series=[],
        )

    issues = {
        issue.id: issue
        for issue in db.execute(select(JiraIssue).where(JiraIssue.id.in_(start_events))).scalars().all()
    }
    team_by_issue = _interruption_issue_teams(
        db,
        issue_ids=set(start_events.keys()),
        date_from=period_from,
        date_to=period_to,
    )
    hours_by_issue = _interruption_issue_hours(
        db,
        issue_ids=set(start_events.keys()),
        date_from=period_from,
        date_to=period_to,
    )
    topic_type_by_issue = _interruption_issue_topic_types(
        db,
        issue_ids=set(start_events.keys()),
        date_from=period_from,
        date_to=period_to,
    )
    issue_rows: list[dict[str, object]] = []
    monthly: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for issue_id, active_start in start_events.items():
        issue = issues.get(issue_id)
        if issue is None:
            continue
        issue_hours = hours_by_issue.get(issue_id, {})
        roadmap_hours = issue_hours.get("roadmap_hours", 0.0)
        continuous_improvement_hours = issue_hours.get("continuous_improvement_hours", 0.0)
        if roadmap_hours <= 0 and continuous_improvement_hours <= 0:
            continue
        team_name = team_by_issue.get(issue_id, "Unknown")
        if team_name not in REAL_INTERRUPTION_TEAMS:
            continue
        if team_filter and team_name != team_filter:
            continue
        topic_type = topic_type_by_issue.get(issue_id)
        evidence = _interruption_evidence(issue, active_start, topic_type=topic_type)
        confidence = _interruption_confidence(evidence)
        is_interrupted = continuous_improvement_hours > 0 and confidence in {"high", "medium"}
        month = date(active_start.year, active_start.month, 1).isoformat()
        if roadmap_hours > 0:
            monthly[(team_name, month)]["started_roadmap_issues"] += 1
            monthly[(team_name, month)]["started_roadmap_hours"] += roadmap_hours
        if is_interrupted:
            monthly[(team_name, month)]["interrupting_issues"] += 1
            monthly[(team_name, month)]["interrupting_hours"] += continuous_improvement_hours
        elif continuous_improvement_hours > 0 and confidence == "weak":
            monthly[(team_name, month)]["maybe_interrupted_issues"] += 1
        issue_rows.append(
            {
                "issue_key": issue.key,
                "issue_title": issue.summary,
                "team": team_name,
                "month": month,
                "active_start": active_start.isoformat(),
                "priority": issue.priority_name,
                "topic_type": topic_type,
                "classification": "interrupted"
                if is_interrupted
                else "maybe_interrupted"
                if confidence == "weak"
                else "planned_or_unknown",
                "confidence": confidence,
                "signals": evidence["signals"],
                "score": evidence["score"],
                "activity_events": evidence["activity_events"],
                "priority_escalations": evidence["priority_escalations"],
                "days_created_to_start": evidence["days_created_to_start"],
                "roadmap_hours": round(roadmap_hours, 2),
                "continuous_improvement_hours": round(continuous_improvement_hours, 2),
            }
        )

    table = []
    teams: set[str] = set()
    months: set[str] = set()
    for (team_name, month), values in monthly.items():
        started_roadmap = int(values.get("started_roadmap_issues", 0))
        interrupting = int(values.get("interrupting_issues", 0))
        maybe = int(values.get("maybe_interrupted_issues", 0))
        started_roadmap_hours = values.get("started_roadmap_hours", 0.0)
        interrupting_hours = values.get("interrupting_hours", 0.0)
        issue_total = started_roadmap + interrupting
        time_total = started_roadmap_hours + interrupting_hours
        issue_ratio = interrupting / issue_total if issue_total else 0
        time_ratio = interrupting_hours / time_total if time_total else 0
        teams.add(team_name)
        months.add(month)
        table.append(
            {
                "team": team_name,
                "month": month,
                "started_roadmap_issues": started_roadmap,
                "interrupting_issues": interrupting,
                "maybe_interrupted_issues": maybe,
                "interruption_ratio": round(issue_ratio, 4),
                "started_roadmap_hours": round(started_roadmap_hours, 2),
                "interrupting_hours": round(interrupting_hours, 2),
                "time_interruption_ratio": round(time_ratio, 4),
            }
        )
    table.sort(key=lambda row: (str(row["month"]), str(row["team"]).lower()), reverse=True)

    series = []
    time_series = []
    ordered_teams = sorted(teams, key=_team_sort_key)
    for month in sorted(months):
        row: dict[str, object] = {"period": month}
        time_row: dict[str, object] = {"period": month}
        for team_name in ordered_teams:
            values = monthly.get((team_name, month), {})
            started_roadmap = int(values.get("started_roadmap_issues", 0))
            interrupting = int(values.get("interrupting_issues", 0))
            started_roadmap_hours = values.get("started_roadmap_hours", 0.0)
            interrupting_hours = values.get("interrupting_hours", 0.0)
            issue_total = started_roadmap + interrupting
            time_total = started_roadmap_hours + interrupting_hours
            row[team_name] = round(interrupting / issue_total, 4) if issue_total else 0.0
            time_row[team_name] = round(interrupting_hours / time_total, 4) if time_total else 0.0
        series.append(row)
        time_series.append(time_row)

    issue_rows.sort(key=lambda row: (str(row["active_start"]), str(row["issue_key"])), reverse=True)
    return AnalyticsReportResponse(
        filters={
            **_real_interruption_filters(date_from=date_from, date_to=date_to, team=team_filter),
            "evidence_notes": [
                "Priority/activity signals require raw Jira changelog JSON. If absent, only creation-to-start evidence is available.",
                "Activity-only evidence is classified as maybe_interrupted and is not included in the ratio numerator.",
                "Bug candidates created within 16 weeks before active start are always treated as interrupting.",
            ],
            "issue_rows": issue_rows[:500],
            "time_series": time_series,
        },
        table=table,
        series=series,
    )


def _real_interruption_filters(*, date_from: date | None, date_to: date | None, team: str | None) -> dict[str, object]:
    return {
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "team": team,
        "topic_types": sorted(INTERRUPTION_TOPIC_TYPES),
        "active_statuses": sorted(INTERRUPTION_ACTIVE_STATUSES),
        "available_teams": list(REAL_INTERRUPTION_TEAMS),
    }


def _latest_active_start_by_issue(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
) -> dict[int, datetime]:
    stmt = select(JiraIssueStatusTransition).where(
        JiraIssueStatusTransition.to_status_name.in_(("In Progress", "Development"))
    )
    if date_from:
        stmt = stmt.where(
            JiraIssueStatusTransition.changed_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to:
        stmt = stmt.where(
            JiraIssueStatusTransition.changed_at
            <= datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        )
    rows = db.execute(stmt.order_by(JiraIssueStatusTransition.changed_at.asc())).scalars().all()
    starts: dict[int, datetime] = {}
    for row in rows:
        starts[int(row.issue_id)] = row.changed_at
    return starts


def _is_interruption_active_status(status_name: str | None) -> bool:
    return (status_name or "").strip().lower() in INTERRUPTION_ACTIVE_STATUSES


def _interruption_issue_teams(
    db: Session,
    *,
    issue_ids: set[int],
    date_from: date | None,
    date_to: date | None,
) -> dict[int, str]:
    if not issue_ids:
        return {}
    stmt = select(MonthlyAllocatedEffort).where(
        MonthlyAllocatedEffort.issue_id.in_(issue_ids),
        MonthlyAllocatedEffort.topic_type.in_(INTERRUPTION_TOPIC_TYPES | {"feature"}),
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated")),
    )
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    stmt = scope_monthly_allocated_effort(stmt)
    assignment_cache: dict[tuple[str, date], JiraUserRoleAssignment | None] = {}
    team_hours: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in db.execute(stmt).scalars().all():
        if row.source_role_name not in HEATMAP_ROLES:
            continue
        cache_key = (row.source_user_email, row.period_month)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=row.source_user_email,
                display_name=row.source_display_name,
                as_of=row.period_month,
            )
        assignment = assignment_cache[cache_key]
        team_name = _normalized_team_name(assignment.team_name if assignment else None)
        team_hours[int(row.issue_id)][team_name] += float(row.hours)
    return {
        issue_id: max(hours.items(), key=lambda item: (item[1], item[0] != "Unknown"))[0]
        for issue_id, hours in team_hours.items()
        if hours
    }


def _interruption_issue_hours(
    db: Session,
    *,
    issue_ids: set[int],
    date_from: date | None,
    date_to: date | None,
) -> dict[int, dict[str, float]]:
    if not issue_ids:
        return {}
    stmt = select(MonthlyAllocatedEffort).where(
        MonthlyAllocatedEffort.issue_id.in_(issue_ids),
        MonthlyAllocatedEffort.topic_type.in_(INTERRUPTION_TOPIC_TYPES | {"feature"}),
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated")),
    )
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    stmt = scope_monthly_allocated_effort(stmt)
    by_issue: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in db.execute(stmt).scalars().all():
        if row.source_role_name not in HEATMAP_ROLES:
            continue
        key = "roadmap_hours" if row.topic_type == "feature" else "continuous_improvement_hours"
        by_issue[int(row.issue_id)][key] += float(row.hours)
    return by_issue


def _interruption_issue_topic_types(
    db: Session,
    *,
    issue_ids: set[int],
    date_from: date | None,
    date_to: date | None,
) -> dict[int, str]:
    if not issue_ids:
        return {}
    stmt = select(MonthlyAllocatedEffort.issue_id, MonthlyAllocatedEffort.topic_type).where(
        MonthlyAllocatedEffort.issue_id.in_(issue_ids),
        MonthlyAllocatedEffort.topic_type.in_(INTERRUPTION_TOPIC_TYPES),
    )
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    stmt = scope_monthly_allocated_effort(stmt)
    topic_rank = {"unassigned_bug": 0, "tech_support": 1, "issue_without_feature": 2}
    by_issue: dict[int, str] = {}
    for issue_id, topic_type in db.execute(stmt).all():
        if issue_id is None or topic_type is None:
            continue
        previous = by_issue.get(int(issue_id))
        if previous is None or topic_rank.get(str(topic_type), 99) < topic_rank.get(previous, 99):
            by_issue[int(issue_id)] = str(topic_type)
    return by_issue


def _interruption_evidence(
    issue: JiraIssue,
    active_start: datetime,
    *,
    topic_type: str | None,
) -> dict[str, object]:
    signals: list[str] = []
    score = 0
    days_created_to_start: int | None = None
    if issue.created_at_jira:
        days_created_to_start = max(0, (_as_utc_datetime(active_start) - _as_utc_datetime(issue.created_at_jira)).days)
        if _is_bug_candidate(issue, topic_type) and days_created_to_start <= INTERRUPTION_RECENT_BUG_START_DAYS:
            signals.append("bug_created_within_16_weeks_before_start")
            score += 3
        elif days_created_to_start <= INTERRUPTION_RECENT_START_DAYS:
            signals.append("created_within_8_weeks_before_start")
            score += 2

    priority_escalations = _priority_escalations_before_start(issue, active_start)
    if priority_escalations:
        signals.append("priority_increased_within_8_weeks_before_start")
        score += 3

    activity_events = _activity_events_before_start(issue, active_start)
    if activity_events >= 2:
        signals.append("serious_activity_within_4_weeks_before_start")
        score += 1

    return {
        "signals": signals,
        "score": score,
        "priority_escalations": priority_escalations,
        "activity_events": activity_events,
        "days_created_to_start": days_created_to_start,
    }


def _interruption_confidence(evidence: dict[str, object]) -> str:
    signals = set(evidence.get("signals") if isinstance(evidence.get("signals"), list) else [])
    score = int(evidence.get("score") or 0)
    if (
        "bug_created_within_16_weeks_before_start" in signals
        or "priority_increased_within_8_weeks_before_start" in signals
        or score >= 3
    ):
        return "high"
    if "created_within_8_weeks_before_start" in signals:
        return "medium"
    if "serious_activity_within_4_weeks_before_start" in signals:
        return "weak"
    return "none"


def _is_bug_candidate(issue: JiraIssue, topic_type: str | None) -> bool:
    issue_type = (issue.issue_type_name or "").strip().lower()
    return topic_type == "unassigned_bug" or "bug" in issue_type


def _priority_escalations_before_start(issue: JiraIssue, active_start: datetime) -> int:
    count = 0
    for history, item in _raw_changelog_items(issue):
        changed_at = _raw_history_changed_at(history)
        if changed_at is None or not _within_lookback(changed_at, active_start, INTERRUPTION_RECENT_START_DAYS):
            continue
        field = str(item.get("field") or item.get("fieldId") or "").strip().lower()
        if field != "priority":
            continue
        if _priority_rank(item.get("toString")) > _priority_rank(item.get("fromString")):
            count += 1
    return count


def _activity_events_before_start(issue: JiraIssue, active_start: datetime) -> int:
    count = 0
    for history, item in _raw_changelog_items(issue):
        changed_at = _raw_history_changed_at(history)
        if changed_at is None or not _within_lookback(changed_at, active_start, INTERRUPTION_ACTIVITY_DAYS):
            continue
        field = str(item.get("fieldId") or item.get("field") or "").strip().lower()
        if field in INTERRUPTION_ACTIVITY_FIELDS:
            count += 1
    return count


def _raw_changelog_items(issue: JiraIssue) -> list[tuple[dict, dict]]:
    raw_issue = issue.raw_issue_json if isinstance(issue.raw_issue_json, dict) else {}
    changelog = raw_issue.get("changelog") if isinstance(raw_issue.get("changelog"), dict) else {}
    histories = changelog.get("histories") or changelog.get("values")
    if not isinstance(histories, list):
        return []
    items: list[tuple[dict, dict]] = []
    for history in histories:
        if not isinstance(history, dict):
            continue
        raw_items = history.get("items")
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if isinstance(item, dict):
                items.append((history, item))
    return items


def _raw_history_changed_at(history: dict) -> datetime | None:
    value = history.get("created")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc_datetime(parsed)


def _within_lookback(changed_at: datetime, active_start: datetime, days: int) -> bool:
    changed = _as_utc_datetime(changed_at)
    start = _as_utc_datetime(active_start)
    return start - timedelta(days=days) <= changed <= start


def _priority_rank(value: object) -> int:
    raw = str(value or "").strip().lower()
    return PRIORITY_RANKS.get(raw, 0)


def _first_worklog_by_issue(db: Session) -> dict[int, datetime]:
    rows = db.execute(
        apply_worklog_issue_scope(
            select(JiraWorklog.issue_id, func.min(JiraWorklog.started_at))
            .where(JiraWorklog.started_at.is_not(None))
            .group_by(JiraWorklog.issue_id)
        )
    ).all()
    return {issue_id: started for issue_id, started in rows if started is not None}


def _feature_worklog_bounds(db: Session) -> dict[str, dict[str, datetime | int | None]]:
    root_issue = aliased(JiraIssue)
    stmt = (
        select(
            JiraFeatureRoot.root_key,
            func.min(JiraWorklog.started_at),
            func.max(JiraWorklog.started_at),
            func.min(root_issue.created_at_jira),
        )
        .join(root_issue, root_issue.id == JiraFeatureRoot.root_issue_id)
        .join(JiraFeatureMembership, JiraFeatureMembership.feature_root_id == JiraFeatureRoot.id)
        .join(JiraWorklog, JiraWorklog.issue_id == JiraFeatureMembership.member_issue_id)
        .where(JiraWorklog.started_at.is_not(None))
        .group_by(JiraFeatureRoot.root_key)
    )
    rows = db.execute(apply_worklog_issue_scope(apply_feature_root_scope(stmt))).all()
    bounds = {}
    for feature_key, first_worklog, last_worklog, created_at in rows:
        bounds[feature_key] = {
            "first_worklog": first_worklog,
            "last_worklog": last_worklog,
            "production_duration_days": _days_between(first_worklog, last_worklog),
            "idle_before_work_days": _days_between(created_at, first_worklog),
        }
    return bounds


def _lifecycle_start(
    issue: JiraIssue,
    detail: JiraIssueDetail | None,
    first_worklog: datetime | None,
) -> datetime | None:
    if detail and detail.actual_start:
        return _as_utc_datetime(detail.actual_start)
    if detail and detail.start_date:
        return datetime.combine(detail.start_date, time.min, tzinfo=timezone.utc)
    if first_worklog:
        return _as_utc_datetime(first_worklog)
    return None


def _lifecycle_end(issue: JiraIssue, detail: JiraIssueDetail | None) -> datetime | None:
    if detail and detail.actual_end:
        return _as_utc_datetime(detail.actual_end)
    if issue.resolved_at_jira:
        return _as_utc_datetime(issue.resolved_at_jira)
    status = (issue.status_name or "").lower()
    if status in {"done", "closed", "resolved"} and issue.updated_at_jira:
        return _as_utc_datetime(issue.updated_at_jira)
    return None


def feature_lifecycle(
    db: Session,
    *,
    team: str | None = None,
    include_created_year: bool = False,
) -> AnalyticsReportResponse:
    roots = db.execute(
        apply_feature_root_scope(
            apply_issue_scope(
                select(JiraFeatureRoot, JiraIssue, JiraIssueDetail)
                .join(JiraIssue, JiraIssue.id == JiraFeatureRoot.root_issue_id)
                .outerjoin(JiraIssueDetail, JiraIssueDetail.issue_id == JiraIssue.id)
            )
        )
    ).all()
    worklog_starts = _first_worklog_by_issue(db)
    table = []
    yearly_groups: dict[tuple[str, int], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    yearly_counts: dict[tuple[str, int], int] = defaultdict(int)
    now = datetime.now(timezone.utc)
    for root, issue, detail in roots:
        row_team = _normalized_team_name(detail.team_name if detail else None)
        if team and not _team_matches(row_team, team):
            continue
        created = _as_utc_datetime(issue.created_at_jira) if issue.created_at_jira else None
        first_wl = worklog_starts.get(issue.id)
        start = _lifecycle_start(issue, detail, first_wl)
        end = _lifecycle_end(issue, detail)
        end_source = _lifecycle_end_source(issue, detail)
        idea_to_start = _days_between(created, start)
        has_end = end_source is not None and end is not None
        start_to_done = _days_between(start, end) if has_end else None
        total = _days_between(created, end) if has_end else None
        elapsed = total if total is not None else _days_between(created, now)
        if created:
            _add_yearly_average_sample(
                yearly_groups,
                yearly_counts,
                team=row_team,
                year=created.year,
                idea_to_start_days=idea_to_start,
                start_to_done_days=start_to_done,
                total_duration_days=total,
                elapsed_duration_days=elapsed,
            )
        row = {
            "feature": root.root_key,
            "feature_name": root.name,
            "idea_to_start_days": idea_to_start,
            "start_to_done_days": start_to_done,
            "total_duration_days": total,
            "elapsed_duration_days": elapsed,
            "status": issue.status_name,
            "team": row_team,
            "date_source": _lifecycle_start_source(detail, first_wl),
            "end_date_source": end_source,
        }
        if include_created_year:
            row["_created_year"] = created.year if created else None
        table.append(row)
    return AnalyticsReportResponse(
        filters={"yearly_team_averages": _yearly_average_rows(yearly_groups, yearly_counts)},
        table=table,
    )


def _lifecycle_start_source(
    detail: JiraIssueDetail | None,
    first_worklog: datetime | None,
) -> str:
    if detail and detail.actual_start:
        return "actual_start"
    if detail and detail.start_date:
        return "start_date"
    if first_worklog:
        return "first_worklog"
    return "created_only"


def _lifecycle_end_source(issue: JiraIssue, detail: JiraIssueDetail | None) -> str | None:
    if detail and detail.actual_end:
        return "actual_end"
    if issue.resolved_at_jira:
        return "resolved_at_jira"
    status = (issue.status_name or "").lower()
    if status in {"done", "closed", "resolved"} and issue.updated_at_jira:
        return "status_updated_at"
    return None


def promised_vs_actual(db: Session, *, team: str | None = None) -> AnalyticsReportResponse:
    rows = db.execute(
        apply_feature_root_scope(
            apply_issue_scope(
                select(JiraFeatureRoot, JiraIssue, JiraIssueDetail)
                .join(JiraIssue, JiraIssue.id == JiraFeatureRoot.root_issue_id)
                .join(JiraIssueDetail, JiraIssueDetail.issue_id == JiraIssue.id)
                .where(JiraIssueDetail.promised_delivery_date.is_not(None))
            )
        )
    ).all()
    actual_dates = _feature_last_member_closed_dates(
        db,
        [root.id for root, _issue, _detail in rows],
    )
    table = []
    yearly_groups: dict[tuple[str, int], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    yearly_counts: dict[tuple[str, int], int] = defaultdict(int)
    for root, issue, detail in rows:
        row_team = _normalized_team_name(detail.team_name)
        if team and not _team_matches(row_team, team):
            continue
        if _is_rejected_issue(issue, detail):
            continue
        promised = detail.promised_delivery_date
        actual = actual_dates.get(root.id) or detail.actual_end or issue.resolved_at_jira
        actual_d = _date_part(actual)
        delay = (actual_d - promised).days if actual_d and promised else None
        if promised:
            _add_yearly_average_sample(
                yearly_groups,
                yearly_counts,
                team=row_team,
                year=promised.year,
                delay_days=delay,
            )
        table.append(
            {
                "feature": root.root_key,
                "feature_title": root.name or issue.summary or root.root_key,
                "promised": promised.isoformat() if promised else None,
                "actual": actual_d.isoformat() if actual_d else None,
                "delay_days": delay,
                "team": row_team,
                "status": issue.status_name,
            }
        )
    return AnalyticsReportResponse(
        filters={"yearly_team_averages": _yearly_average_rows(yearly_groups, yearly_counts)},
        table=table,
    )


def _feature_last_member_closed_dates(db: Session, feature_root_ids: list[int]) -> dict[int, date]:
    if not feature_root_ids:
        return {}

    member_issue = aliased(JiraIssue)
    member_detail = aliased(JiraIssueDetail)
    member_project = aliased(JiraProject)
    rows = db.execute(
        select(JiraFeatureMembership.feature_root_id, member_issue, member_detail)
        .join(member_issue, member_issue.id == JiraFeatureMembership.member_issue_id)
        .outerjoin(member_detail, member_detail.issue_id == member_issue.id)
        .outerjoin(member_project, member_project.id == member_issue.project_id)
        .where(JiraFeatureMembership.feature_root_id.in_(feature_root_ids))
        .where(
            or_(
                member_issue.project_id.is_(None),
                member_project.key.notin_(tuple(EXCLUDED_PROJECT_KEYS)),
            )
        )
    ).all()
    last_closed: dict[int, date] = {}
    for feature_root_id, issue, detail in rows:
        if _is_rejected_issue(issue, detail):
            continue
        closed_at = _closed_at(issue, detail)
        closed_date = _date_part(closed_at)
        if closed_date is None:
            continue
        is_latest = feature_root_id not in last_closed or closed_date > last_closed[feature_root_id]
        if is_latest:
            last_closed[feature_root_id] = closed_date
    return last_closed


def _closed_at(issue: JiraIssue, detail: JiraIssueDetail | None) -> datetime | date | None:
    if detail and detail.actual_end:
        return detail.actual_end
    if issue.resolved_at_jira:
        return issue.resolved_at_jira
    status = (issue.status_name or "").strip().lower()
    category = (issue.status_category_key or issue.status_category_name or "").strip().lower()
    if (status in {"done", "closed", "resolved"} or category == "done") and issue.updated_at_jira:
        return issue.updated_at_jira
    return None


def _date_part(value: datetime | date | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _is_rejected_issue(issue: JiraIssue, detail: JiraIssueDetail | None = None) -> bool:
    values = [
        issue.status_name,
        issue.resolution_name,
        detail.delivery_status if detail else None,
    ]
    return any((value or "").strip().lower() == "rejected" for value in values)


def idea_aging(
    db: Session,
    *,
    min_age_days: int = 0,
    team: str | None = None,
) -> AnalyticsReportResponse:
    lc = feature_lifecycle(db, team=team, include_created_year=True)
    table = []
    yearly_groups: dict[tuple[str, int], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    yearly_counts: dict[tuple[str, int], int] = defaultdict(int)
    for row in lc.table or []:
        waiting = row.get("idea_to_start_days")
        if waiting is None:
            continue
        if waiting >= min_age_days:
            output_row = {key: value for key, value in row.items() if not key.startswith("_")}
            output_row["waiting_days"] = waiting
            table.append(output_row)
            _add_yearly_average_sample(
                yearly_groups,
                yearly_counts,
                team=_normalized_team_name(row.get("team")),
                year=row.get("_created_year"),
                waiting_days=waiting,
            )
    table.sort(key=lambda x: -(x.get("waiting_days") or 0))
    return AnalyticsReportResponse(
        filters={"yearly_team_averages": _yearly_average_rows(yearly_groups, yearly_counts)},
        table=table,
    )


def status_waiting_time(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    project_keys: list[str] | None = None,
    include_other_workflows: bool = False,
) -> AnalyticsReportResponse:
    workflows_configured = bool(scoped_workflow_ids(db))
    available_projects = available_status_waiting_projects(db)
    scoped_project_keys = filter_excluded_keys(project_keys) if project_keys else None
    sections = build_status_waiting_sections(
        db,
        date_from=date_from,
        date_to=date_to,
        project_keys=scoped_project_keys,
        include_other_workflows=include_other_workflows,
    )
    table: list[dict] = []
    for entry in sections["main_workflows"] + sections["other_workflows"]:
        section = "main" if entry in sections["main_workflows"] else "other"
        for row in entry.get("rows") or []:
            table.append(
                {
                    "section": section,
                    "workflow": entry.get("label"),
                    "workflow_name": entry.get("workflow_name"),
                    **row,
                }
            )
    return AnalyticsReportResponse(
        filters={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "project_keys": project_keys or [],
            "include_other_workflows": include_other_workflows,
            "workflows_synced": workflows_configured,
            "available_projects": available_projects,
            "main_workflows": sections["main_workflows"],
            "other_workflows": sections["other_workflows"],
        },
        table=table,
    )


def active_vs_passive(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    team: str | None = None,
    issue_type: str | None = None,
    workflow: str | None = None,
) -> AnalyticsReportResponse:
    allowed_workflow_ids = scoped_workflow_ids(db)
    if not allowed_workflow_ids:
        return AnalyticsReportResponse(
            filters={
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
                "team": team,
                "issue_type": issue_type,
                "workflow": workflow,
                "date_basis": "issue_created",
                "date_basis_label": "Issue created date",
                "workflows_synced": False,
                "available_teams": [],
                "available_projects": available_status_waiting_projects(db),
                "main_workflows": [],
            },
            table=[],
        )

    available_projects = available_status_waiting_projects(db)
    project_keys = [project["key"] for project in available_projects if project.get("key")]
    cohort_issue_ids = _active_passive_issue_ids_by_created_date(
        db,
        project_keys=project_keys or None,
        date_from=date_from,
        date_to=date_to,
    )
    intervals = build_status_intervals(db, issue_ids=cohort_issue_ids)
    issue_ids = {interval.issue_id for interval in intervals}
    workflow_by_issue = resolve_workflow_ids_for_issues(db, issue_ids)
    main_workflow_ids = {
        workflow_id
        for workflow_id in workflow_by_issue.values()
        if workflow_id in allowed_workflow_ids
    }
    relevant_issue_ids = {
        interval.issue_id
        for interval in intervals
        if workflow_by_issue.get(interval.issue_id) in main_workflow_ids
    }
    workflows = load_workflows_by_id(
        db,
        main_workflow_ids,
    )
    workflow_by_spec = _main_workflows_by_spec(workflows)
    attribution_by_issue = _active_passive_issue_attributions(db, relevant_issue_ids)

    selected_workflow = (workflow or "").strip()
    selected_issue_type = (issue_type or "").strip()
    by_workflow_team: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    all_teams: set[str] = set()
    sections: list[dict] = []

    for spec in MAIN_WORKFLOW_SPECS:
        workflow_row = workflow_by_spec.get(spec.catalog_key)
        data_points: list[dict] = []
        if workflow_row is not None:
            for iv in intervals:
                if workflow_by_issue.get(iv.issue_id) != workflow_row.id:
                    continue
                if not issue_type_eligible_for_main_spec(iv.issue_type_name, spec):
                    continue
                if selected_workflow and selected_workflow not in {
                    spec.catalog_key,
                    spec.label,
                    workflow_row.name,
                }:
                    continue
                if selected_issue_type and not issue_type_matches_catalog_option(
                    iv.issue_type_name,
                    selected_issue_type,
                ):
                    continue
                seconds = iv.duration_seconds
                if seconds <= 0:
                    continue
                attribution = attribution_by_issue.get(
                    iv.issue_id,
                    _IssueTeamAttribution(
                        team="Unknown",
                        confidence="unknown",
                        detail="No PMGT team and no assigned worklog contributor team.",
                    ),
                )
                all_teams.add(attribution.team)
                if team and not _team_matches(attribution.team, team):
                    continue
                cls = _active_passive_status_bucket(iv.status_name, spec)
                if cls is None:
                    continue
                hours = seconds / 3600.0
                by_workflow_team[(spec.label, attribution.team)][cls] += hours
                data_points.append(
                    {
                        "issue_id": iv.issue_id,
                        "issue_key": iv.issue_key,
                        "issue_type": (iv.issue_type_name or "").strip(),
                        "team": attribution.team,
                        "confidence": attribution.confidence,
                        "attribution_detail": attribution.detail,
                        "status_class": cls,
                        "hours": hours,
                    }
                )

        issue_type_options = sorted(
            {str(point["issue_type"]) for point in data_points if point.get("issue_type")},
            key=str.lower,
        )
        sections.append(
            {
                "catalog_key": spec.catalog_key,
                "label": spec.label,
                "workflow_id": workflow_row.id if workflow_row else None,
                "workflow_name": workflow_row.name if workflow_row else spec.label,
                "issue_type_options": issue_type_options,
                "projects": projects_for_workflow(db, workflow_row.id) if workflow_row else [],
                "data_points": data_points,
            }
        )

    table = []
    for (workflow_label, team_name), buckets in sorted(
        by_workflow_team.items(),
        key=lambda item: (item[0][0].lower(), _team_sort_key(item[0][1])),
    ):
        table.append(
            {
                "workflow": workflow_label,
                "team": team_name,
                **{k: round(v, 2) for k, v in sorted(buckets.items())},
            }
        )
    return AnalyticsReportResponse(
        filters={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "team": team,
            "issue_type": issue_type,
            "workflow": workflow,
            "date_basis": "issue_created",
            "date_basis_label": "Issue created date",
            "workflows_synced": True,
            "available_teams": sorted(all_teams, key=_team_sort_key),
            "available_workflows": [
                spec.label
                for spec in MAIN_WORKFLOW_SPECS
                if workflow_by_spec.get(spec.catalog_key) is not None
            ],
            "available_projects": available_projects,
            "main_workflows": sections,
        },
        table=table,
    )


def active_vs_passive_trend(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    team: str | None = None,
    workflow: str | None = None,
) -> AnalyticsReportResponse:
    allowed_workflow_ids = scoped_workflow_ids(db)
    available_projects = available_status_waiting_projects(db)
    project_keys = [project["key"] for project in available_projects if project.get("key")]
    if not allowed_workflow_ids:
        return AnalyticsReportResponse(
            filters={
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
                "team": team,
                "workflow": workflow,
                "grain": "quarter",
                "date_basis": "status_interval_overlap",
                "date_basis_label": "Status interval overlap",
                "workflows_synced": False,
                "available_teams": [],
                "available_projects": available_projects,
            },
            summary={},
            series=[],
            table=[],
        )

    effective_from, effective_to = bound_quarter_period(date_from, date_to)
    intervals = build_status_intervals(
        db,
        project_keys=project_keys or None,
        date_from=effective_from,
        date_to=effective_to,
    )
    issue_ids = {interval.issue_id for interval in intervals}
    workflow_by_issue = resolve_workflow_ids_for_issues(db, issue_ids)
    main_workflow_ids = {
        workflow_id
        for workflow_id in workflow_by_issue.values()
        if workflow_id in allowed_workflow_ids
    }
    relevant_issue_ids = {
        interval.issue_id
        for interval in intervals
        if workflow_by_issue.get(interval.issue_id) in main_workflow_ids
    }
    workflows = load_workflows_by_id(db, main_workflow_ids)
    workflow_by_spec = _main_workflows_by_spec(workflows)
    attribution_by_issue = _active_passive_issue_attributions(db, relevant_issue_ids)
    quarters = _quarter_date_ranges(effective_from, effective_to)
    now_utc = datetime.now(timezone.utc)
    selected_workflow = (workflow or "").strip()

    bucket_totals: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    all_teams: set[str] = set()
    available_workflow_labels = [
        spec.label
        for spec in MAIN_WORKFLOW_SPECS
        if workflow_by_spec.get(spec.catalog_key) is not None
    ]

    for spec in MAIN_WORKFLOW_SPECS:
        workflow_row = workflow_by_spec.get(spec.catalog_key)
        if workflow_row is None:
            continue
        if selected_workflow and selected_workflow not in {
            spec.catalog_key,
            spec.label,
            workflow_row.name,
        }:
            continue
        for iv in intervals:
            if workflow_by_issue.get(iv.issue_id) != workflow_row.id:
                continue
            if not issue_type_eligible_for_main_spec(iv.issue_type_name, spec):
                continue
            cls = _active_passive_status_bucket(iv.status_name, spec)
            if cls is None:
                continue
            attribution = attribution_by_issue.get(
                iv.issue_id,
                _IssueTeamAttribution(
                    team="Unknown",
                    confidence="unknown",
                    detail="No PMGT team and no assigned worklog contributor team.",
                ),
            )
            all_teams.add(attribution.team)
            if team and not _team_matches(attribution.team, team):
                continue
            interval_end = iv.interval_end or now_utc
            for quarter_key, _, quarter_start, quarter_end in quarters:
                seconds = _interval_overlap_seconds_dt(
                    iv.interval_start,
                    interval_end,
                    quarter_start,
                    quarter_end,
                )
                if seconds <= 0:
                    continue
                bucket_totals[(quarter_key, attribution.team, spec.label)][cls] += seconds / 3600.0

    table: list[dict[str, object]] = []
    previous_by_group: dict[tuple[str, str], dict[str, float]] = {}
    for quarter_key, quarter_label, quarter_start, quarter_end in quarters:
        group_keys = sorted(
            {
                (team_name, workflow_label)
                for period, team_name, workflow_label in bucket_totals
                if period == quarter_key
            },
            key=lambda item: (_team_sort_key(item[0]), item[1].lower()),
        )
        for team_name, workflow_label in group_keys:
            buckets = bucket_totals[(quarter_key, team_name, workflow_label)]
            row = _active_passive_trend_row(
                quarter_key=quarter_key,
                quarter_label=quarter_label,
                quarter_start=quarter_start,
                quarter_end=quarter_end,
                team_name=team_name,
                workflow_label=workflow_label,
                buckets=buckets,
            )
            previous = previous_by_group.get((team_name, workflow_label))
            if previous:
                row["passive_share_delta"] = _round_optional(
                    row["passive_share"] - previous["passive_share"]
                    if row["passive_share"] is not None and previous["passive_share"] is not None
                    else None,
                    4,
                )
                row["total_hours_delta"] = round(row["total_hours"] - previous["total_hours"], 2)
            else:
                row["passive_share_delta"] = None
                row["total_hours_delta"] = None
            previous_by_group[(team_name, workflow_label)] = {
                "passive_share": row["passive_share"],
                "total_hours": row["total_hours"],
            }
            table.append(row)

    series = _active_passive_trend_series(quarters, bucket_totals)
    summary = _active_passive_trend_summary(series)
    return AnalyticsReportResponse(
        filters={
            "from": effective_from.isoformat(),
            "to": effective_to.isoformat(),
            "team": team,
            "workflow": workflow,
            "grain": "quarter",
            "date_basis": "status_interval_overlap",
            "date_basis_label": "Status interval overlap",
            "workflows_synced": True,
            "available_teams": sorted(all_teams, key=_team_sort_key),
            "available_workflows": available_workflow_labels,
            "available_projects": available_projects,
        },
        summary=summary,
        series=series,
        table=table,
    )


def _active_passive_trend_row(
    *,
    quarter_key: str,
    quarter_label: str,
    quarter_start: date,
    quarter_end: date,
    team_name: str,
    workflow_label: str,
    buckets: dict[str, float],
) -> dict[str, object]:
    active = buckets.get("Active Work", 0.0)
    product_queue = buckets.get("Product Queue", 0.0)
    dev_queue = buckets.get("Dev Queue", 0.0)
    qa_queue = buckets.get("QA Queue", 0.0)
    passive = product_queue + dev_queue + qa_queue
    total = active + passive
    return {
        "period": quarter_key,
        "quarter": quarter_label,
        "quarter_start": quarter_start.isoformat(),
        "quarter_end": quarter_end.isoformat(),
        "team": team_name,
        "workflow": workflow_label,
        "active_hours": round(active, 2),
        "passive_hours": round(passive, 2),
        "product_queue_hours": round(product_queue, 2),
        "dev_queue_hours": round(dev_queue, 2),
        "qa_queue_hours": round(qa_queue, 2),
        "total_hours": round(total, 2),
        "passive_share": round(passive / total, 4) if total > 0 else None,
    }


def _active_passive_trend_series(
    quarters: list[tuple[str, str, date, date]],
    bucket_totals: dict[tuple[str, str, str], dict[str, float]],
) -> list[dict[str, object]]:
    series: list[dict[str, object]] = []
    previous_share: float | None = None
    for quarter_key, quarter_label, quarter_start, quarter_end in quarters:
        active = 0.0
        product_queue = 0.0
        dev_queue = 0.0
        qa_queue = 0.0
        team_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for (period, team_name, _workflow_label), buckets in bucket_totals.items():
            if period != quarter_key:
                continue
            active += buckets.get("Active Work", 0.0)
            product_queue += buckets.get("Product Queue", 0.0)
            dev_queue += buckets.get("Dev Queue", 0.0)
            qa_queue += buckets.get("QA Queue", 0.0)
            for bucket, value in buckets.items():
                team_totals[team_name][bucket] += value
        passive = product_queue + dev_queue + qa_queue
        total = active + passive
        passive_share = round(passive / total, 4) if total > 0 else None
        row: dict[str, object] = {
            "period": quarter_key,
            "quarter": quarter_label,
            "quarter_start": quarter_start.isoformat(),
            "quarter_end": quarter_end.isoformat(),
            "active_hours": round(active, 2),
            "passive_hours": round(passive, 2),
            "product_queue_hours": round(product_queue, 2),
            "dev_queue_hours": round(dev_queue, 2),
            "qa_queue_hours": round(qa_queue, 2),
            "total_hours": round(total, 2),
            "passive_share": passive_share,
            "passive_share_delta": _round_optional(
                passive_share - previous_share
                if passive_share is not None and previous_share is not None
                else None,
                4,
            ),
        }
        sorted_team_totals = sorted(
            team_totals.items(),
            key=lambda item: _team_sort_key(item[0]),
        )
        for team_name, team_buckets in sorted_team_totals:
            team_active = team_buckets.get("Active Work", 0.0)
            team_passive = sum(
                value for bucket, value in team_buckets.items() if bucket != "Active Work"
            )
            team_total = team_active + team_passive
            row[f"{team_name}__passive_share"] = (
                round(team_passive / team_total, 4) if team_total > 0 else None
            )
            row[f"{team_name}__active_hours"] = round(team_active, 2)
            row[f"{team_name}__passive_hours"] = round(team_passive, 2)
        if passive_share is not None:
            previous_share = passive_share
        series.append(row)
    return series


def _active_passive_trend_summary(series: list[dict[str, object]]) -> dict[str, object]:
    populated = [row for row in series if isinstance(row.get("passive_share"), float)]
    if not populated:
        return {}
    latest = populated[-1]
    previous = populated[-2] if len(populated) > 1 else None
    best = min(populated, key=lambda row: float(row["passive_share"]))
    worst = max(populated, key=lambda row: float(row["passive_share"]))
    latest_passive_share = float(latest["passive_share"])
    previous_passive_share = None
    if previous and previous.get("passive_share") is not None:
        previous_passive_share = float(previous["passive_share"])
    return {
        "latest_quarter": latest["period"],
        "latest_passive_share": latest_passive_share,
        "previous_passive_share": previous_passive_share,
        "passive_share_delta": _round_optional(
            latest_passive_share - previous_passive_share
            if previous_passive_share is not None
            else None,
            4,
        ),
        "best_quarter": best["period"],
        "best_passive_share": best["passive_share"],
        "worst_quarter": worst["period"],
        "worst_passive_share": worst["passive_share"],
    }


def bound_quarter_period(
    date_from: date | None,
    date_to: date | None,
    *,
    default_quarters: int = DEFAULT_TREND_QUARTERS,
    max_quarters: int = MAX_TREND_QUARTERS,
) -> tuple[date, date]:
    """Clamp workflow trend windows so heavy interval scans stay bounded."""
    today = datetime.now(timezone.utc).date()
    effective_to = date_to or today
    if date_from:
        effective_from = date_from
    else:
        effective_from = _add_quarters(_quarter_start(effective_to), -(default_quarters - 1))
    earliest_allowed = _add_quarters(_quarter_start(effective_to), -(max_quarters - 1))
    if effective_from < earliest_allowed:
        effective_from = earliest_allowed
    if effective_from > effective_to:
        effective_from = _quarter_start(effective_to)
    return effective_from, effective_to


def _iter_issue_id_chunks(issue_ids: set[int], chunk_size: int = ISSUE_ID_CHUNK_SIZE):
    issue_id_list = sorted(issue_ids)
    for offset in range(0, len(issue_id_list), chunk_size):
        yield issue_id_list[offset : offset + chunk_size]


def _quarter_date_ranges(date_from: date, date_to: date) -> list[tuple[str, str, date, date]]:
    ranges: list[tuple[str, str, date, date]] = []
    current = _quarter_start(date_from)
    while current <= date_to:
        next_start = _add_quarters(current, 1)
        quarter_end = min(date_to, next_start - timedelta(days=1))
        quarter = ((current.month - 1) // 3) + 1
        key = f"{current.year}-Q{quarter}"
        ranges.append((key, f"Q{quarter} {current.year}", max(current, date_from), quarter_end))
        current = next_start
    return ranges


def _quarter_start(value: date) -> date:
    month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, month, 1)


def _add_quarters(value: date, quarters: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + quarters * 3
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _interval_overlap_seconds(
    interval_start: datetime,
    interval_end: datetime | None,
    date_from: date,
    date_to: date,
) -> float:
    interval_end_dt = interval_end or datetime.now(timezone.utc)
    return _interval_overlap_seconds_dt(interval_start, interval_end_dt, date_from, date_to)


def _interval_overlap_seconds_dt(
    interval_start: datetime,
    interval_end: datetime,
    date_from: date,
    date_to: date,
) -> float:
    range_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    range_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start = max(interval_start, range_start)
    end = min(interval_end, range_end)
    return max(0.0, (end - start).total_seconds())


def _round_optional(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def _main_workflows_by_spec(workflows: dict[int, JiraWorkflow]) -> dict[str, JiraWorkflow]:
    by_spec: dict[str, JiraWorkflow] = {}
    for spec in MAIN_WORKFLOW_SPECS:
        for workflow in workflows.values():
            name = getattr(workflow, "name", None)
            if name and workflow_matches_main_spec(name, spec):
                by_spec[spec.catalog_key] = workflow
                break
    return by_spec


def _issue_created_month_by_id(db: Session, issue_ids: list[int]) -> dict[int, str]:
    month_by_issue: dict[int, str] = {}
    for chunk in _iter_issue_id_chunks(set(issue_ids)):
        rows = db.execute(
            select(JiraIssue.id, JiraIssue.created_at_jira).where(JiraIssue.id.in_(chunk))
        ).all()
        for issue_id, created_at in rows:
            if created_at is None:
                continue
            created_on = created_at.date()
            month_by_issue[int(issue_id)] = date(created_on.year, created_on.month, 1).isoformat()
    return month_by_issue


def _active_passive_issue_ids_by_created_date(
    db: Session,
    *,
    project_keys: list[str] | None,
    date_from: date | None,
    date_to: date | None,
) -> list[int]:
    stmt = apply_issue_scope(select(JiraIssue.id))
    if project_keys:
        stmt = stmt.where(JiraProject.key.in_(project_keys))
    if date_from is not None:
        stmt = stmt.where(
            JiraIssue.created_at_jira
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        stmt = stmt.where(
            JiraIssue.created_at_jira
            <= datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        )
    return [int(issue_id) for issue_id in db.execute(stmt).scalars().all()]


def _active_passive_status_bucket(status_name: str | None, spec: MainWorkflowSpec) -> str | None:
    status_key = (status_name or "").strip().lower()
    if not status_key:
        return None
    return ACTIVE_PASSIVE_STATUS_BUCKETS.get(spec.catalog_key, {}).get(status_key)


def _active_passive_issue_attributions(
    db: Session,
    issue_ids: set[int],
) -> dict[int, _IssueTeamAttribution]:
    if not issue_ids:
        return {}
    issue_pmgt_teams = _active_passive_pmgt_teams_by_issue(db, issue_ids)
    contributors = _active_passive_contributors_by_issue(db, issue_ids)
    return {
        issue_id: _attribute_active_passive_issue(
            pmgt_teams=issue_pmgt_teams.get(issue_id, set()),
            contributors=contributors.get(issue_id, []),
        )
        for issue_id in issue_ids
    }


def _active_passive_pmgt_teams_by_issue(
    db: Session,
    issue_ids: set[int],
) -> dict[int, set[str]]:
    teams_by_issue: dict[int, set[str]] = defaultdict(set)
    RootDetail = aliased(JiraIssueDetail)
    for chunk in _iter_issue_id_chunks(issue_ids):
        rows = db.execute(
            select(JiraFeatureMembership.member_issue_id, RootDetail.team_name)
            .join(JiraFeatureRoot, JiraFeatureRoot.id == JiraFeatureMembership.feature_root_id)
            .join(RootDetail, RootDetail.issue_id == JiraFeatureRoot.root_issue_id)
            .where(JiraFeatureMembership.member_issue_id.in_(chunk))
        ).all()
        for issue_id, team_name in rows:
            teams_by_issue[int(issue_id)].update(_team_parts(team_name))
    return teams_by_issue


def _active_passive_contributors_by_issue(
    db: Session,
    issue_ids: set[int],
) -> dict[int, list[_ContributorTeam]]:
    assignments = (
        db.execute(select(JiraUserRoleAssignment).where(JiraUserRoleAssignment.active.is_(True)))
        .scalars()
        .all()
    )
    by_issue: dict[int, list[_ContributorTeam]] = defaultdict(list)
    seen: set[tuple[int, str, str]] = set()
    for chunk in _iter_issue_id_chunks(issue_ids):
        worklogs = db.execute(
            select(
                JiraWorklog.issue_id,
                JiraWorklog.author_account_id,
                JiraWorklog.author_email_address,
                JiraWorklog.author_display_name,
                JiraWorklog.started_at,
            ).where(JiraWorklog.issue_id.in_(chunk))
        ).all()
        for issue_id, account_id, email, display_name, started_at in worklogs:
            assignment = _assignment_for_worklog(
                assignments,
                account_id=str(account_id or "").strip() or None,
                email=str(email or "").strip() or None,
                started_at=started_at,
            )
            team = _normalized_team_name(assignment.team_name) if assignment else "Unknown"
            role_bucket = _active_passive_role_bucket(assignment.role_name if assignment else None)
            contributor_name = (
                str(display_name or "").strip()
                or str(email or "").strip()
                or str(account_id or "").strip()
                or None
            )
            key = (int(issue_id), team, role_bucket)
            if key in seen:
                continue
            seen.add(key)
            by_issue[int(issue_id)].append(
                _ContributorTeam(team=team, role_bucket=role_bucket, display_name=contributor_name)
            )
    return by_issue


def _assignment_for_worklog(
    assignments: list[JiraUserRoleAssignment],
    *,
    account_id: str | None,
    email: str | None,
    started_at: datetime | None,
) -> JiraUserRoleAssignment | None:
    as_of = (started_at or datetime.now(timezone.utc)).date()
    matches: list[JiraUserRoleAssignment] = []
    for assignment in assignments:
        assignment_account = (assignment.user_account_id or "").strip()
        assignment_email = (assignment.user_email or "").strip()
        if account_id and assignment_account != account_id:
            if not email or assignment_email.lower() != email.lower():
                continue
        elif email and assignment_email.lower() != email.lower():
            continue
        if assignment.valid_from > as_of:
            continue
        if assignment.valid_to is not None and assignment.valid_to < as_of:
            continue
        matches.append(assignment)
    if matches:
        team_matches = [row for row in matches if (row.team_name or "").strip()]
        return sorted(team_matches or matches, key=lambda row: row.valid_from, reverse=True)[0]

    identity_matches: list[JiraUserRoleAssignment] = []
    for assignment in assignments:
        assignment_account = (assignment.user_account_id or "").strip()
        assignment_email = (assignment.user_email or "").strip()
        if account_id and assignment_account == account_id:
            identity_matches.append(assignment)
            continue
        if email and assignment_email.lower() == email.lower():
            identity_matches.append(assignment)
    if not identity_matches:
        return None
    team_matches = [row for row in identity_matches if (row.team_name or "").strip()]
    return sorted(team_matches or identity_matches, key=lambda row: row.valid_from, reverse=True)[0]


def _attribute_active_passive_issue(
    *,
    pmgt_teams: set[str],
    contributors: list[_ContributorTeam],
) -> _IssueTeamAttribution:
    if "CoP" in pmgt_teams:
        return _IssueTeamAttribution(team="CoP", confidence="pmgt_cop", detail="PMGT team is CoP.")

    contributor_teams = {item.team for item in contributors if item.team != "Unknown"}
    dev_teams = {
        item.team for item in contributors if item.role_bucket == "dev" and item.team != "Unknown"
    }
    qa_teams = {
        item.team for item in contributors if item.role_bucket == "qa" and item.team != "Unknown"
    }

    if pmgt_teams and len(contributor_teams) == 1:
        only_team = next(iter(contributor_teams))
        if only_team in pmgt_teams:
            return _IssueTeamAttribution(
                team=only_team,
                confidence="definite",
                detail="PMGT team and contributor assignment team match.",
            )

    if len(contributor_teams) == 1 and not pmgt_teams:
        return _IssueTeamAttribution(
            team=next(iter(contributor_teams)),
            confidence="definite",
            detail="All assigned worklog contributors are from this team.",
        )

    if pmgt_teams:
        dev_matches = dev_teams & pmgt_teams
        if len(dev_matches) == 1:
            return _IssueTeamAttribution(
                team=next(iter(dev_matches)),
                confidence="definite" if len(pmgt_teams) == 1 else "likely_pmgt_dev_match",
                detail="Developer assignment team matches one PMGT team.",
            )
        contributor_matches = contributor_teams & pmgt_teams
        if len(contributor_matches) == 1:
            return _IssueTeamAttribution(
                team=next(iter(contributor_matches)),
                confidence="likely_pmgt_match",
                detail="Contributor assignment team matches one PMGT team.",
            )
        if len(pmgt_teams) == 1:
            return _IssueTeamAttribution(
                team=next(iter(pmgt_teams)),
                confidence="likely_pmgt_only",
                detail="Single PMGT team is available; contributor team was not decisive.",
            )

    dev_qa_teams = dev_teams | qa_teams
    if len(dev_qa_teams) == 1:
        return _IssueTeamAttribution(
            team=next(iter(dev_qa_teams)),
            confidence="definite",
            detail="DEV/QA worklog contributors are assigned to this team.",
        )
    if len(dev_teams) == 1:
        return _IssueTeamAttribution(
            team=next(iter(dev_teams)),
            confidence="dev_team_assumed",
            detail="DEV contributor assignment team is used because teams differ.",
        )
    if len(contributor_teams) == 1:
        return _IssueTeamAttribution(
            team=next(iter(contributor_teams)),
            confidence="definite",
            detail="All assigned worklog contributors are from this team.",
        )

    unknown_names = sorted(
        {item.display_name for item in contributors if item.team == "Unknown" and item.display_name}
    )
    if unknown_names:
        names = ", ".join(unknown_names[:5])
        if len(unknown_names) > 5:
            names = f"{names}, +{len(unknown_names) - 5} more"
        return _IssueTeamAttribution(
            team="Unknown",
            confidence="unknown",
            detail=f"No PMGT team and no team assignment for worklog contributor(s): {names}.",
        )
    return _IssueTeamAttribution(
        team="Unknown",
        confidence="unknown",
        detail="No PMGT team and no worklogs with assigned contributor teams.",
    )


def _active_passive_role_bucket(role_name: str | None) -> str:
    role = (role_name or "").strip().lower()
    if any(token in role for token in ("qa", "test", "quality")):
        return "qa"
    if any(token in role for token in ("dev", "developer", "development", "engineer", "architect")):
        return "dev"
    return "other"


def _team_parts(team: object) -> set[str]:
    normalized = _normalized_team_name(team)
    if normalized == "Unknown":
        return set()
    return {part.strip() for part in normalized.split(",") if part.strip()}


def _team_sort_key(team: str) -> tuple[int, str]:
    return (0 if team != "Unknown" else 1, team.lower())


def _is_excluded_throughput_team(team: object) -> bool:
    normalized = _normalized_team_name(team)
    return normalized.lower() in THROUGHPUT_REPORT_EXCLUDED_TEAMS


def workflow_thrashing(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    min_score: float = 0,
) -> AnalyticsReportResponse:
    summaries = thrash_by_issue(db, date_from=date_from, date_to=date_to)
    table = [
        {
            "issue_key": s.issue_key,
            "summary": s.summary,
            "status_changes": s.status_changes,
            "reopens": s.reopens,
            "ping_pong_count": s.ping_pong_count,
            "thrash_score": round(s.thrash_score, 1),
        }
        for s in summaries
        if s.thrash_score >= min_score
    ][:100]
    return AnalyticsReportResponse(filters={}, table=table)


def throughput_stability(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
) -> AnalyticsReportResponse:
    stmt = apply_issue_scope(
        select(
            JiraIssue.id,
            JiraIssue.resolved_at_jira,
            JiraUser.account_id,
            JiraUser.email_address,
            JiraUser.display_name,
        )
        .outerjoin(JiraUser, JiraUser.id == JiraIssue.assignee_user_id)
        .where(JiraIssue.resolved_at_jira.is_not(None))
    )
    if date_from:
        stmt = stmt.where(
            JiraIssue.resolved_at_jira
            >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
        )
    if date_to:
        stmt = stmt.where(
            JiraIssue.resolved_at_jira
            < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        )
    rows = db.execute(stmt).all()
    issue_ids = {int(row[0]) for row in rows}
    dev_team_by_issue = _dev_team_by_issue_from_worklogs(db, issue_ids)
    assignee_assignment_cache: dict[tuple[str, date], JiraUserRoleAssignment | None] = {}
    by_team_week: dict[tuple[str, str], int] = defaultdict(int)
    for issue_id, resolved_at, account_id, email, display_name in rows:
        if not resolved_at:
            continue
        resolved_on = resolved_at.date()
        team_name = dev_team_by_issue.get(int(issue_id))
        if team_name is None:
            source = str(account_id or email or "").strip()
            if source:
                cache_key = (source.lower(), resolved_on)
                if cache_key not in assignee_assignment_cache:
                    assignee_assignment_cache[cache_key] = get_assignment_for_allocated_source(
                        db,
                        source_user_email=source,
                        display_name=str(display_name or "").strip() or None,
                        as_of=resolved_on,
                    )
                assignment = assignee_assignment_cache[cache_key]
                team_name = (
                    _normalized_team_name(assignment.team_name)
                    if assignment and assignment.team_name
                    else None
                )
        team = team_name or "Unknown"
        week = resolved_at.isocalendar()
        by_team_week[(team, f"{week[0]}-W{week[1]:02d}")] += 1

    team_counts: dict[str, list[int]] = defaultdict(list)
    for (team, _week), count in by_team_week.items():
        team_counts[team].append(count)
    table = []
    for team, counts in team_counts.items():
        avg = sum(counts) / len(counts) if counts else 0
        variance = sum((c - avg) ** 2 for c in counts) / len(counts) if counts else 0
        std = variance**0.5
        predictability = max(0.0, min(1.0, 1 - (std / avg) if avg else 0))
        if _is_excluded_throughput_team(team):
            continue
        table.append(
            {
                "team": team,
                "avg_done_per_week": round(avg, 2),
                "stddev": round(std, 2),
                "predictability": round(predictability, 4),
            }
        )
    table.sort(key=lambda row: _team_sort_key(str(row["team"])))
    return AnalyticsReportResponse(filters={}, table=table)


def _dev_team_by_issue_from_worklogs(db: Session, issue_ids: set[int]) -> dict[int, str]:
    if not issue_ids:
        return {}
    assignments = (
        db.execute(select(JiraUserRoleAssignment).where(JiraUserRoleAssignment.active.is_(True)))
        .scalars()
        .all()
    )
    worklogs = db.execute(
        select(
            JiraWorklog.issue_id,
            JiraWorklog.author_account_id,
            JiraWorklog.author_email_address,
            JiraWorklog.started_at,
            JiraWorklog.time_spent_seconds,
        ).where(JiraWorklog.issue_id.in_(issue_ids))
    ).all()
    effort_by_issue_team: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for issue_id, account_id, email, started_at, seconds in worklogs:
        assignment = _assignment_for_worklog(
            assignments,
            account_id=str(account_id or "").strip() or None,
            email=str(email or "").strip() or None,
            started_at=started_at,
        )
        if assignment is None:
            continue
        if _active_passive_role_bucket(assignment.role_name) != "dev":
            continue
        team = _normalized_team_name(assignment.team_name)
        if team == "Unknown":
            continue
        effort_by_issue_team[int(issue_id)][team] += int(seconds or 0)

    resolved: dict[int, str] = {}
    for issue_id, team_seconds in effort_by_issue_team.items():
        if not team_seconds:
            continue
        resolved[issue_id] = max(team_seconds.items(), key=lambda item: (item[1], item[0]))[0]
    return resolved


def bus_factor(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    team: str | None = None,
) -> AnalyticsReportResponse:
    stmt = select(MonthlyTopicEffortBase).where(
        MonthlyTopicEffortBase.feature_root_id.is_not(None)
    )
    if date_from:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month <= date_to)
    stmt = scope_monthly_topic_effort(stmt)
    by_feature_person: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    names: dict[str, str] = {}
    contributor_teams: dict[tuple[str, str], str | None] = {}
    available_teams: set[str] = set()
    assignment_cache: dict[tuple[str | None, str | None, date], JiraUserRoleAssignment | None] = {}
    for row in db.execute(stmt).scalars().all():
        cache_key = (row.user_account_id, row.display_name, row.period_month)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=row.user_account_id or "",
                display_name=row.display_name,
                as_of=row.period_month,
            )
        assignment = assignment_cache[cache_key]
        contributor_team = _normalized_team_name(assignment.team_name if assignment else None)
        if contributor_team:
            available_teams.add(contributor_team)
        if team and not _team_matches(contributor_team, team):
            continue
        key = row.feature_key or "unknown"
        names[key] = row.feature_name or key
        person = (assignment.display_name if assignment else row.display_name) or "Unknown"
        by_feature_person[key][person] += float(row.direct_hours)
        contributor_teams[(key, person)] = contributor_team
    table = []
    for fk, people in by_feature_person.items():
        total = sum(people.values())
        if total <= 0:
            continue
        top_person = max(people.items(), key=lambda x: x[1])
        share = top_person[1] / total
        risk = (
            "low"
            if share < 0.4
            else "medium"
            if share < 0.65
            else "high"
            if share < 0.8
            else "extreme"
        )
        table.append(
            {
                "feature_key": fk,
                "feature_name": names[fk],
                "top_contributor": top_person[0],
                "top_contributor_team": contributor_teams.get((fk, top_person[0])),
                "share": round(share, 4),
                "contributors": len(people),
                "risk": risk,
            }
        )
    table.sort(key=lambda x: -x["share"])
    return AnalyticsReportResponse(filters={"available_teams": sorted(available_teams)}, table=table)


def _normalize_customer_names(raw: object) -> list[str]:
    if not raw:
        return []
    values = raw if isinstance(raw, list) else [raw]
    names: list[str] = []
    for item in values:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("value") or item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def _customer_effort_topic_bucket(topic_type: str | None) -> str:
    mapping = {
        "feature": "feature_hours",
        "unassigned_bug": "bugfix_hours",
        "tech_support": "support_hours",
        "issue_without_feature": "improvement_hours",
    }
    return mapping.get((topic_type or "").strip(), "other_hours")


def customer_effort(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    customer: str | None = None,
) -> AnalyticsReportResponse:
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    stmt = (
        select(
            MonthlyAllocatedEffort.period_month,
            MonthlyAllocatedEffort.topic_type,
            MonthlyAllocatedEffort.hours,
            MonthlyAllocatedEffort.issue_key,
            MonthlyAllocatedEffort.source_display_name,
            JiraIssue.summary,
            JiraIssueDetail.customers,
        )
        .join(JiraIssue, JiraIssue.id == MonthlyAllocatedEffort.issue_id)
        .join(JiraIssueDetail, JiraIssueDetail.issue_id == MonthlyAllocatedEffort.issue_id)
        .where(
            MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated")),
            JiraIssueDetail.customers.isnot(None),
        )
    )
    if period_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= period_from)
    if period_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= period_to)
    stmt = scope_monthly_allocated_effort(stmt)

    customer_filter = customer.strip() if customer else None
    by_customer: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_month_customer: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_year_customer: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_customer_issue: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    attributed_hours = 0.0

    for (
        period_month,
        topic_type,
        hours_raw,
        issue_key,
        source_display_name,
        issue_summary,
        customers_raw,
    ) in db.execute(stmt).all():
        customers = _normalize_customer_names(customers_raw)
        if not customers:
            continue
        if customer_filter and customer_filter not in customers:
            continue
        hours = float(hours_raw or 0)
        if hours <= 0:
            continue
        share = hours / len(customers)
        topic_bucket = _customer_effort_topic_bucket(topic_type)
        month = period_month.isoformat()
        year = str(period_month.year)
        attributed_hours += hours
        for name in customers:
            if customer_filter and name != customer_filter:
                continue
            by_customer[name]["total_hours"] += share
            by_customer[name][topic_bucket] += share
            by_month_customer[month][name] += share
            by_year_customer[year][name] += share
            _add_customer_effort_issue_drilldown(
                by_customer_issue,
                customer=name,
                issue_key=str(issue_key or "unknown"),
                issue_summary=str(issue_summary) if issue_summary else None,
                topic_type=topic_type,
                contributor=str(source_display_name or "Unknown"),
                hours=share,
            )

    table = []
    for name, values in by_customer.items():
        row = {"customer": name}
        for key in (
            "feature_hours",
            "bugfix_hours",
            "support_hours",
            "improvement_hours",
            "other_hours",
            "total_hours",
        ):
            row[key] = round(float(values.get(key, 0.0)), 2)
        table.append(row)
    table.sort(key=lambda row: (-row["total_hours"], row["customer"]))

    unattributed_hours = _customer_effort_unattributed_hours(
        db,
        period_from=period_from,
        period_to=period_to,
    )

    return AnalyticsReportResponse(
        filters={
            "period_from": period_from.isoformat() if period_from else None,
            "period_to": period_to.isoformat() if period_to else None,
            "attribution_method": "equal_split",
            "available_customers": sorted(by_customer.keys()),
            "yearly_series": _customer_period_series(by_year_customer, period_key="year"),
            "issue_drilldowns": _customer_effort_issue_drilldowns(by_customer_issue),
            "unattributed_hours": round(unattributed_hours, 2),
        },
        summary={
            "customer_count": len(table),
            "attributed_hours": round(attributed_hours, 2),
            "unattributed_hours": round(unattributed_hours, 2),
        },
        table=table,
        series=_customer_period_series(by_month_customer, period_key="period"),
    )


def _add_customer_effort_issue_drilldown(
    by_customer_issue: dict[str, dict[str, dict[str, object]]],
    *,
    customer: str,
    issue_key: str,
    issue_summary: str | None,
    topic_type: str | None,
    contributor: str,
    hours: float,
) -> None:
    customer_issues = by_customer_issue[customer]
    issue = customer_issues.setdefault(
        issue_key,
        {
            "issue_key": issue_key,
            "issue_summary": issue_summary,
            "topic_type": topic_type,
            "total_hours": 0.0,
            "_people": defaultdict(float),
        },
    )
    issue["total_hours"] = float(issue.get("total_hours") or 0.0) + hours
    people = issue.get("_people")
    if isinstance(people, defaultdict):
        people[contributor] += hours


def _customer_effort_issue_drilldowns(
    by_customer_issue: dict[str, dict[str, dict[str, object]]],
) -> dict[str, list[dict[str, object]]]:
    drilldowns: dict[str, list[dict[str, object]]] = {}
    for customer, issues in by_customer_issue.items():
        rows = []
        for issue in issues.values():
            people_raw = issue.get("_people")
            people = (
                [
                    {"person": person, "hours": round(float(hours), 2)}
                    for person, hours in people_raw.items()
                ]
                if isinstance(people_raw, defaultdict)
                else []
            )
            rows.append(
                {
                    "issue_key": issue.get("issue_key"),
                    "issue_summary": issue.get("issue_summary"),
                    "topic_type": issue.get("topic_type"),
                    "total_hours": round(float(issue.get("total_hours") or 0.0), 2),
                    "people": sorted(people, key=lambda row: (-float(row["hours"]), str(row["person"]))),
                }
            )
        drilldowns[customer] = sorted(
            rows,
            key=lambda row: (-float(row["total_hours"]), str(row["issue_key"])),
        )
    return drilldowns


def _customer_effort_unattributed_hours(
    db: Session,
    *,
    period_from: date | None,
    period_to: date | None,
) -> float:
    stmt = (
        select(MonthlyAllocatedEffort.hours, JiraIssueDetail.customers)
        .select_from(MonthlyAllocatedEffort)
        .outerjoin(JiraIssueDetail, JiraIssueDetail.issue_id == MonthlyAllocatedEffort.issue_id)
        .where(
            MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated")),
        )
    )
    if period_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= period_from)
    if period_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= period_to)
    stmt = scope_monthly_allocated_effort(stmt)
    total = 0.0
    for hours_raw, customers_raw in db.execute(stmt).all():
        if _normalize_customer_names(customers_raw):
            continue
        total += float(hours_raw or 0)
    return total


def _customer_period_series(
    grouped: dict[str, dict[str, float]],
    *,
    period_key: str,
) -> list[dict[str, str | float]]:
    return [
        {
            period_key: period,
            **{customer: round(hours, 2) for customer, hours in sorted(values.items())},
        }
        for period, values in sorted(grouped.items())
    ]


def investment_by_theme(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
) -> AnalyticsReportResponse:
    stmt = (
        select(MonthlyAllocatedEffort, JiraIssueDetail)
        .join(JiraFeatureRoot, JiraFeatureRoot.id == MonthlyAllocatedEffort.feature_root_id)
        .outerjoin(
            JiraIssueDetail,
            JiraIssueDetail.issue_id == JiraFeatureRoot.root_issue_id,
        )
        .where(MonthlyAllocatedEffort.topic_type == "feature")
    )
    if date_from:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month >= date_from)
    if date_to:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month <= date_to)
    stmt = scope_monthly_allocated_effort(stmt)
    by_theme: dict[str, float] = defaultdict(float)
    by_month_theme: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_year_theme: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for alloc, detail in db.execute(stmt).all():
        themes = _pmgt_theme_values(detail.pmgt_product if detail else None)
        hours = float(alloc.hours) / len(themes)
        month = alloc.period_month.isoformat()
        year = str(alloc.period_month.year)
        for theme in themes:
            by_theme[theme] += hours
            by_month_theme[month][theme] += hours
            by_year_theme[year][theme] += hours
    table = [
        {"theme": k, "hours": round(v, 2)}
        for k, v in sorted(by_theme.items(), key=lambda x: (-x[1], x[0]))
    ]
    return AnalyticsReportResponse(
        filters={
            "yearly_series": _theme_period_series(by_year_theme, period_key="year"),
        },
        table=table,
        series=_theme_period_series(by_month_theme, period_key="period"),
    )


def _pmgt_theme_values(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        values = option_values(raw_value)
    else:
        value = text_value(raw_value)
        values = [value] if value else []
    return values or ["Unknown"]


def _theme_period_series(
    grouped: dict[str, dict[str, float]],
    *,
    period_key: str,
) -> list[dict[str, str | float]]:
    return [
        {period_key: period, **{theme: round(hours, 2) for theme, hours in sorted(values.items())}}
        for period, values in sorted(grouped.items())
    ]


def feature_risk(db: Session) -> AnalyticsReportResponse:
    cost = feature_cost(db, date_from=None, date_to=None, team=None, feature_key=None)
    lc = {r["feature"]: r for r in (feature_lifecycle(db).table or [])}
    worklog_bounds = _feature_worklog_bounds(db)
    structure = _feature_structure_stats(db)
    table = []
    for row in cost.table or []:
        fk = row.get("feature_key")
        hours = row.get("total", 0)
        lifecycle = lc.get(fk, {})
        bounds = worklog_bounds.get(fk, {})
        structure_stats = structure.get(fk, _empty_feature_structure_stats())
        lifecycle_duration = lifecycle.get("total_duration_days")
        if lifecycle_duration is None:
            lifecycle_duration = lifecycle.get("elapsed_duration_days")
        duration = bounds.get("production_duration_days")
        duration_component = duration or 0
        size_risk_points = hours / 10
        duration_risk_points = duration_component / 5
        risk = min(100, size_risk_points + duration_risk_points)
        risk_drivers = _feature_risk_drivers(
            hours=hours,
            production_duration_days=duration,
            idle_before_work_days=bounds.get("idle_before_work_days"),
            structure_stats=structure_stats,
        )
        table.append(
            {
                "feature_key": fk,
                "feature_title": row.get("feature") or lifecycle.get("feature_name") or fk,
                "status": lifecycle.get("status") or "unknown",
                "hours": hours,
                "production_duration_days": duration,
                "lifecycle_duration_days": lifecycle_duration,
                "idle_before_work_days": bounds.get("idle_before_work_days"),
                "size_risk_points": round(size_risk_points, 2),
                "duration_risk_points": round(duration_risk_points, 2),
                "risk_drivers": risk_drivers,
                **structure_stats,
                "risk_score": round(risk, 2),
            }
        )
    table.sort(key=lambda x: -x["risk_score"])
    return AnalyticsReportResponse(filters={}, table=table)


def _feature_structure_stats(db: Session) -> dict[str, dict[str, int | float | str]]:
    member_issue = aliased(JiraIssue)
    member_project = aliased(JiraProject)
    rows = db.execute(
        apply_feature_root_scope(
            select(
                JiraFeatureRoot.root_key,
                JiraFeatureMembership.depth,
                member_issue.status_name,
                member_issue.status_category_key,
                member_issue.status_category_name,
            )
            .join(
                JiraFeatureMembership,
                JiraFeatureMembership.feature_root_id == JiraFeatureRoot.id,
            )
            .join(member_issue, member_issue.id == JiraFeatureMembership.member_issue_id)
            .outerjoin(member_project, member_project.id == member_issue.project_id)
            .where(
                or_(
                    member_issue.project_id.is_(None),
                    member_project.key.notin_(tuple(EXCLUDED_PROJECT_KEYS)),
                )
            )
        )
    ).all()

    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "member_issue_count": 0,
            "child_issue_count": 0,
            "done_member_issue_count": 0,
            "open_member_issue_count": 0,
            "blocked_member_issue_count": 0,
            "max_hierarchy_depth": 0,
        }
    )
    for feature_key, depth, status, category_key, category_name in rows:
        stats = grouped[feature_key]
        normalized_depth = int(depth or 0)
        is_done = _is_done_status(status, category_key, category_name)
        is_blocked = "block" in (status or "").strip().lower()
        stats["member_issue_count"] += 1
        if normalized_depth > 0:
            stats["child_issue_count"] += 1
        if is_done:
            stats["done_member_issue_count"] += 1
        else:
            stats["open_member_issue_count"] += 1
        if is_blocked:
            stats["blocked_member_issue_count"] += 1
        stats["max_hierarchy_depth"] = max(stats["max_hierarchy_depth"], normalized_depth)

    return {
        feature_key: {
            **stats,
            "done_member_ratio": round(
                stats["done_member_issue_count"] / stats["member_issue_count"],
                2,
            )
            if stats["member_issue_count"]
            else 0,
            "structure_signal": _feature_structure_signal(stats),
        }
        for feature_key, stats in grouped.items()
    }


def _empty_feature_structure_stats() -> dict[str, int | float | str]:
    return {
        "member_issue_count": 0,
        "child_issue_count": 0,
        "done_member_issue_count": 0,
        "open_member_issue_count": 0,
        "blocked_member_issue_count": 0,
        "max_hierarchy_depth": 0,
        "done_member_ratio": 0,
        "structure_signal": "unknown_structure",
    }


def _feature_structure_signal(stats: dict[str, int]) -> str:
    child_count = stats["child_issue_count"]
    member_count = stats["member_issue_count"]
    done_ratio = stats["done_member_issue_count"] / member_count if member_count else 0
    open_count = stats["open_member_issue_count"]
    blocked_count = stats["blocked_member_issue_count"]
    max_depth = stats["max_hierarchy_depth"]

    if blocked_count > 0:
        return "blocked_structure"
    if child_count == 0:
        return "under_defined"
    if child_count >= 8 and done_ratio < 0.5:
        return "broad_scope"
    if max_depth >= 2 and open_count >= 6:
        return "integration_risk"
    if child_count >= 3 and done_ratio >= 0.7:
        return "well_decomposed"
    return "some_decomposition"


def _feature_risk_drivers(
    *,
    hours: float,
    production_duration_days: int | None,
    idle_before_work_days: int | None,
    structure_stats: dict[str, int | float | str],
) -> list[str]:
    drivers = []
    if hours >= 200:
        drivers.append("large_scope")
    elif hours >= 80:
        drivers.append("medium_scope")
    if production_duration_days is None:
        drivers.append("missing_production_duration")
    elif production_duration_days >= 45:
        drivers.append("long_running")
    elif production_duration_days >= 20:
        drivers.append("extended_duration")
    if idle_before_work_days is not None and idle_before_work_days >= 30:
        drivers.append("idle_before_start")

    signal = str(structure_stats.get("structure_signal") or "")
    if signal in {"under_defined", "broad_scope", "integration_risk", "blocked_structure"}:
        drivers.append(signal)
    elif signal == "well_decomposed":
        drivers.append("well_decomposed")

    return drivers


def _is_done_status(
    status: str | None,
    category_key: str | None = None,
    category_name: str | None = None,
) -> bool:
    normalized_status = (status or "").strip().lower()
    normalized_category = (category_key or category_name or "").strip().lower()
    return normalized_category == "done" or normalized_status in {
        "done",
        "closed",
        "resolved",
        "released",
        "shipped",
    }


def engineering_health(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    team: str | None = None,
) -> AnalyticsReportResponse:
    period_from, period_to = _engineering_health_period(date_from, date_to)
    months = _month_sequence(period_from, period_to)
    team_filter = _normalized_team_name(team) if team else None
    component_warnings: list[str] = []

    focus_by_key, focus_raw = _engineering_health_try_component(
        "focus_health",
        component_warnings,
        lambda: _health_focus_components(
            db,
            date_from=period_from,
            date_to=period_to,
            team=team_filter,
        ),
        default=({}, {}),
    )
    interruption_by_key, interruption_raw = _engineering_health_try_component(
        "interruption_health",
        component_warnings,
        lambda: _health_interruption_components(
            db,
            date_from=period_from,
            date_to=period_to,
            team=team_filter,
            focus_raw=focus_raw,
        ),
        default=({}, {}),
    )
    flow_by_key, flow_raw = _engineering_health_try_component(
        "flow_efficiency",
        component_warnings,
        lambda: _health_flow_components(
            db,
            date_from=period_from,
            date_to=period_to,
            team=team_filter,
            component_warnings=component_warnings,
        ),
        default=({}, {}),
    )
    predictability_by_key, predictability_raw = _engineering_health_try_component(
        "execution_predictability",
        component_warnings,
        lambda: _health_predictability_components(
            db,
            date_from=period_from,
            date_to=period_to,
        ),
        default=({}, {}),
    )
    work_shape_by_key, work_shape_raw = _engineering_health_try_component(
        "work_shape_health",
        component_warnings,
        lambda: _health_work_shape_components(
            db,
            date_from=period_from,
            date_to=period_to,
            team=team_filter,
        ),
        default=({}, {}),
    )
    workforce_raw = _engineering_health_try_component(
        "workforce_context",
        component_warnings,
        lambda: _health_workforce_context(
            db,
            date_from=period_from,
            date_to=period_to,
            team=team_filter,
        ),
        default={},
    )

    available_teams = _engineering_health_available_teams(
        db,
        period_from=period_from,
        period_to=period_to,
        component_keys=set(focus_by_key)
        | set(interruption_by_key)
        | set(work_shape_by_key)
        | set(workforce_raw),
        range_teams={team for team, _month in set(flow_by_key) | set(predictability_by_key)},
    )
    focused_teams = _engineering_health_selected_teams(available_teams, team_filter)

    table: list[dict[str, object]] = []
    series_by_month: dict[str, dict[str, object]] = {month: {"period": month} for month in months}
    drag_counts: dict[str, int] = defaultdict(int)
    scored_values: list[float] = []

    for month in months:
        for team_name in focused_teams:
            key = (team_name, month)
            components = {
                "flow_efficiency": flow_by_key.get(key),
                "focus_health": focus_by_key.get(key),
                "interruption_health": interruption_by_key.get(key),
                "execution_predictability": predictability_by_key.get(key),
                "work_shape_health": work_shape_by_key.get(key),
            }
            score, confidence = _weighted_health_score(components)
            drags = _health_drags(components)
            if drags:
                drag_counts[drags[0]] += 1
            if score is not None:
                scored_values.append(score)
            series_by_month[month][team_name] = score
            table.append(
                {
                    "team": team_name,
                    "month": month,
                    "health_index": score,
                    "confidence": confidence,
                    "biggest_drag": drags[0] if drags else None,
                    "second_drag": drags[1] if len(drags) > 1 else None,
                    **{name: value for name, value in components.items()},
                    **focus_raw.get(key, {}),
                    **interruption_raw.get(key, {}),
                    **flow_raw.get(key, {}),
                    **predictability_raw.get(key, {}),
                    **work_shape_raw.get(key, {}),
                    **workforce_raw.get(key, _empty_workforce_context()),
                }
            )

    table.sort(key=lambda row: (str(row["month"]), _team_sort_key(str(row["team"]))), reverse=True)
    worst_drag = max(drag_counts.items(), key=lambda item: item[1])[0] if drag_counts else None
    return AnalyticsReportResponse(
        filters={
            "from": period_from.isoformat(),
            "to": period_to.isoformat(),
            "team": team_filter,
            "available_teams": available_teams,
            "focused_teams": focused_teams,
            "weights": ENGINEERING_HEALTH_WEIGHTS,
            "component_labels": ENGINEERING_HEALTH_COMPONENT_LABELS,
            "window_months": len(months),
            "component_warnings": component_warnings,
            "methodology_notes": [
                "Scores are 0-100 and combine normalized component signals; raw metrics are returned beside the score.",
                "Missing component data lowers confidence. A score is withheld when less than half of the configured weight is available.",
                "Flow efficiency and throughput predictability are calculated per calendar month for the selected window.",
                "FreeDevs is included only when team assignment or component data exists for the selected window.",
                "Workforce Strength is capacity context from HRWorks planned hours and is not weighted into the health score.",
            ],
        },
        summary={
            "average_health_index": round(sum(scored_values) / len(scored_values), 2)
            if scored_values
            else None,
            "worst_drag": worst_drag,
            "scored_team_months": len(scored_values),
            "total_team_months": len(table),
            "data_coverage": round(len(scored_values) / len(table), 4) if table else 0,
        },
        series=list(series_by_month.values()),
        table=table,
    )


_EngineeringHealthComponent = TypeVar("_EngineeringHealthComponent")


def _engineering_health_try_component(
    name: str,
    warnings: list[str],
    loader: Callable[[], _EngineeringHealthComponent],
    *,
    default: _EngineeringHealthComponent,
) -> _EngineeringHealthComponent:
    try:
        return loader()
    except Exception as exc:
        logger.exception("engineering_health component %s failed", name)
        warnings.append(f"{name}: {type(exc).__name__}")
        return default


def _engineering_health_period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    to_date = date_to or today
    to_month = date(to_date.year, to_date.month, 1)
    if date_from:
        return date(date_from.year, date_from.month, 1), to_date
    month = to_month.month - 5
    year = to_month.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1), to_date


def _capacity_forecast_period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    current_month = date(today.year, today.month, 1)
    default_from = _add_months(current_month, -1)
    default_to = _add_months(current_month, 5)
    from_month = date(date_from.year, date_from.month, 1) if date_from else default_from
    to_month = date(date_to.year, date_to.month, 1) if date_to else default_to
    return from_month, to_month


def _month_start_dates(period_from: date, period_to: date) -> list[date]:
    months: list[date] = []
    current = date(period_from.year, period_from.month, 1)
    end = date(period_to.year, period_to.month, 1)
    while current <= end:
        months.append(current)
        current = _add_months(current, 1)
    return months


def _add_months(month_start: date, offset: int) -> date:
    month_index = (month_start.year * 12) + (month_start.month - 1) + offset
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _month_end(month_start: date) -> date:
    return _add_months(month_start, 1) - timedelta(days=1)


def _assignment_valid_for_month(assignment: JiraUserRoleAssignment, month_start: date) -> bool:
    if not assignment.active:
        return False
    as_of = _month_end(month_start)
    if assignment.valid_from > as_of:
        return False
    return assignment.valid_to is None or assignment.valid_to >= as_of


def _month_sequence(period_from: date, period_to: date) -> list[str]:
    months: list[str] = []
    current = date(period_from.year, period_from.month, 1)
    end = date(period_to.year, period_to.month, 1)
    while current <= end:
        months.append(current.isoformat())
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        current = date(year, month, 1)
    return months


def _engineering_health_selected_teams(
    available_teams: list[str],
    team_filter: str | None,
) -> list[str]:
    if team_filter:
        return [team_filter]
    available_set = set(available_teams)
    teams = list(ENGINEERING_HEALTH_FOCUSED_TEAMS)
    for optional_team in ENGINEERING_HEALTH_OPTIONAL_TEAMS:
        if optional_team in available_set:
            teams.append(optional_team)
    return teams


def _engineering_health_available_teams(
    db: Session,
    *,
    period_from: date,
    period_to: date,
    component_keys: set[tuple[str, str]],
    range_teams: set[str],
) -> list[str]:
    teams = set(
        _available_assignment_teams(
            db,
            date_from=period_from,
            date_to=period_to,
            project_keys=None,
            role_names=HEATMAP_ROLES,
        )
    )
    teams.update(team for team, _month in component_keys)
    teams.update(range_teams)
    return sorted({_normalized_team_name(team) for team in teams if team}, key=_team_sort_key)


def _health_workforce_context(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    team: str | None,
) -> dict[tuple[str, str], dict[str, object]]:
    period_from, period_to = _monthly_period_bounds(date_from, date_to)
    team_filter = _normalized_team_name(team) if team else None
    by_key: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    assignment_cache: dict[tuple[str, str | None, date], JiraUserRoleAssignment | None] = {}

    def assignment_for(
        *,
        source_user_email: str,
        display_name: str | None,
        as_of: date,
    ) -> JiraUserRoleAssignment | None:
        cache_key = (source_user_email, display_name, as_of)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=source_user_email,
                display_name=display_name,
                as_of=as_of,
            )
        return assignment_cache[cache_key]

    hrworks_stmt = select(JiraUserMonthlyHrworksHours, JiraUser).join(
        JiraUser,
        JiraUser.id == JiraUserMonthlyHrworksHours.jira_user_id,
    )
    if period_from:
        hrworks_stmt = hrworks_stmt.where(JiraUserMonthlyHrworksHours.month_start >= period_from)
    if period_to:
        hrworks_stmt = hrworks_stmt.where(JiraUserMonthlyHrworksHours.month_start <= period_to)

    for hours_row, user in db.execute(hrworks_stmt).all():
        source_key = user.account_id or user.email_address or user.display_name
        assignment = assignment_for(
            source_user_email=source_key,
            display_name=user.display_name,
            as_of=hours_row.month_start,
        )
        if not assignment or assignment.role_name not in HEATMAP_ROLES:
            continue
        team_name = _normalized_team_name(assignment.team_name)
        if team_filter and team_name != team_filter:
            continue
        month = hours_row.month_start.isoformat()
        key = (team_name, month)
        available = float(hours_row.planned_working_hours)
        if assignment.role_name == "Developer":
            by_key[key]["dev_workforce_strength_hours"] += available
        elif assignment.role_name == "QA":
            by_key[key]["qa_workforce_strength_hours"] += available

    topic_stmt = select(MonthlyTopicEffortBase).where(
        MonthlyTopicEffortBase.role_name.in_(HEATMAP_ROLES)
    )
    if period_from:
        topic_stmt = topic_stmt.where(MonthlyTopicEffortBase.period_month >= period_from)
    if period_to:
        topic_stmt = topic_stmt.where(MonthlyTopicEffortBase.period_month <= period_to)
    topic_stmt = scope_monthly_topic_effort(topic_stmt)

    for row in db.execute(topic_stmt).scalars().all():
        source_key = row.user_account_id or row.display_name or "unknown"
        assignment = assignment_for(
            source_user_email=source_key,
            display_name=row.display_name,
            as_of=row.period_month,
        )
        if not assignment or assignment.role_name not in HEATMAP_ROLES:
            continue
        team_name = _normalized_team_name(assignment.team_name)
        if team_filter and team_name != team_filter:
            continue
        month = row.period_month.isoformat()
        key = (team_name, month)
        logged = float(row.direct_hours)
        if assignment.role_name == "Developer":
            by_key[key]["dev_booked_hours"] += logged
        elif assignment.role_name == "QA":
            by_key[key]["qa_booked_hours"] += logged

    result: dict[tuple[str, str], dict[str, object]] = {}
    for key, values in by_key.items():
        dev_available = values.get("dev_workforce_strength_hours", 0.0)
        qa_available = values.get("qa_workforce_strength_hours", 0.0)
        dev_booked = values.get("dev_booked_hours", 0.0)
        qa_booked = values.get("qa_booked_hours", 0.0)
        total_available = dev_available + qa_available
        total_booked = dev_booked + qa_booked
        result[key] = {
            "dev_workforce_strength_hours": round(dev_available, 2),
            "qa_workforce_strength_hours": round(qa_available, 2),
            "workforce_strength_hours": round(total_available, 2),
            "dev_booked_hours": round(dev_booked, 2),
            "qa_booked_hours": round(qa_booked, 2),
            "booked_hours": round(total_booked, 2),
            "dev_utilization_ratio": _ratio_or_none(dev_booked, dev_available),
            "qa_utilization_ratio": _ratio_or_none(qa_booked, qa_available),
            "utilization_ratio": _ratio_or_none(total_booked, total_available),
        }
    return result


def _empty_workforce_context() -> dict[str, object]:
    return {
        "dev_workforce_strength_hours": 0.0,
        "qa_workforce_strength_hours": 0.0,
        "workforce_strength_hours": 0.0,
        "dev_booked_hours": 0.0,
        "qa_booked_hours": 0.0,
        "booked_hours": 0.0,
        "dev_utilization_ratio": None,
        "qa_utilization_ratio": None,
        "utilization_ratio": None,
    }


def _ratio_or_none(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _health_focus_components(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    team: str | None,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], dict[str, object]]]:
    report = planned_vs_unplanned(db, date_from=date_from, date_to=date_to, team=team)
    scores: dict[tuple[str, str], float] = {}
    raw: dict[tuple[str, str], dict[str, object]] = {}
    for row in report.table or []:
        team_name = _normalized_team_name(row.get("team"))
        month = str(row.get("month") or "")
        if not month:
            continue
        focus = _float_or_none(row.get("roadmap_focus"))
        key = (team_name, month)
        if focus is not None:
            # Soft penalty: operational work matters, but planned support load should not zero a team.
            scores[key] = round(50 + 50 * _clamp(focus, 0, 1), 2)
        raw[key] = {
            "roadmap_hours": _float_or_none(row.get("roadmap_hours")),
            "continuous_improvement_hours": _float_or_none(
                row.get("continuous_improvement_hours")
            ),
            "roadmap_focus": focus,
        }
    return scores, raw


def _health_interruption_components(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    team: str | None,
    focus_raw: dict[tuple[str, str], dict[str, object]],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], dict[str, object]]]:
    scores: dict[tuple[str, str], float] = {}
    raw: dict[tuple[str, str], dict[str, object]] = {}
    # Full interruption analysis scans active-start events for all issues; only run when
    # a single real-interruption team is selected. The aggregate view uses roadmap focus.
    if team and team in REAL_INTERRUPTION_TEAMS:
        report = real_interruption_ratio(db, date_from=date_from, date_to=date_to, team=team)
    else:
        report = AnalyticsReportResponse(table=[])
    for row in report.table or []:
        team_name = _normalized_team_name(row.get("team"))
        if team and team_name != team:
            continue
        month = str(row.get("month") or "")
        if not month:
            continue
        time_ratio = _float_or_none(row.get("time_interruption_ratio"))
        issue_ratio = _float_or_none(row.get("interruption_ratio"))
        ratio = time_ratio if time_ratio is not None else issue_ratio
        key = (team_name, month)
        if ratio is not None:
            scores[key] = round((1 - _clamp(ratio, 0, 1)) * 100, 2)
        raw[key] = {
            "interruption_ratio": issue_ratio,
            "time_interruption_ratio": time_ratio,
            "interrupting_hours": _float_or_none(row.get("interrupting_hours")),
            "interruption_source": "real_interruption",
        }

    for key, values in focus_raw.items():
        if key in scores:
            continue
        focus = _float_or_none(values.get("roadmap_focus"))
        if focus is None:
            continue
        scores[key] = round(_clamp(focus, 0, 1) * 100, 2)
        raw[key] = {
            "interruption_ratio": round(1 - _clamp(focus, 0, 1), 4),
            "time_interruption_ratio": None,
            "interrupting_hours": values.get("continuous_improvement_hours"),
            "interruption_source": "roadmap_focus_fallback",
        }
    return scores, raw


def _health_flow_components(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    team: str | None,
    component_warnings: list[str] | None = None,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], dict[str, object]]]:
    scores: dict[tuple[str, str], float] = {}
    raw: dict[tuple[str, str], dict[str, object]] = {}
    allowed_workflow_ids = scoped_workflow_ids(db)
    if not allowed_workflow_ids:
        return scores, raw

    available_projects = available_status_waiting_projects(db)
    project_keys = [project["key"] for project in available_projects if project.get("key")]
    cohort_issue_ids = _active_passive_issue_ids_by_created_date(
        db,
        project_keys=project_keys or None,
        date_from=date_from,
        date_to=date_to,
    )
    if not cohort_issue_ids:
        return scores, raw
    if len(cohort_issue_ids) > ENGINEERING_HEALTH_MAX_FLOW_COHORT_ISSUES:
        message = (
            "flow_efficiency: skipped because issue cohort is too large "
            f"({len(cohort_issue_ids)} > {ENGINEERING_HEALTH_MAX_FLOW_COHORT_ISSUES})"
        )
        logger.warning("engineering_health %s", message)
        if component_warnings is not None:
            component_warnings.append(message)
        return scores, raw

    issue_month = _issue_created_month_by_id(db, cohort_issue_ids)
    intervals = build_status_intervals(db, issue_ids=cohort_issue_ids)
    issue_ids = {interval.issue_id for interval in intervals}
    workflow_by_issue = resolve_workflow_ids_for_issues(db, issue_ids)
    main_workflow_ids = {
        workflow_id
        for workflow_id in workflow_by_issue.values()
        if workflow_id in allowed_workflow_ids
    }
    relevant_issue_ids = {
        interval.issue_id
        for interval in intervals
        if workflow_by_issue.get(interval.issue_id) in main_workflow_ids
    }
    workflows = load_workflows_by_id(db, main_workflow_ids)
    workflow_by_spec = _main_workflows_by_spec(workflows)
    attribution_by_issue = _active_passive_issue_attributions(db, relevant_issue_ids)
    totals: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for spec in MAIN_WORKFLOW_SPECS:
        workflow_row = workflow_by_spec.get(spec.catalog_key)
        if workflow_row is None:
            continue
        for iv in intervals:
            if iv.issue_id not in relevant_issue_ids:
                continue
            if workflow_by_issue.get(iv.issue_id) != workflow_row.id:
                continue
            if not issue_type_eligible_for_main_spec(iv.issue_type_name, spec):
                continue
            seconds = iv.duration_seconds
            if seconds <= 0:
                continue
            attribution = attribution_by_issue.get(
                iv.issue_id,
                _IssueTeamAttribution(
                    team="Unknown",
                    confidence="unknown",
                    detail="No PMGT team and no assigned worklog contributor team.",
                ),
            )
            if team and not _team_matches(attribution.team, team):
                continue
            cls = _active_passive_status_bucket(iv.status_name, spec)
            if cls is None:
                continue
            month = issue_month.get(iv.issue_id)
            if not month:
                continue
            hours = seconds / 3600.0
            totals[(_normalized_team_name(attribution.team), month)][cls] += hours

    for (team_name, month), values in totals.items():
        active = values.get("Active Work", 0.0)
        queue = sum(value for bucket, value in values.items() if bucket != "Active Work")
        total = active + queue
        if total <= 0:
            continue
        ratio = active / total
        key = (team_name, month)
        scores[key] = round(ratio * 100, 2)
        raw[key] = {
            "active_work_hours": round(active, 2),
            "queue_hours": round(queue, 2),
            "flow_efficiency_ratio": round(ratio, 4),
        }
    return scores, raw


def _health_predictability_components(
    db: Session,
    *,
    date_from: date,
    date_to: date,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], dict[str, object]]]:
    scores: dict[tuple[str, str], float] = {}
    raw: dict[tuple[str, str], dict[str, object]] = {}
    stmt = apply_issue_scope(
        select(
            JiraIssue.id,
            JiraIssue.resolved_at_jira,
            JiraUser.account_id,
            JiraUser.email_address,
            JiraUser.display_name,
        )
        .outerjoin(JiraUser, JiraUser.id == JiraIssue.assignee_user_id)
        .where(JiraIssue.resolved_at_jira.is_not(None))
    )
    stmt = stmt.where(
        JiraIssue.resolved_at_jira
        >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
    )
    stmt = stmt.where(
        JiraIssue.resolved_at_jira
        < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    )
    rows = db.execute(stmt).all()
    issue_ids = {int(row[0]) for row in rows}
    dev_team_by_issue = _dev_team_by_issue_from_worklogs(db, issue_ids)
    assignee_assignment_cache: dict[tuple[str, date], JiraUserRoleAssignment | None] = {}
    by_team_month_week: dict[tuple[str, str, str], int] = defaultdict(int)

    for issue_id, resolved_at, account_id, email, display_name in rows:
        if not resolved_at:
            continue
        resolved_on = resolved_at.date()
        team_name = dev_team_by_issue.get(int(issue_id))
        if team_name is None:
            source = str(account_id or email or "").strip()
            if source:
                cache_key = (source.lower(), resolved_on)
                if cache_key not in assignee_assignment_cache:
                    assignee_assignment_cache[cache_key] = get_assignment_for_allocated_source(
                        db,
                        source_user_email=source,
                        display_name=str(display_name or "").strip() or None,
                        as_of=resolved_on,
                    )
                assignment = assignee_assignment_cache[cache_key]
                team_name = (
                    _normalized_team_name(assignment.team_name)
                    if assignment and assignment.team_name
                    else None
                )
        team = team_name or "Unknown"
        if _is_excluded_throughput_team(team):
            continue
        month = date(resolved_on.year, resolved_on.month, 1).isoformat()
        week = resolved_at.isocalendar()
        by_team_month_week[(team, month, f"{week[0]}-W{week[1]:02d}")] += 1

    month_counts: dict[tuple[str, str], list[int]] = defaultdict(list)
    for (team, month, _week), count in by_team_month_week.items():
        month_counts[(team, month)].append(count)

    for (team, month), counts in month_counts.items():
        avg = sum(counts) / len(counts) if counts else 0
        variance = sum((c - avg) ** 2 for c in counts) / len(counts) if counts else 0
        std = variance**0.5
        predictability = max(0.0, min(1.0, 1 - (std / avg) if avg else 0))
        team_name = _normalized_team_name(team)
        key = (team_name, month)
        scores[key] = round(_clamp(predictability, 0, 1) * 100, 2)
        raw[key] = {
            "avg_done_per_week": round(avg, 2),
            "throughput_stddev": round(std, 2),
            "throughput_predictability": round(predictability, 4),
        }
    return scores, raw


def _month_date_ranges(date_from: date, date_to: date) -> list[tuple[date, date]]:
    ranges: list[tuple[date, date]] = []
    current = date(date_from.year, date_from.month, 1)
    end_month = date(date_to.year, date_to.month, 1)
    while current <= end_month:
        next_year = current.year + (1 if current.month == 12 else 0)
        next_month = 1 if current.month == 12 else current.month + 1
        next_start = date(next_year, next_month, 1)
        month_end = min(date_to, next_start - timedelta(days=1))
        ranges.append((current, month_end))
        current = next_start
    return ranges


def _health_work_shape_components(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    team: str | None,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], dict[str, object]]]:
    stmt = _allocated_effort_filter_base(date_from, date_to).where(
        MonthlyAllocatedEffort.topic_type == "feature",
        MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated")),
    )
    assignment_cache: dict[tuple[str, date], JiraUserRoleAssignment | None] = {}
    feature_hours_total: dict[str, float] = defaultdict(float)
    risk_weighted: dict[tuple[str, str], float] = defaultdict(float)
    hours_by_key: dict[tuple[str, str], float] = defaultdict(float)
    risk_adjusted_hours_by_key: dict[tuple[str, str], float] = defaultdict(float)
    feature_count: dict[tuple[str, str], set[str]] = defaultdict(set)
    allocated_rows = db.execute(stmt).scalars().all()
    for row in allocated_rows:
        if row.source_role_name not in HEATMAP_ROLES:
            continue
        feature_key = str(row.feature_key or "").strip()
        if not feature_key:
            continue
        hours = float(row.hours or 0)
        if hours <= 0:
            continue
        feature_hours_total[feature_key] += hours
    risk_by_feature = {
        feature_key: min(100.0, total_hours / 10.0)
        for feature_key, total_hours in feature_hours_total.items()
    }
    for row in allocated_rows:
        if row.source_role_name not in HEATMAP_ROLES:
            continue
        cache_key = (row.source_user_email, row.period_month)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = get_assignment_for_allocated_source(
                db,
                source_user_email=row.source_user_email,
                display_name=row.source_display_name,
                as_of=row.period_month,
            )
        assignment = assignment_cache[cache_key]
        team_name = _normalized_team_name(assignment.team_name if assignment else None)
        if team and team_name != team:
            continue
        month = row.period_month.isoformat()
        key = (team_name, month)
        hours = float(row.hours or 0)
        if hours <= 0:
            continue
        feature_key = str(row.feature_key or "").strip()
        if not feature_key:
            continue
        risk = risk_by_feature.get(feature_key)
        if risk is None:
            continue
        risk_weighted[key] += risk * hours
        hours_by_key[key] += hours
        risk_adjusted_hours_by_key[key] += hours * (risk / 100)
        if row.feature_key:
            feature_count[key].add(row.feature_key)

    scores: dict[tuple[str, str], float] = {}
    raw: dict[tuple[str, str], dict[str, object]] = {}
    for key, hours in hours_by_key.items():
        if hours <= 0:
            continue
        avg_risk = risk_weighted[key] / hours
        scores[key] = round(100 - _clamp(avg_risk, 0, 100), 2)
        raw[key] = {
            "feature_hours": round(hours, 2),
            "risk_adjusted_feature_hours": round(risk_adjusted_hours_by_key[key], 2),
            "avg_feature_risk": round(avg_risk, 2),
            "feature_count": len(feature_count[key]),
        }
    return scores, raw


def _weighted_health_score(components: dict[str, float | None]) -> tuple[float | None, float]:
    available_weight = 0.0
    weighted = 0.0
    for name, weight in ENGINEERING_HEALTH_WEIGHTS.items():
        value = components.get(name)
        if value is None:
            continue
        available_weight += weight
        weighted += _clamp(float(value), 0, 100) * weight
    confidence = round(available_weight / sum(ENGINEERING_HEALTH_WEIGHTS.values()), 4)
    if available_weight < 0.5:
        return None, confidence
    return round(weighted / available_weight, 2), confidence


def _health_drags(components: dict[str, float | None]) -> list[str]:
    available = [
        (name, float(value))
        for name, value in components.items()
        if isinstance(value, (int, float))
    ]
    return [name for name, _value in sorted(available, key=lambda item: item[1])[:2]]


def _float_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def roadmap_reliability(db: Session) -> AnalyticsReportResponse:
    pva = promised_vs_actual(db)
    table = [
        row
        for row in (pva.table or [])
        if not _is_roadmap_reliability_hidden_status(row.get("status"))
    ]
    current_year = date.today().year
    on_time = delayed = open_late = 0
    yearly_team: dict[tuple[str, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in table:
        delay = row.get("delay_days")
        promised_year = _year_from_value(row.get("promised"))
        if delay is None:
            if promised_year == current_year:
                open_late += 1
            for yearly_key in _yearly_average_keys(row.get("team"), promised_year):
                yearly_team[yearly_key]["still_open"] += 1
        elif delay <= 0:
            if promised_year == current_year:
                on_time += 1
            for yearly_key in _yearly_average_keys(row.get("team"), promised_year):
                yearly_team[yearly_key]["on_time"] += 1
                yearly_team[yearly_key]["delay_days_total"] += float(delay)
                yearly_team[yearly_key]["delay_days_count"] += 1
        else:
            if promised_year == current_year:
                delayed += 1
            for yearly_key in _yearly_average_keys(row.get("team"), promised_year):
                yearly_team[yearly_key]["delayed"] += 1
                yearly_team[yearly_key]["delay_days_total"] += float(delay)
                yearly_team[yearly_key]["delay_days_count"] += 1
    total = on_time + delayed + open_late
    reliability = on_time / total if total else 0
    return AnalyticsReportResponse(
        filters={
            "yearly_team_averages": _roadmap_yearly_team_rows(yearly_team),
            "summary_year": current_year,
        },
        summary={
            "on_time": on_time,
            "delayed": delayed,
            "still_open": open_late,
            "reliability": round(reliability, 4),
        },
        table=table,
    )


def _is_roadmap_reliability_hidden_status(status: object) -> bool:
    return str(status or "").strip().lower() in ROADMAP_RELIABILITY_HIDDEN_STATUSES


def release_quality(db: Session) -> AnalyticsReportResponse:
    releases = (
        db.execute(select(Release).order_by(Release.committed_at.desc()).limit(50))
        .scalars()
        .all()
    )
    table = [
        {
            "release": r.tag_name or str(r.id),
            "released_at": r.committed_at.isoformat() if r.committed_at else None,
        }
        for r in releases
    ]
    return AnalyticsReportResponse(filters={}, table=table)


def size_vs_speed(db: Session) -> AnalyticsReportResponse:
    cost = feature_cost(db, date_from=None, date_to=None, team=None, feature_key=None)
    lc = {r["feature"]: r for r in (feature_lifecycle(db).table or [])}
    worklog_bounds = _feature_worklog_bounds(db)
    table = []
    for row in cost.table or []:
        fk = row.get("feature_key")
        lifecycle = lc.get(fk, {})
        bounds = worklog_bounds.get(fk, {})
        hours = float(row.get("total") or 0)
        lifecycle_duration = lifecycle.get("total_duration_days")
        production_duration = bounds.get("production_duration_days")
        table.append(
            {
                "feature_key": fk,
                "feature_name": row.get("feature") or lifecycle.get("feature_name") or fk,
                "hours": hours,
                "production_duration_days": production_duration,
                "hours_per_production_day": _hours_per_day(hours, production_duration),
                "lifecycle_days": lifecycle_duration,
                "hours_per_lifecycle_day": _hours_per_day(hours, lifecycle_duration),
                # Backward compatible alias for existing consumers.
                "duration_days": lifecycle_duration,
            }
        )
    return AnalyticsReportResponse(filters={}, table=table)


def _team_matches(row_team: object, team_filter: str) -> bool:
    normalized_row = _normalized_team_name(row_team)
    normalized_filter = _normalized_team_name(team_filter)
    row_parts = {part.strip() for part in normalized_row.split(",") if part.strip()}
    return normalized_row == normalized_filter or normalized_filter in row_parts


def _yearly_average_teams(team: object) -> list[str]:
    normalized = _normalized_team_name(team)
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    return [part for part in parts if part in FLOW_YEARLY_AVERAGE_TEAM_ORDER]


def _yearly_average_keys(team: object, year: object) -> list[tuple[str, int]]:
    normalized_year = _year_from_value(year)
    if normalized_year not in FLOW_REPORT_YEARS:
        return []
    return [(team_name, normalized_year) for team_name in _yearly_average_teams(team)]


def _add_yearly_average_sample(
    groups: dict[tuple[str, int], dict[str, list[float]]],
    counts: dict[tuple[str, int], int],
    *,
    team: object,
    year: object,
    **metrics: int | float | None,
) -> None:
    for key in _yearly_average_keys(team, year):
        counts[key] += 1
        for metric, value in metrics.items():
            if isinstance(value, (int, float)):
                groups[key][metric].append(float(value))


def _yearly_average_rows(
    groups: dict[tuple[str, int], dict[str, list[float]]],
    counts: dict[tuple[str, int], int],
) -> list[dict[str, object]]:
    rows = []
    for (team, year), count in sorted(counts.items(), key=_yearly_team_item_sort_key):
        metric_values = groups.get((team, year), {})
        row: dict[str, object] = {
            "team": team,
            "year": year,
            "feature_count": count,
        }
        for metric, values in sorted(metric_values.items()):
            row[f"avg_{metric}"] = round(sum(values) / len(values), 2) if values else None
        rows.append(row)
    return rows


def _roadmap_yearly_team_rows(
    grouped: dict[tuple[str, int], dict[str, float]],
) -> list[dict[str, object]]:
    rows = []
    for (team, year), values in sorted(grouped.items(), key=_yearly_team_item_sort_key):
        if year not in FLOW_REPORT_YEARS:
            continue
        on_time = int(values.get("on_time", 0))
        delayed = int(values.get("delayed", 0))
        still_open = int(values.get("still_open", 0))
        total = on_time + delayed + still_open
        delay_count = values.get("delay_days_count", 0)
        rows.append(
            {
                "team": team,
                "year": year,
                "feature_count": total,
                "on_time": on_time,
                "delayed": delayed,
                "still_open": still_open,
                "reliability": round(on_time / total, 4) if total else 0,
                "avg_delay_days": round(values.get("delay_days_total", 0) / delay_count, 2)
                if delay_count
                else None,
            }
        )
    return rows


def _yearly_team_sort_key(key: tuple[str, int]) -> tuple[int, int, str]:
    team, year = key
    return (year, FLOW_YEARLY_AVERAGE_TEAM_ORDER.get(team, len(FLOW_YEARLY_AVERAGE_TEAMS)), team)


def _yearly_team_item_sort_key(
    item: tuple[tuple[str, int], object],
) -> tuple[int, int, str]:
    return _yearly_team_sort_key(item[0])


def _year_from_value(value: object) -> int | None:
    if isinstance(value, datetime | date):
        return value.year
    if isinstance(value, int):
        return value
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def _as_utc_datetime(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _days_between(start: datetime | date | None, end: datetime | date | None) -> int | None:
    if start is None or end is None:
        return None
    start_dt = _as_utc_datetime(start)
    end_dt = _as_utc_datetime(end)
    if end_dt < start_dt:
        return 0
    return max(0, (end_dt - start_dt).days)


def _hours_per_day(hours: float, duration_days: int | None) -> float | None:
    if duration_days is None or duration_days <= 0:
        return None
    return round(float(hours) / duration_days, 2)


def _guess_status_class(status_name: str | None) -> str:
    name = (status_name or "").lower()
    if name in {"done", "closed", "resolved"}:
        return "done"
    if "block" in name:
        return "blocked"
    if "review" in name:
        return "review"
    if "qa" in name or "test" in name:
        return "qa"
    if "progress" in name:
        return "active_work"
    return "waiting"
