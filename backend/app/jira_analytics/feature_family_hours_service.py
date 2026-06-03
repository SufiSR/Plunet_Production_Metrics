from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jira_analytics.feature_hours_service import (
    _add_hours,
    _available_filters,
    _build_feature_drilldown,
    _empty_hours,
    _feature_root_metadata_by_issue_id,
    _fetch_allocated_effort,
    _hours_for_period,
    _issue_url,
    _jira_base_url,
    _month_periods,
    _period_cascade_sort_key,
)
from app.jira_analytics.models import (
    JiraFeatureFamily,
    JiraFeatureFamilyMember,
    JiraFeatureRoot,
)
from app.jira_analytics.project_scope import apply_feature_root_scope
from app.jira_analytics.team_names import normalize_team_name
from app.schemas.jira_analytics_reports import (
    FeatureFamilyDrilldownFeature,
    FeatureFamilyHoursDrilldownResponse,
    FeatureFamilyHoursMatrixResponse,
    FeatureFamilyHoursMatrixRow,
)

DONE_STATUSES = {"done", "released", "complete", "completed", "closed", "resolved"}
PLANNED_STATUSES = {"planned", "new", "backlog", "todo", "to do", "open"}


def _rollup_progress(values: list[str | None]) -> str | None:
    normalized = [(value or "").strip().lower() for value in values if (value or "").strip()]
    if not normalized:
        return None
    if all(value in DONE_STATUSES for value in normalized):
        return "done"
    if all(value in PLANNED_STATUSES for value in normalized):
        return "planned"
    return "in progress"


def _earliest(values: list[str | None]) -> str | None:
    dates = sorted(value for value in values if value)
    return dates[0] if dates else None


def _latest(values: list[str | None]) -> str | None:
    dates = sorted(value for value in values if value)
    return dates[-1] if dates else None


def _sort_family_rows(
    rows: list[FeatureFamilyHoursMatrixRow],
    periods: list[str],
) -> list[FeatureFamilyHoursMatrixRow]:
    return sorted(
        rows,
        key=lambda row: _period_cascade_sort_key(
            row.hours_by_period,
            periods,
            tiebreaker=row.label.lower(),
        ),
    )


def _family_members(
    db: Session,
) -> tuple[list[JiraFeatureFamily], dict[int, list[JiraFeatureRoot]]]:
    families = db.execute(
        select(JiraFeatureFamily)
        .where(JiraFeatureFamily.active.is_(True))
        .order_by(func.lower(JiraFeatureFamily.name))
    ).scalars().all()
    rows = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureFamilyMember.family_id, JiraFeatureRoot)
            .join(JiraFeatureRoot, JiraFeatureRoot.id == JiraFeatureFamilyMember.feature_root_id)
            .where(JiraFeatureRoot.active.is_(True))
        )
    ).all()
    by_family: dict[int, list[JiraFeatureRoot]] = defaultdict(list)
    for family_id, root in rows:
        by_family[int(family_id)].append(root)
    return families, by_family


