from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jira_analytics.allocation.role_mapping import worklog_role_for_allocation_role
from app.jira_analytics.extractors import text_value
from app.jira_analytics.feature_delivery_progress import delivery_progress_by_root_issue_id
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraProject,
    MonthlyAllocatedEffort,
)
from app.jira_analytics.project_scope import (
    apply_feature_root_scope,
    apply_issue_scope,
    scope_monthly_allocated_effort,
)
from app.jira_analytics.team_names import normalize_team_name
from app.schemas.jira_analytics_reports import (
    FeatureHoursDrilldownIssue,
    FeatureHoursDrilldownResponse,
    FeatureHoursDrilldownSection,
    FeatureHoursMatrixResponse,
    FeatureHoursMatrixRow,
    RowType,
)

OTHER_BUG_TYPES = frozenset({"Bug", "Problem"})
OTHER_FEATURE_TYPES = frozenset(
    {
        "Epic",
        "New Feature",
        "Improvement",
        "Feature",
        "Idea",
        "Sub-task",
        "Subtask",
        "Development Subtask",
        "Improvement Subtask",
    }
)

ROW_OTHER_BUG = "__other_bug__"
ROW_OTHER_FEATURE = "__other_feature__"
ROW_OTHER_MISC = "__other_misc__"


@dataclass(slots=True)
class _AllocatedEffortRow:
    period: str
    hours: float
    issue_id: int | None
    issue_key: str | None
    topic_type: str
    feature_root_id: int | None
    feature_key: str | None
    feature_name: str | None
    source_role_name: str | None
    team_name: str | None


@dataclass(slots=True)
class _IssueMeta:
    key: str
    summary: str | None
    issue_type_name: str | None
    self_url: str | None
    parent_issue_id: int | None
    epic_link_issue_id: int | None
    epic_link_key: str | None
    project_key: str | None
    project_name: str | None


OTHER_ROW_LABELS: dict[str, tuple[str, RowType]] = {
    ROW_OTHER_BUG: ("Other bug", "other_bug"),
    ROW_OTHER_FEATURE: ("Other feature", "other_feature"),
    ROW_OTHER_MISC: ("Other misc", "other_misc"),
}


def _jira_base_url(settings_json: dict[str, Any]) -> str:
    jira = settings_json.get("jira")
    if isinstance(jira, dict):
        base = str(jira.get("base_url") or "").strip()
        if base:
            return base.rstrip("/")
    return "https://plunet.atlassian.net"


def _issue_url(*, base_url: str, key: str, self_url: str | None = None) -> str:
    del self_url
    return f"{base_url.rstrip('/')}/browse/{key}"


def _month_periods(*, months: int, anchor: date | None = None) -> list[str]:
    today = anchor or datetime.now(timezone.utc).date()
    year, month = today.year, today.month
    out: list[str] = []
    for _ in range(max(months, 1)):
        out.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return out


def _period_date(period: str) -> date:
    year, month = period.split("-", 1)
    return date(int(year), int(month), 1)


def _allocation_role_filter_value(role_name: str | None) -> str | None:
    if not role_name:
        return None
    return worklog_role_for_allocation_role(role_name) or role_name.strip().lower() or None


def _allocated_effort_passes_filters(
    row: _AllocatedEffortRow,
    *,
    role_filter: str | None,
    team_filter: str | None,
) -> bool:
    if role_filter:
        role = _allocation_role_filter_value(row.source_role_name)
        if role_filter == "unmapped":
            if role is not None:
                return False
        elif role != role_filter:
            return False
    if team_filter:
        row_team = normalize_team_name(row.team_name)
        filter_team = normalize_team_name(team_filter)
        if row_team != filter_team:
            return False
    return True


