from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jira_analytics.models import (
    JiraIssue,
    JiraIssueStatusTransition,
    JiraProject,
    JiraProjectWorkflowMapping,
    JiraWorkflow,
)
from app.jira_analytics.project_scope import apply_issue_scope, filter_excluded_keys, is_excluded_project_key
from app.jira_analytics.workflow.status_intervals import StatusInterval, build_status_intervals
from app.jira_analytics.workflow.plunet_cloud_status_condensation import (
    condense_plunet_cloud_status,
    plunet_cloud_status_display_order,
)
from app.jira_analytics.workflow.standard_plunet_status_condensation import (
    condense_standard_plunet_status,
    standard_plunet_status_display_order,
)
from app.jira_analytics.workflow.status_waiting_catalog import (
    MAIN_WORKFLOW_SPECS,
    OTHER_WORKFLOW_SPECS,
    MainWorkflowSpec,
    OtherWorkflowSpec,
    issue_type_eligible_for_main_spec,
    issue_type_matches_any_name,
    normalize_priority_name,
    status_waiting_priority_columns,
    workflow_matches_main_spec,
    workflow_matches_other_spec,
)
from app.jira_analytics.workflow.workflow_normalization import (
    canonical_status_name,
    is_excluded_status,
    issue_type_matches_filter,
    normalize_issue_type_family,
)
from app.jira_analytics.workflow.workflow_resolution import (
    load_workflows_by_id,
    resolve_workflow_ids_for_issues,
)
from app.jira_analytics.workflow.workflow_sync import scoped_workflow_ids


def clip_interval_seconds(
    interval: StatusInterval,
    *,
    date_from: date | None,
    date_to: date | None,
) -> float:
    if date_from is None and date_to is None:
        return interval.duration_seconds
    start = interval.interval_start
    end = interval.interval_end or datetime.now(timezone.utc)
    if date_from is not None:
        range_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        if end <= range_start:
            return 0.0
        start = max(start, range_start)
    if date_to is not None:
        range_end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        if start >= range_end:
            return 0.0
        end = min(end, range_end)
    return max(0.0, (end - start).total_seconds())


def _order_statuses(
    workflow: JiraWorkflow,
    statuses: set[str],
    *,
    issue_status_sequences: list[list[str]],
) -> list[str]:
    order = workflow.status_order_json if isinstance(workflow.status_order_json, list) else []
    declared = [status for status in order if isinstance(status, str) and status in statuses]
    remaining = statuses - set(declared)
    if not remaining:
        return declared
    rank_samples: dict[str, list[int]] = defaultdict(list)
    for sequence in issue_status_sequences:
        seen: set[str] = set()
        ordered: list[str] = []
        for status in sequence:
            if status in seen:
                continue
            seen.add(status)
            ordered.append(status)
        for index, status in enumerate(ordered):
            if status in remaining:
                rank_samples[status].append(index)
    median_rank = {
        status: median(samples) if samples else float(len(remaining))
        for status, samples in rank_samples.items()
    }
    extras = sorted(remaining, key=lambda s: (median_rank.get(s, float(len(remaining))), s.lower()))
    return declared + extras