def build_feature_family_hours_matrix(
    db: Session,
    *,
    settings_json: dict[str, Any],
    months: int = 12,
    role_filter: str | None = None,
    team_filter: str | None = None,
    anchor: date | None = None,
) -> FeatureFamilyHoursMatrixResponse:
    periods = _month_periods(months=months, anchor=anchor)
    all_allocated_rows = _fetch_allocated_effort(db, periods=periods)
    available_roles, available_teams = _available_filters(all_allocated_rows)
    allocated_rows = [
        row
        for row in all_allocated_rows
        if not role_filter or _feature_row_matches(row.source_role_name, role_filter)
    ]
    normalized_team_filter = normalize_team_name(team_filter) if team_filter else None
    if normalized_team_filter:
        allocated_rows = [
            row
            for row in allocated_rows
            if normalize_team_name(row.team_name) == normalized_team_filter
        ]

    families, members_by_family = _family_members(db)
    root_to_family: dict[int, int] = {}
    for family_id, roots in members_by_family.items():
        for root in roots:
            root_to_family[root.id] = family_id

    all_roots_by_id = {
        root.id: root
        for root in db.execute(
            apply_feature_root_scope(
                select(JiraFeatureRoot).where(JiraFeatureRoot.active.is_(True))
            )
        ).scalars().all()
    }
    family_hours: dict[int, dict[str, float]] = defaultdict(lambda: _empty_hours(periods))
    family_teams: dict[int, set[str]] = defaultdict(set)
    unassigned_hours: dict[int, dict[str, float]] = defaultdict(lambda: _empty_hours(periods))
    unassigned_teams: dict[int, set[str]] = defaultdict(set)
    for row in allocated_rows:
        if row.feature_root_id is None:
            continue
        family_id = root_to_family.get(row.feature_root_id)
        if family_id is None:
            if row.feature_root_id in all_roots_by_id:
                _add_hours(unassigned_hours[row.feature_root_id], row.period, row.hours)
                team = normalize_team_name(row.team_name)
                if team:
                    unassigned_teams[row.feature_root_id].add(team)
            continue
        _add_hours(family_hours[family_id], row.period, row.hours)
        team = normalize_team_name(row.team_name)
        if team:
            family_teams[family_id].add(team)

    root_meta = _feature_root_metadata_by_issue_id(db, list(all_roots_by_id.values()))
    rows: list[FeatureFamilyHoursMatrixRow] = []
    for family in families:
        roots = members_by_family.get(family.id, [])
        if not roots:
            continue
        hours = family_hours.get(family.id, _empty_hours(periods))
        if round(sum(hours.values()), 2) <= 0:
            continue
        metas = [root_meta.get(root.root_issue_id) for root in roots]
        teams = {
            team
            for meta in metas
            if meta is not None and (team := normalize_team_name(meta.team_name))
        }
        teams.update(family_teams.get(family.id, set()))
        rows.append(
            FeatureFamilyHoursMatrixRow(
                row_id=str(family.id),
                family_id=family.id,
                label=family.name,
                feature_count=len(roots),
                start_date=_earliest([meta.start_date if meta else None for meta in metas]),
                target_end_date=_latest([meta.target_end_date if meta else None for meta in metas]),
                delivery_progress=_rollup_progress(
                    [meta.delivery_progress if meta else None for meta in metas]
                ),
                team_names=sorted(teams),
                hours_by_period=hours,
                total_hours=round(sum(hours.values()), 2),
            )
        )

    for root_id, hours in unassigned_hours.items():
        if round(sum(hours.values()), 2) <= 0:
            continue
        root = all_roots_by_id.get(root_id)
        if root is None:
            continue
        meta = root_meta.get(root.root_issue_id)
        feature_name = root.name or (meta.feature_name if meta else "") or root.root_key
        teams = {
            team
            for meta in (meta,)
            if meta is not None and (team := normalize_team_name(meta.team_name))
        }
        teams.update(unassigned_teams.get(root_id, set()))
        rows.append(
            FeatureFamilyHoursMatrixRow(
                row_id=f"feature:{root.root_key}",
                family_id=-root.id,
                label=feature_name,
                feature_count=1,
                start_date=meta.start_date if meta else None,
                target_end_date=meta.target_end_date if meta else None,
                delivery_progress=meta.delivery_progress if meta else None,
                team_names=sorted(teams),
                hours_by_period=hours,
                total_hours=round(sum(hours.values()), 2),
            )
        )

    return FeatureFamilyHoursMatrixResponse(
        periods=periods,
        rows=_sort_family_rows(rows, periods),
        jira_base_url=_jira_base_url(settings_json),
        role_filter=role_filter,
        team_filter=team_filter,
        available_roles=available_roles,
        available_teams=available_teams,
    )


def _feature_row_matches(source_role_name: str | None, role_filter: str) -> bool:
    from app.jira_analytics.feature_hours_service import _allocation_role_filter_value

    role = _allocation_role_filter_value(source_role_name)
    if role_filter == "unmapped":
        return role is None
    return role == role_filter