def _fetch_allocated_effort(
    db: Session,
    *,
    periods: list[str],
    role_filter: str | None = None,
    team_filter: str | None = None,
) -> list[_AllocatedEffortRow]:
    period_dates = [_period_date(period) for period in periods]
    if not period_dates:
        return []
    stmt = scope_monthly_allocated_effort(
        select(
            MonthlyAllocatedEffort.period_month,
            MonthlyAllocatedEffort.hours,
            MonthlyAllocatedEffort.issue_id,
            MonthlyAllocatedEffort.issue_key,
            MonthlyAllocatedEffort.topic_type,
            MonthlyAllocatedEffort.feature_root_id,
            MonthlyAllocatedEffort.feature_key,
            MonthlyAllocatedEffort.feature_name,
            MonthlyAllocatedEffort.source_role_name,
            MonthlyAllocatedEffort.team_name,
        )
        .where(MonthlyAllocatedEffort.period_month.in_(period_dates))
        .where(MonthlyAllocatedEffort.allocation_kind.in_(("direct_worklog", "indirect_allocated")))
    )
    rows: list[_AllocatedEffortRow] = []
    for row in db.execute(stmt).all():
        period = row.period_month.isoformat()[:7]
        allocated = _AllocatedEffortRow(
            period=period,
            hours=float(row.hours),
            issue_id=int(row.issue_id) if row.issue_id is not None else None,
            issue_key=row.issue_key,
            topic_type=row.topic_type,
            feature_root_id=int(row.feature_root_id) if row.feature_root_id is not None else None,
            feature_key=row.feature_key,
            feature_name=row.feature_name,
            source_role_name=row.source_role_name,
            team_name=row.team_name,
        )
        if _allocated_effort_passes_filters(
            allocated,
            role_filter=role_filter,
            team_filter=team_filter,
        ):
            rows.append(allocated)
    return rows


def _issue_meta_by_id(db: Session) -> dict[int, _IssueMeta]:
    project_key = (
        select(JiraProject.key)
        .where(JiraProject.id == JiraIssue.project_id)
        .correlate_except(JiraProject)
        .scalar_subquery()
    )
    project_name = (
        select(JiraProject.name)
        .where(JiraProject.id == JiraIssue.project_id)
        .correlate_except(JiraProject)
        .scalar_subquery()
    )
    stmt = apply_issue_scope(
        select(
            JiraIssue.id,
            JiraIssue.key,
            JiraIssue.summary,
            JiraIssue.issue_type_name,
            JiraIssue.self_url,
            JiraIssue.parent_issue_id,
            JiraIssueDetail.epic_link_issue_id,
            JiraIssueDetail.epic_link_key,
            project_key,
            project_name,
        )
        .outerjoin(JiraIssueDetail, JiraIssueDetail.issue_id == JiraIssue.id)
    )
    return {
        int(row[0]): _IssueMeta(
            key=str(row[1]),
            summary=row[2],
            issue_type_name=row[3],
            self_url=row[4],
            parent_issue_id=row[5],
            epic_link_issue_id=row[6],
            epic_link_key=row[7],
            project_key=row[8],
            project_name=row[9],
        )
        for row in db.execute(stmt).all()
    }


def _membership_by_issue(db: Session) -> dict[int, list[int]]:
    stmt = apply_feature_root_scope(
        select(JiraFeatureMembership.member_issue_id, JiraFeatureMembership.feature_root_id)
        .join(JiraFeatureRoot, JiraFeatureRoot.id == JiraFeatureMembership.feature_root_id)
        .where(JiraFeatureRoot.active.is_(True))
    )
    out: dict[int, list[int]] = defaultdict(list)
    for member_issue_id, feature_root_id in db.execute(stmt).all():
        out[int(member_issue_id)].append(int(feature_root_id))
    return dict(out)


def _feature_roots(db: Session) -> dict[int, JiraFeatureRoot]:
    roots = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureRoot)
            .where(JiraFeatureRoot.active.is_(True))
            .order_by(JiraFeatureRoot.root_key)
        )
    ).scalars()
    return {root.id: root for root in roots}


def _classify_other_topic(topic_type: str | None, meta: _IssueMeta | None = None) -> RowType:
    topic = (topic_type or "").strip()
    if topic == "unassigned_bug":
        return "other_bug"
    if topic == "issue_without_feature":
        return "other_feature"
    if topic in {"tech_support", "unclassified"}:
        return "other_misc"
    if meta is not None:
        issue_type = (meta.issue_type_name or "").strip()
        if issue_type in OTHER_BUG_TYPES:
            return "other_bug"
        if issue_type in OTHER_FEATURE_TYPES:
            return "other_feature"
    return "other_misc"