def aggregate_status_waiting_points(
    points: list[dict],
    *,
    workflow: JiraWorkflow,
    selected_issue_types: set[str] | None = None,
) -> tuple[list[dict], list[str]]:
    filtered = [
        point
        for point in points
        if selected_issue_types is None
        or str(point.get("issue_type") or "") in selected_issue_types
    ]
    days_by_status_priority_issue: dict[str, dict[str, dict[int, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    issues_by_status: dict[str, set[int]] = defaultdict(set)
    sequences_by_issue: dict[int, list[str]] = defaultdict(list)

    for point in filtered:
        status = str(point.get("status") or "")
        if not status:
            continue
        issue_id = int(point["issue_id"])
        priority = str(point.get("priority") or "Unknown")
        days = float(point["days"])
        days_by_status_priority_issue[status][priority][issue_id] += days
        issues_by_status[status].add(issue_id)
        seq = sequences_by_issue[issue_id]
        if not seq or seq[-1] != status:
            seq.append(status)

    durations_by_status_priority: dict[str, dict[str, list[float]]] = defaultdict(dict)
    all_days_by_status: dict[str, list[float]] = defaultdict(list)
    for status, by_priority in days_by_status_priority_issue.items():
        for priority, by_issue in by_priority.items():
            issue_totals = list(by_issue.values())
            durations_by_status_priority[status][priority] = issue_totals
            all_days_by_status[status].extend(issue_totals)

    return _workflow_rows_by_priority(
        workflow,
        durations_by_status_priority=durations_by_status_priority,
        issues_by_status=issues_by_status,
        all_days_by_status=all_days_by_status,
        sequences_by_issue=sequences_by_issue,
    )


def _workflow_rows_by_priority(
    workflow: JiraWorkflow,
    *,
    durations_by_status_priority: dict[str, dict[str, list[float]]],
    issues_by_status: dict[str, set[int]],
    all_days_by_status: dict[str, list[float]],
    sequences_by_issue: dict[int, list[str]],
) -> tuple[list[dict], list[str]]:
    status_names = set(durations_by_status_priority.keys())
    ordered_statuses = _order_statuses(
        workflow,
        status_names,
        issue_status_sequences=list(sequences_by_issue.values()),
    )
    priority_columns = status_waiting_priority_columns()

    rows: list[dict] = []
    for status in ordered_statuses:
        by_priority = durations_by_status_priority.get(status)
        if not by_priority:
            continue
        median_by_priority: dict[str, float | None] = {}
        average_by_priority: dict[str, float | None] = {}
        for priority in priority_columns:
            durations = by_priority.get(priority)
            median_by_priority[priority] = (
                round(median(durations), 2) if durations else None
            )
            average_by_priority[priority] = (
                round(sum(durations) / len(durations), 2) if durations else None
            )
        all_days = all_days_by_status.get(status) or []
        if not all_days:
            continue
        rows.append(
            {
                "status": status,
                "unique_issue_count": len(issues_by_status.get(status) or set()),
                "average_days_all_priorities": round(sum(all_days) / len(all_days), 2),
                "median_by_priority": median_by_priority,
                "average_by_priority": average_by_priority,
            }
        )
    return rows, priority_columns


def _collect_workflow_data_points(
    intervals: list[StatusInterval],
    *,
    workflow: JiraWorkflow,
    workflow_by_issue: dict[int, int],
    priority_by_issue: dict[int, str],
    date_from: date | None,
    date_to: date | None,
    project_keys: list[str] | None,
    main_spec: MainWorkflowSpec | None = None,
) -> list[dict]:
    points: list[dict] = []
    for interval in intervals:
        if project_keys and (interval.project_key or "") not in project_keys:
            continue
        if workflow_by_issue.get(interval.issue_id) != workflow.id:
            continue
        issue_type_name = (interval.issue_type_name or "").strip()
        if main_spec is not None:
            if not issue_type_eligible_for_main_spec(interval.issue_type_name, main_spec):
                continue
        canonical = canonical_status_name(interval.status_name)
        if not canonical or is_excluded_status(canonical):
            continue
        if main_spec is not None:
            if main_spec.catalog_key == "plunet_cloud":
                canonical = condense_plunet_cloud_status(canonical)
            elif main_spec.catalog_key == "standard_plunet":
                canonical = condense_standard_plunet_status(canonical)
        seconds = clip_interval_seconds(interval, date_from=date_from, date_to=date_to)
        if seconds <= 0:
            continue
        if not issue_type_name:
            continue
        points.append(
            {
                "issue_id": interval.issue_id,
                "issue_key": (interval.issue_key or "").strip(),
                "issue_type": issue_type_name,
                "status": canonical,
                "priority": priority_by_issue.get(interval.issue_id, "Unknown"),
                "days": seconds / 86400.0,
            }
        )
    return points


def _status_order_list(workflow: JiraWorkflow) -> list[str]:
    order = workflow.status_order_json if isinstance(workflow.status_order_json, list) else []
    return [status for status in order if isinstance(status, str)]


def _find_workflow_for_main_spec(db: Session, spec: MainWorkflowSpec) -> JiraWorkflow | None:
    for workflow in db.execute(select(JiraWorkflow)).scalars().all():
        if workflow.name and workflow_matches_main_spec(workflow.name, spec):
            return workflow
    return None


def _find_workflow_for_other_spec(db: Session, spec: OtherWorkflowSpec) -> JiraWorkflow | None:
    for workflow in db.execute(select(JiraWorkflow)).scalars().all():
        if workflow.name and workflow_matches_other_spec(workflow.name, spec):
            return workflow
    return None


def projects_for_workflow(db: Session, workflow_id: int) -> list[dict[str, str | None]]:
    stmt = (
        select(JiraProject.key, JiraProject.name)
        .join(JiraProjectWorkflowMapping, JiraProjectWorkflowMapping.project_id == JiraProject.id)
        .where(JiraProjectWorkflowMapping.workflow_id == workflow_id)
        .distinct()
        .order_by(JiraProject.key)
    )
    rows = db.execute(stmt).all()
    seen: set[str] = set()
    projects: list[dict[str, str | None]] = []
    for key, name in rows:
        if not key or key in seen or is_excluded_project_key(key):
            continue
        seen.add(key)
        projects.append({"key": key, "name": name})
    return projects


def available_status_waiting_projects(db: Session) -> list[dict[str, str | None]]:
    stmt = apply_issue_scope(
        select(JiraProject.key, JiraProject.name)
        .select_from(JiraIssueStatusTransition)
        .join(JiraIssue, JiraIssue.id == JiraIssueStatusTransition.issue_id)
    )
    rows = db.execute(stmt.distinct().order_by(JiraProject.key)).all()
    seen: set[str] = set()
    projects: list[dict[str, str | None]] = []
    for key, name in rows:
        if not key or key in seen:
            continue
        seen.add(key)
        projects.append({"key": key, "name": name})
    return projects


def _load_priority_by_issue(db: Session, issue_ids: set[int]) -> dict[int, str]:
    if not issue_ids:
        return {}
    priority_by_issue: dict[int, str] = {}
    issue_id_list = sorted(issue_ids)
    chunk_size = 1000
    for offset in range(0, len(issue_id_list), chunk_size):
        chunk = issue_id_list[offset : offset + chunk_size]
        rows = db.execute(
            select(JiraIssue.id, JiraIssue.priority_name).where(JiraIssue.id.in_(chunk))
        ).all()
        for issue_id, priority_name in rows:
            priority_by_issue[int(issue_id)] = normalize_priority_name(priority_name)
    return priority_by_issue


def discover_main_workflow_issue_types(
    intervals: list[StatusInterval],
    *,
    workflow_id: int,
    workflow_by_issue: dict[int, int],
    spec: MainWorkflowSpec,
) -> list[str]:
    names: set[str] = set()
    for interval in intervals:
        if workflow_by_issue.get(interval.issue_id) != workflow_id:
            continue
        issue_type_name = interval.issue_type_name
        if not issue_type_name or not issue_type_eligible_for_main_spec(issue_type_name, spec):
            continue
        names.add(issue_type_name.strip())
    return sorted(names, key=str.lower)


def _aggregate_intervals_for_workflow(
    db: Session,
    intervals: list[StatusInterval],
    *,
    workflow: JiraWorkflow,
    workflow_by_issue: dict[int, int],
    priority_by_issue: dict[int, str],
    date_from: date | None,
    date_to: date | None,
    project_keys: list[str] | None,
    selected_issue_type_names: set[str] | None,
    main_spec: MainWorkflowSpec | None = None,
) -> tuple[list[dict], list[str]]:
    allowed_workflow_ids = scoped_workflow_ids(db)
    if workflow.id not in allowed_workflow_ids:
        return [], []

    points = _collect_workflow_data_points(
        intervals,
        workflow=workflow,
        workflow_by_issue=workflow_by_issue,
        priority_by_issue=priority_by_issue,
        date_from=date_from,
        date_to=date_to,
        project_keys=project_keys,
        main_spec=main_spec,
    )
    selected = selected_issue_type_names
    if main_spec is not None and selected is not None:
        selected = {name for name in selected if name}
    return aggregate_status_waiting_points(
        points,
        workflow=workflow,
        selected_issue_types=selected,
    )


def build_status_waiting_sections(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    project_keys: list[str] | None,
    include_other_workflows: bool,
) -> dict[str, list[dict]]:
    if not scoped_workflow_ids(db):
        return {"main_workflows": [], "other_workflows": []}

    scoped_keys = filter_excluded_keys(project_keys) if project_keys else None
    if not scoped_keys:
        return {"main_workflows": [], "other_workflows": []}

    intervals = build_status_intervals(
        db,
        project_keys=scoped_keys,
        date_from=date_from,
        date_to=date_to,
    )
    issue_ids = {interval.issue_id for interval in intervals}
    workflow_by_issue = resolve_workflow_ids_for_issues(db, issue_ids)
    priority_by_issue = _load_priority_by_issue(db, issue_ids)

    main_workflows: list[dict] = []
    for spec in MAIN_WORKFLOW_SPECS:
        workflow = _find_workflow_for_main_spec(db, spec)
        dynamic_types: list[str] = []
        data_points: list[dict] = []
        status_order: list[str] = []
        if workflow is not None:
            data_points = _collect_workflow_data_points(
                intervals,
                workflow=workflow,
                workflow_by_issue=workflow_by_issue,
                priority_by_issue=priority_by_issue,
                date_from=date_from,
                date_to=date_to,
                project_keys=scoped_keys,
                main_spec=spec,
            )
            dynamic_types = sorted(
                {str(point["issue_type"]) for point in data_points if point.get("issue_type")},
                key=str.lower,
            )
            if spec.catalog_key == "plunet_cloud":
                status_order = plunet_cloud_status_display_order()
            elif spec.catalog_key == "standard_plunet":
                status_order = standard_plunet_status_display_order()
            else:
                status_order = _status_order_list(workflow)

        main_workflows.append(
            {
                "catalog_key": spec.catalog_key,
                "label": spec.label,
                "workflow_id": workflow.id if workflow else None,
                "workflow_name": workflow.name if workflow else spec.label,
                "issue_type_options": dynamic_types,
                "status_order": status_order,
                "data_points": data_points,
            }
        )

    other_workflows: list[dict] = []
    if include_other_workflows:
        for spec in OTHER_WORKFLOW_SPECS:
            workflow = _find_workflow_for_other_spec(db, spec)
            projects: list[dict[str, str | None]] = []
            rows: list[dict] = []
            priority_columns: list[str] = []
            if workflow is not None:
                projects = [
                    project
                    for project in projects_for_workflow(db, workflow.id)
                    if str(project.get("key") or "") in scoped_keys
                ]
                rows, priority_columns = _aggregate_intervals_for_workflow(
                    db,
                    intervals,
                    workflow=workflow,
                    workflow_by_issue=workflow_by_issue,
                    priority_by_issue=priority_by_issue,
                    date_from=date_from,
                    date_to=date_to,
                    project_keys=scoped_keys,
                    selected_issue_type_names=None,
                    main_spec=None,
                )
            other_workflows.append(
                {
                    "catalog_key": spec.catalog_key,
                    "label": spec.label,
                    "workflow_id": workflow.id if workflow else None,
                    "workflow_name": workflow.name if workflow else spec.label,
                    "projects": projects,
                    "priority_columns": priority_columns,
                    "rows": rows,
                }
            )

    return {"main_workflows": main_workflows, "other_workflows": other_workflows}


def build_status_waiting_groups(
    db: Session,
    intervals: list[StatusInterval],
    *,
    date_from: date | None,
    date_to: date | None,
    project_keys: list[str] | None,
    issue_type_family: str | None,
    workflow_name: str | None,
) -> list[dict]:
    """Legacy flat grouping helper used in unit tests."""
    allowed_workflow_ids = scoped_workflow_ids(db)
    if not allowed_workflow_ids:
        return []

    issue_ids = {interval.issue_id for interval in intervals}
    workflow_by_issue = resolve_workflow_ids_for_issues(db, issue_ids)
    priority_by_issue = _load_priority_by_issue(db, issue_ids)
    workflow_ids_in_use = {
        workflow_id
        for workflow_id in workflow_by_issue.values()
        if workflow_id in allowed_workflow_ids
    }
    workflows = load_workflows_by_id(db, workflow_ids_in_use)

    by_workflow: dict[int, dict] = defaultdict(
        lambda: {
            "durations_by_status_priority": defaultdict(lambda: defaultdict(list)),
            "sequences_by_issue": defaultdict(list),
        }
    )

    for interval in intervals:
        if project_keys and (interval.project_key or "") not in project_keys:
            continue
        if not issue_type_matches_filter(interval.issue_type_name, issue_type_family):
            continue
        canonical = canonical_status_name(interval.status_name)
        if not canonical or is_excluded_status(canonical):
            continue
        seconds = clip_interval_seconds(interval, date_from=date_from, date_to=date_to)
        if seconds <= 0:
            continue

        workflow_id = workflow_by_issue.get(interval.issue_id)
        if workflow_id is None or workflow_id not in allowed_workflow_ids:
            continue
        workflow = workflows.get(workflow_id)
        if workflow is None:
            continue
        if workflow_name and workflow.name != workflow_name:
            continue

        bucket = by_workflow[workflow_id]
        priority = priority_by_issue.get(interval.issue_id, "Unknown")
        days = seconds / 86400.0
        bucket["durations_by_status_priority"][canonical][priority].append(days)
        seq = bucket["sequences_by_issue"][interval.issue_id]
        if not seq or seq[-1] != canonical:
            seq.append(canonical)

    groups: list[dict] = []
    for workflow_id in sorted(
        by_workflow.keys(),
        key=lambda wf_id: (workflows.get(wf_id).name if workflows.get(wf_id) else "").lower(),
    ):
        workflow = workflows.get(workflow_id)
        if workflow is None:
            continue
        bucket = by_workflow[workflow_id]
        issues_by_status: dict[str, set[int]] = defaultdict(set)
        all_days_by_status: dict[str, list[float]] = defaultdict(list)
        for status, by_priority in bucket["durations_by_status_priority"].items():
            for durations in by_priority.values():
                all_days_by_status[status].extend(durations)
        for issue_id, seq in bucket["sequences_by_issue"].items():
            for status in seq:
                issues_by_status[status].add(issue_id)
        rows, priority_columns = _workflow_rows_by_priority(
            workflow,
            durations_by_status_priority=bucket["durations_by_status_priority"],
            issues_by_status=issues_by_status,
            all_days_by_status=all_days_by_status,
            sequences_by_issue=bucket["sequences_by_issue"],
        )
        if not rows:
            continue
        groups.append(
            {
                "group_key": str(workflow_id),
                "label": workflow.name,
                "workflow_id": workflow_id,
                "workflow_name": workflow.name,
                "priority_columns": priority_columns,
                "rows": rows,
            }
        )
    return groups
