from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jira_analytics.models import (
    DEFAULT_WORKFLOW_ISSUE_TYPE_KEY,
    JiraIssue,
    JiraProjectWorkflowMapping,
    JiraWorkflow,
)


def _lookup_mapping(
    mapping_index: dict[tuple[int, str], int],
    *,
    project_id: int | None,
    issue_type_id: str | None,
) -> int | None:
    if project_id is None:
        return None
    if issue_type_id:
        workflow_id = mapping_index.get((project_id, issue_type_id))
        if workflow_id is not None:
            return workflow_id
    return mapping_index.get((project_id, DEFAULT_WORKFLOW_ISSUE_TYPE_KEY))


def build_project_workflow_mapping_index(db: Session) -> dict[tuple[int, str], int]:
    rows = db.execute(
        select(
            JiraProjectWorkflowMapping.project_id,
            JiraProjectWorkflowMapping.issue_type_id,
            JiraProjectWorkflowMapping.workflow_id,
        )
    ).all()
    return {
        (project_id, issue_type_id): workflow_id
        for project_id, issue_type_id, workflow_id in rows
    }


def resolve_workflow_ids_for_issues(
    db: Session,
    issue_ids: set[int],
) -> dict[int, int]:
    if not issue_ids:
        return {}
    mapping_index = build_project_workflow_mapping_index(db)
    if not mapping_index:
        return {}

    issue_id_list = sorted(issue_ids)
    issues: list[JiraIssue] = []
    chunk_size = 1000
    for offset in range(0, len(issue_id_list), chunk_size):
        chunk = issue_id_list[offset : offset + chunk_size]
        issues.extend(db.execute(select(JiraIssue).where(JiraIssue.id.in_(chunk))).scalars().all())
    issue_by_id = {issue.id: issue for issue in issues}
    parent_ids = {
        issue.parent_issue_id
        for issue in issues
        if issue.parent_issue_id and issue.parent_issue_id not in issue_by_id
    }
    if parent_ids:
        for parent in db.execute(select(JiraIssue).where(JiraIssue.id.in_(parent_ids))).scalars():
            issue_by_id[parent.id] = parent

    resolved: dict[int, int] = {}
    for issue_id in issue_ids:
        issue = issue_by_id.get(issue_id)
        if issue is None:
            continue
        workflow_id = _lookup_mapping(
            mapping_index,
            project_id=issue.project_id,
            issue_type_id=issue.issue_type_id,
        )
        if workflow_id is None and issue.parent_issue_id:
            parent = issue_by_id.get(issue.parent_issue_id)
            if parent is not None:
                workflow_id = _lookup_mapping(
                    mapping_index,
                    project_id=parent.project_id,
                    issue_type_id=parent.issue_type_id,
                )
                if workflow_id is None:
                    workflow_id = _lookup_mapping(
                        mapping_index,
                        project_id=parent.project_id,
                        issue_type_id=issue.issue_type_id,
                    )
        if workflow_id is None:
            workflow_id = _lookup_mapping(
                mapping_index,
                project_id=issue.project_id,
                issue_type_id=DEFAULT_WORKFLOW_ISSUE_TYPE_KEY,
            )
        if workflow_id is not None:
            resolved[issue_id] = workflow_id
    return resolved


def load_workflows_by_id(db: Session, workflow_ids: set[int]) -> dict[int, JiraWorkflow]:
    if not workflow_ids:
        return {}
    rows = db.execute(select(JiraWorkflow).where(JiraWorkflow.id.in_(workflow_ids))).scalars().all()
    return {row.id: row for row in rows}