def build_feature_family_hours_drilldown(
    db: Session,
    *,
    settings_json: dict[str, Any],
    family_id: int,
    months: int = 12,
    role_filter: str | None = None,
    team_filter: str | None = None,
    anchor: date | None = None,
) -> FeatureFamilyHoursDrilldownResponse | None:
    if family_id < 0:
        root = db.get(JiraFeatureRoot, abs(family_id))
        if root is None or not root.active:
            return None
        return _build_standalone_feature_drilldown(
            db,
            settings_json=settings_json,
            root=root,
            months=months,
            role_filter=role_filter,
            team_filter=team_filter,
            anchor=anchor,
        )
    family = db.get(JiraFeatureFamily, family_id)
    if family is None or not family.active:
        return None
    periods = _month_periods(months=months, anchor=anchor)
    base_url = _jira_base_url(settings_json)
    roots = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureRoot)
            .join(
                JiraFeatureFamilyMember,
                JiraFeatureFamilyMember.feature_root_id == JiraFeatureRoot.id,
            )
            .where(JiraFeatureFamilyMember.family_id == family.id)
            .where(JiraFeatureRoot.active.is_(True))
            .order_by(func.lower(func.coalesce(JiraFeatureRoot.name, JiraFeatureRoot.root_key)))
        )
    ).scalars().all()
    root_meta = _feature_root_metadata_by_issue_id(db, roots)
    features: list[FeatureFamilyDrilldownFeature] = []
    for root in roots:
        detail = _build_feature_drilldown(
            db,
            settings_json=settings_json,
            root_key=root.root_key,
            months=months,
            role_filter=role_filter,
            team_filter=team_filter,
            anchor=anchor,
        )
        if detail is None:
            continue
        hours = _empty_hours(periods)
        for section in detail.sections:
            for issue in section.issues:
                for period in periods:
                    hours[period] = round(
                        hours[period] + _hours_for_period(issue.hours_by_period, period),
                        2,
                    )
        total = round(sum(hours.values()), 2)
        if total <= 0:
            continue
        meta = root_meta.get(root.root_issue_id)
        features.append(
            FeatureFamilyDrilldownFeature(
                root_key=root.root_key,
                feature_name=(root.name or (meta.feature_name if meta else "") or root.root_key),
                row_url=detail.row_url
                or _issue_url(base_url=base_url, key=root.root_key, self_url=None),
                start_date=meta.start_date if meta else None,
                target_end_date=meta.target_end_date if meta else None,
                delivery_progress=meta.delivery_progress if meta else None,
                team_name=meta.team_name if meta else None,
                hours_by_period=hours,
                total_hours=total,
                sections=detail.sections,
            )
        )

    features = sorted(
        features,
        key=lambda item: _period_cascade_sort_key(
            item.hours_by_period,
            periods,
            tiebreaker=item.feature_name.lower(),
        ),
    )
    return FeatureFamilyHoursDrilldownResponse(
        row_id=str(family.id),
        family_id=family.id,
        row_label=family.name,
        periods=periods,
        features=features,
        role_filter=role_filter,
        team_filter=team_filter,
    )


def _build_standalone_feature_drilldown(
    db: Session,
    *,
    settings_json: dict[str, Any],
    root: JiraFeatureRoot,
    months: int,
    role_filter: str | None,
    team_filter: str | None,
    anchor: date | None,
) -> FeatureFamilyHoursDrilldownResponse | None:
    periods = _month_periods(months=months, anchor=anchor)
    base_url = _jira_base_url(settings_json)
    root_meta = _feature_root_metadata_by_issue_id(db, [root])
    detail = _build_feature_drilldown(
        db,
        settings_json=settings_json,
        root_key=root.root_key,
        months=months,
        role_filter=role_filter,
        team_filter=team_filter,
        anchor=anchor,
    )
    if detail is None:
        return None
    hours = _empty_hours(periods)
    for section in detail.sections:
        for issue in section.issues:
            for period in periods:
                hours[period] = round(
                    hours[period] + _hours_for_period(issue.hours_by_period, period),
                    2,
                )
    meta = root_meta.get(root.root_issue_id)
    feature_name = root.name or (meta.feature_name if meta else "") or root.root_key
    return FeatureFamilyHoursDrilldownResponse(
        row_id=f"feature:{root.root_key}",
        family_id=-root.id,
        row_label=feature_name,
        periods=periods,
        features=[
            FeatureFamilyDrilldownFeature(
                root_key=root.root_key,
                feature_name=feature_name,
                row_url=detail.row_url
                or _issue_url(base_url=base_url, key=root.root_key, self_url=None),
                start_date=meta.start_date if meta else None,
                target_end_date=meta.target_end_date if meta else None,
                delivery_progress=meta.delivery_progress if meta else None,
                team_name=meta.team_name if meta else None,
                hours_by_period=hours,
                total_hours=round(sum(hours.values()), 2),
                sections=detail.sections,
            )
        ],
        role_filter=role_filter,
        team_filter=team_filter,
    )