def _available_filters(
    rows: list[_AllocatedEffortRow],
) -> tuple[list[str], list[str]]:
    roles: set[str] = set()
    teams: set[str] = set()
    for row in rows:
        role = _allocation_role_filter_value(row.source_role_name)
        if role:
            roles.add(role)
        else:
            roles.add("unmapped")
        team = normalize_team_name(row.team_name)
        if team:
            teams.add(team)
    return sorted(roles), sorted(teams)


def _empty_hours(periods: list[str]) -> dict[str, float]:
    return {period: 0.0 for period in periods}


def _iso_date(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _metadata_from_raw_fields(
    raw_fields: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    if not isinstance(raw_fields, dict):
        return None, None, None
    from app.jira_analytics.extractors import (
        _extract_promised_delivery_date,
        _extract_start_date,
        _extract_team_name,
    )

    start_date = _iso_date(_extract_start_date(raw_fields))
    target_end_date = _iso_date(_extract_promised_delivery_date(raw_fields))
    _, team_name = _extract_team_name(raw_fields)
    team_name = (team_name or "").strip() or None
    return start_date, target_end_date, team_name


def _delivery_progress_from_raw(raw_fields: dict[str, Any] | None) -> str | None:
    if not isinstance(raw_fields, dict):
        return None
    return text_value(raw_fields.get("customfield_10259"))


@dataclass(slots=True)
class _FeatureRootMeta:
    feature_name: str
    start_date: str | None
    target_end_date: str | None
    delivery_progress: str | None
    team_name: str | None


def _feature_root_metadata_by_issue_id(
    db: Session,
    roots: list[JiraFeatureRoot],
) -> dict[int, _FeatureRootMeta]:
    root_issue_ids = [root.root_issue_id for root in roots]
    if not root_issue_ids:
        return {}
    stmt = apply_issue_scope(
        select(
            JiraIssue.id,
            JiraIssue.summary,
            JiraIssue.raw_fields_json,
            JiraIssueDetail.start_date,
            JiraIssueDetail.promised_delivery_date,
            JiraIssueDetail.team_name,
            JiraIssueDetail.delivery_status,
        )
        .outerjoin(JiraIssueDetail, JiraIssueDetail.issue_id == JiraIssue.id)
        .where(JiraIssue.id.in_(root_issue_ids))
    )
    computed_progress = delivery_progress_by_root_issue_id(db, root_issue_ids)
    out: dict[int, _FeatureRootMeta] = {}
    for row in db.execute(stmt).all():
        issue_id = int(row[0])
        summary = (row[1] or "").strip()
        raw_fields = row[2] if isinstance(row[2], dict) else None
        start_date = _iso_date(row[3])
        target_end_date = _iso_date(row[4])
        team_name = (row[5] or "").strip() or None
        raw_start, raw_target_end, raw_team = _metadata_from_raw_fields(raw_fields)
        start_date = start_date or raw_start
        target_end_date = target_end_date or raw_target_end
        team_name = normalize_team_name(team_name or raw_team)
        delivery_progress = computed_progress.get(issue_id)
        if delivery_progress is None:
            delivery_progress = (
                _delivery_progress_from_raw(raw_fields) or (row[6] or "").strip() or None
            )
        out[issue_id] = _FeatureRootMeta(
            feature_name=summary,
            start_date=start_date,
            target_end_date=target_end_date,
            delivery_progress=delivery_progress,
            team_name=team_name,
        )
    return out


def _hours_for_period(hours_by_period: dict[str, float], period: str) -> float:
    if period in hours_by_period:
        return float(hours_by_period[period])
    # Tolerate alternate month keys (e.g. "2026-5" vs "2026-05").
    if len(period) == 7 and period[4] == "-":
        year, month = period.split("-", 1)
        if month.isdigit():
            alt = f"{year}-{int(month):02d}"
            if alt in hours_by_period:
                return float(hours_by_period[alt])
    return 0.0


def _period_cascade_sort_key(
    hours_by_period: dict[str, float],
    periods: list[str],
    *,
    tiebreaker: str = "",
) -> tuple[float | str, ...]:
    """Descending hours: newest period first, then each older month."""
    return tuple(-_hours_for_period(hours_by_period, period) for period in periods) + (tiebreaker,)


def _sort_matrix_rows(
    rows: list[FeatureHoursMatrixRow],
    periods: list[str],
) -> list[FeatureHoursMatrixRow]:
    if not periods:
        return rows

    def sort_key(row: FeatureHoursMatrixRow) -> tuple[int, float | str, ...]:
        other_rank = 1 if row.row_type != "feature" else 0
        return (other_rank, *_period_cascade_sort_key(
            row.hours_by_period,
            periods,
            tiebreaker=row.label.lower(),
        ))

    return sorted(
        rows,
        key=sort_key,
    )


def _aggregate_hours(
    issues: list[FeatureHoursDrilldownIssue],
    periods: list[str],
) -> dict[str, float]:
    totals = _empty_hours(periods)
    for issue in issues:
        for period in periods:
            totals[period] = round(
                totals[period] + _hours_for_period(issue.hours_by_period, period),
                2,
            )
    return totals


def _sort_drilldown_issues(
    issues: list[FeatureHoursDrilldownIssue],
    periods: list[str],
) -> list[FeatureHoursDrilldownIssue]:
    if not periods:
        return sorted(issues, key=lambda item: item.issue_key)
    return sorted(
        issues,
        key=lambda item: _period_cascade_sort_key(
            item.hours_by_period,
            periods,
            tiebreaker=item.issue_key,
        ),
    )


def _add_hours(bucket: dict[str, float], period: str, hours: float) -> None:
    bucket[period] = round(bucket.get(period, 0.0) + hours, 2)


def build_feature_hours_matrix(
    db: Session,
    *,
    settings_json: dict[str, Any],
    months: int = 12,
    role_filter: str | None = None,
    team_filter: str | None = None,
    anchor: date | None = None,
) -> FeatureHoursMatrixResponse:
    periods = _month_periods(months=months, anchor=anchor)
    all_allocated_rows = _fetch_allocated_effort(db, periods=periods)
    available_roles, available_teams = _available_filters(all_allocated_rows)
    allocated_rows = [
        row
        for row in all_allocated_rows
        if _allocated_effort_passes_filters(
            row,
            role_filter=role_filter,
            team_filter=team_filter,
        )
    ]

    roots_by_id = _feature_roots(db)
    issue_meta = _issue_meta_by_id(db)

    feature_buckets: dict[int, dict[str, float]] = defaultdict(lambda: _empty_hours(periods))
    other_buckets: dict[str, dict[str, float]] = {
        ROW_OTHER_BUG: _empty_hours(periods),
        ROW_OTHER_FEATURE: _empty_hours(periods),
        ROW_OTHER_MISC: _empty_hours(periods),
    }

    for row in allocated_rows:
        if row.feature_root_id is not None and row.feature_root_id in roots_by_id:
            _add_hours(feature_buckets[row.feature_root_id], row.period, row.hours)
            continue
        meta = issue_meta.get(row.issue_id) if row.issue_id is not None else None
        row_type = _classify_other_topic(row.topic_type, meta)
        row_id = {
            "other_bug": ROW_OTHER_BUG,
            "other_feature": ROW_OTHER_FEATURE,
            "other_misc": ROW_OTHER_MISC,
        }[row_type]
        _add_hours(other_buckets[row_id], row.period, row.hours)

    root_meta_by_issue = _feature_root_metadata_by_issue_id(db, list(roots_by_id.values()))

    matrix_rows: list[FeatureHoursMatrixRow] = []
    for root in roots_by_id.values():
        hours = feature_buckets.get(root.id, _empty_hours(periods))
        if round(sum(hours.values()), 2) <= 0:
            continue
        meta = root_meta_by_issue.get(root.root_issue_id)
        stored_name = (root.name or "").strip()
        feature_name = stored_name or (meta.feature_name if meta else "") or root.root_key
        matrix_rows.append(
            FeatureHoursMatrixRow(
                row_id=root.root_key,
                label=feature_name,
                row_type="feature",
                root_key=root.root_key,
                feature_name=feature_name,
                start_date=meta.start_date if meta else None,
                target_end_date=meta.target_end_date if meta else None,
                delivery_progress=meta.delivery_progress if meta else None,
                team_name=meta.team_name if meta else None,
                hours_by_period=hours,
                total_hours=round(sum(hours.values()), 2),
            )
        )

    for row_id, label, row_type in (
        (ROW_OTHER_BUG, "Other bug", "other_bug"),
        (ROW_OTHER_FEATURE, "Other feature", "other_feature"),
        (ROW_OTHER_MISC, "Other misc", "other_misc"),
    ):
        hours = other_buckets[row_id]
        if round(sum(hours.values()), 2) <= 0:
            continue
        matrix_rows.append(
            FeatureHoursMatrixRow(
                row_id=row_id,
                label=label,
                row_type=row_type,
                hours_by_period=hours,
                total_hours=round(sum(hours.values()), 2),
            )
        )

    matrix_rows = _sort_matrix_rows(matrix_rows, periods)

    return FeatureHoursMatrixResponse(
        periods=periods,
        rows=matrix_rows,
        jira_base_url=_jira_base_url(settings_json),
        role_filter=role_filter,
        team_filter=team_filter,
        available_roles=available_roles,
        available_teams=available_teams,
    )


def _resolve_epic_for_issue(
    issue_id: int,
    *,
    issue_meta: dict[int, _IssueMeta],
    epic_issue_ids: set[int],
) -> int | None:
    visited: set[int] = set()
    current_id: int | None = issue_id
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        meta = issue_meta.get(current_id)
        if meta is None:
            return None
        if meta.epic_link_issue_id and meta.epic_link_issue_id in epic_issue_ids:
            return meta.epic_link_issue_id
        if current_id in epic_issue_ids:
            return current_id
        current_id = meta.parent_issue_id
    return None


def build_feature_hours_row_drilldown(
    db: Session,
    *,
    settings_json: dict[str, Any],
    row_id: str,
    months: int = 12,
    role_filter: str | None = None,
    team_filter: str | None = None,
    anchor: date | None = None,
) -> FeatureHoursDrilldownResponse | None:
    if row_id in OTHER_ROW_LABELS:
        return _build_other_bucket_drilldown(
            db,
            settings_json=settings_json,
            row_id=row_id,
            months=months,
            role_filter=role_filter,
            team_filter=team_filter,
            anchor=anchor,
        )
    return _build_feature_drilldown(
        db,
        settings_json=settings_json,
        root_key=row_id,
        months=months,
        role_filter=role_filter,
        team_filter=team_filter,
        anchor=anchor,
    )


def _build_other_bucket_drilldown(
    db: Session,
    *,
    settings_json: dict[str, Any],
    row_id: str,
    months: int = 12,
    role_filter: str | None = None,
    team_filter: str | None = None,
    anchor: date | None = None,
) -> FeatureHoursDrilldownResponse:
    row_label, row_type = OTHER_ROW_LABELS[row_id]
    periods = _month_periods(months=months, anchor=anchor)
    base_url = _jira_base_url(settings_json)

    issue_meta = _issue_meta_by_id(db)
    hours_by_issue: dict[int | str, dict[str, float]] = defaultdict(lambda: _empty_hours(periods))

    for row in _fetch_allocated_effort(
        db,
        periods=periods,
        role_filter=role_filter,
        team_filter=team_filter,
    ):
        if row.feature_root_id is not None:
            continue
        meta = issue_meta.get(row.issue_id) if row.issue_id is not None else None
        classified = {
            "other_bug": ROW_OTHER_BUG,
            "other_feature": ROW_OTHER_FEATURE,
            "other_misc": ROW_OTHER_MISC,
        }[_classify_other_topic(row.topic_type, meta)]
        if classified != row_id:
            continue
        issue_key: int | str = (
            row.issue_id
            if row.issue_id is not None
            else f"{row_id}-allocated-overhead-without-issue"
        )
        _add_hours(hours_by_issue[issue_key], row.period, row.hours)

    sections_map: dict[str, list[FeatureHoursDrilldownIssue]] = defaultdict(list)
    for issue_id, issue_hours in hours_by_issue.items():
        if round(sum(issue_hours.values()), 2) <= 0:
            continue
        meta = issue_meta.get(issue_id) if isinstance(issue_id, int) else None
        if meta is None:
            section_key = (
                "Allocated overhead without issue"
                if isinstance(issue_id, str)
                else "Unknown"
            )
            issue_key = issue_id if isinstance(issue_id, str) else f"issue-{issue_id}"
            summary = (
                f"{row_label} allocated overhead without issue attribution"
                if isinstance(issue_id, str)
                else None
            )
            issue_type_name = None
            issue_url = _issue_url(
                base_url=base_url,
                key=issue_key,
                self_url=None,
            )
        else:
            project_key = (meta.project_key or "").strip()
            project_name = (meta.project_name or "").strip()
            section_key = (
                f"{project_key} - {project_name}"
                if project_key and project_name
                else project_key or "Unknown project"
            )
            issue_key = meta.key
            summary = meta.summary
            issue_type_name = meta.issue_type_name
            issue_url = _issue_url(base_url=base_url, key=meta.key, self_url=meta.self_url)
        sections_map[section_key].append(
            FeatureHoursDrilldownIssue(
                issue_key=issue_key,
                issue_url=issue_url,
                summary=summary,
                issue_type_name=issue_type_name,
                depth=0,
                hours_by_period=dict(issue_hours),
                total_hours=round(sum(issue_hours.values()), 2),
                multi_feature=False,
                other_feature_keys=[],
            )
        )

    sections: list[FeatureHoursDrilldownSection] = []
    for section_key in sorted(sections_map):
        issues = _sort_drilldown_issues(sections_map[section_key], periods)
        sections.append(
            FeatureHoursDrilldownSection(
                epic_key=None,
                epic_url=None,
                epic_summary=section_key,
                total_hours=round(sum(issue.total_hours for issue in issues), 2),
                issues=issues,
            )
        )

    return FeatureHoursDrilldownResponse(
        row_id=row_id,
        row_label=row_label,
        row_type=row_type,
        feature_root_key=row_id,
        feature_summary=f"Issues without PMGT feature membership ({row_label.lower()})",
        row_url=None,
        periods=periods,
        sections=sections,
        role_filter=role_filter,
        team_filter=team_filter,
    )


def _build_feature_drilldown(
    db: Session,
    *,
    settings_json: dict[str, Any],
    root_key: str,
    months: int = 12,
    role_filter: str | None = None,
    team_filter: str | None = None,
    anchor: date | None = None,
) -> FeatureHoursDrilldownResponse | None:
    root = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureRoot).where(
                JiraFeatureRoot.root_key == root_key,
                JiraFeatureRoot.active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if root is None:
        return None

    periods = _month_periods(months=months, anchor=anchor)
    base_url = _jira_base_url(settings_json)

    roots_by_id = _feature_roots(db)
    root_key_by_id = {rid: item.root_key for rid, item in roots_by_id.items()}
    membership_by_issue = _membership_by_issue(db)
    issue_meta = _issue_meta_by_id(db)

    member_rows = db.execute(
        select(JiraFeatureMembership.member_issue_id, JiraFeatureMembership.depth).where(
            JiraFeatureMembership.feature_root_id == root.id
        )
    ).all()
    member_ids = {int(row[0]) for row in member_rows}
    depth_by_issue = {int(row[0]): int(row[1]) for row in member_rows}

    epic_issue_ids = {
        issue_id
        for issue_id in member_ids
        if (issue_meta.get(issue_id) and (issue_meta[issue_id].issue_type_name or "") == "Epic")
    }

    hours_by_issue: dict[int, dict[str, float]] = defaultdict(lambda: _empty_hours(periods))

    for row in _fetch_allocated_effort(
        db,
        periods=periods,
        role_filter=role_filter,
        team_filter=team_filter,
    ):
        if row.issue_id is None or row.feature_root_id != root.id:
            continue
        _add_hours(hours_by_issue[row.issue_id], row.period, row.hours)

    visible_issue_ids = {
        issue_id
        for issue_id, hours in hours_by_issue.items()
        if round(sum(hours.values()), 2) > 0
    }

    sections_map: dict[str | None, list[FeatureHoursDrilldownIssue]] = defaultdict(list)
    ungrouped_key: str | None = None

    for issue_id in sorted(
        visible_issue_ids,
        key=lambda i: (
            depth_by_issue.get(i, 0),
            issue_meta.get(i, _IssueMeta("", None, None, None, None, None, None, None, None)).key,
        ),
    ):
        meta = issue_meta.get(issue_id)
        if meta is None:
            continue
        if issue_id == root.root_issue_id and depth_by_issue.get(issue_id, 0) == 0:
            continue

        feature_ids = membership_by_issue.get(issue_id, [])
        other_keys = sorted(
            {root_key_by_id[fid] for fid in feature_ids if fid != root.id and fid in root_key_by_id}
        )
        multi_feature = len(other_keys) > 0

        epic_id = _resolve_epic_for_issue(
            issue_id, issue_meta=issue_meta, epic_issue_ids=epic_issue_ids
        )
        section_key: str | None
        if epic_id is not None and epic_id != issue_id:
            section_key = issue_meta[epic_id].key if epic_id in issue_meta else None
        elif (meta.issue_type_name or "") == "Epic":
            section_key = meta.key
        else:
            section_key = ungrouped_key

        issue_hours = hours_by_issue.get(issue_id, _empty_hours(periods))
        if round(sum(issue_hours.values()), 2) <= 0:
            continue

        sections_map[section_key].append(
            FeatureHoursDrilldownIssue(
                issue_key=meta.key,
                issue_url=_issue_url(base_url=base_url, key=meta.key, self_url=meta.self_url),
                summary=meta.summary,
                issue_type_name=meta.issue_type_name,
                depth=depth_by_issue.get(issue_id, 0),
                hours_by_period=issue_hours,
                total_hours=round(sum(issue_hours.values()), 2),
                multi_feature=multi_feature,
                other_feature_keys=other_keys,
            )
        )

    root_meta = issue_meta.get(root.root_issue_id) if root.root_issue_id else None
    row_url = (
        _issue_url(base_url=base_url, key=root_meta.key, self_url=root_meta.self_url)
        if root_meta
        else _issue_url(base_url=base_url, key=root.root_key, self_url=None)
    )
    root_issue_meta = issue_meta.get(root.root_issue_id)
    stored_name = (root.name or "").strip()
    row_label = stored_name or (root_issue_meta.summary if root_issue_meta else "") or root.root_key

    sections: list[FeatureHoursDrilldownSection] = []
    section_keys = sorted(
        sections_map,
        key=lambda section_key: _period_cascade_sort_key(
            _aggregate_hours(sections_map[section_key], periods),
            periods,
            tiebreaker=section_key or "Other linked issues",
        ),
    )
    for section_key in section_keys:
        if section_key is None:
            sections.append(
                FeatureHoursDrilldownSection(
                    epic_key=None,
                    epic_url=None,
                    epic_summary="Other linked issues",
                    total_hours=round(sum(issue.total_hours for issue in sections_map[None]), 2),
                    issues=_sort_drilldown_issues(sections_map[None], periods),
                )
            )
            continue
        epic_meta = next((m for m in issue_meta.values() if m.key == section_key), None)
        epic_url = (
            _issue_url(base_url=base_url, key=epic_meta.key, self_url=epic_meta.self_url)
            if epic_meta
            else _issue_url(base_url=base_url, key=section_key, self_url=None)
        )
        sections.append(
            FeatureHoursDrilldownSection(
                epic_key=section_key,
                epic_url=epic_url,
                epic_summary=epic_meta.summary if epic_meta else None,
                total_hours=round(sum(issue.total_hours for issue in sections_map[section_key]), 2),
                issues=_sort_drilldown_issues(sections_map[section_key], periods),
            )
        )

    return FeatureHoursDrilldownResponse(
        row_id=root.root_key,
        row_label=row_label,
        row_type="feature",
        feature_root_key=root.root_key,
        feature_summary=root.name,
        row_url=row_url,
        periods=periods,
        sections=sections,
        role_filter=role_filter,
        team_filter=team_filter,
    )
