from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.jira_analytics.client import JiraAnalyticsClient
from app.jira_analytics.models import (
    DEFAULT_WORKFLOW_ISSUE_TYPE_KEY,
    JiraProject,
    JiraProjectWorkflowMapping,
    JiraWorkflow,
)
from app.jira_analytics.project_scope import excluded_project_keys, is_excluded_project_key

logger = logging.getLogger(__name__)

_NAMED_PROJECT_WORKFLOW = re.compile(r"^(\d+):\s*(\d+)\s+workflow\b", re.IGNORECASE)


@dataclass(slots=True)
class WorkflowSyncCounts:
    projects_scanned: int = 0
    workflow_names_collected: int = 0
    workflows_upserted: int = 0
    mappings_upserted: int = 0
    errors: list[str] = field(default_factory=list)

    def as_records_processed(self) -> dict[str, int]:
        return {
            "projects_scanned": self.projects_scanned,
            "workflow_names_collected": self.workflow_names_collected,
            "workflows_upserted": self.workflows_upserted,
            "mappings_upserted": self.mappings_upserted,
        }


def _status_reference_map(payload: dict) -> dict[str, str]:
    statuses = payload.get("statuses")
    if not isinstance(statuses, list):
        return {}
    mapping: dict[str, str] = {}
    for status in statuses:
        if not isinstance(status, dict):
            continue
        reference = str(status.get("statusReference") or status.get("id") or "").strip()
        name = str(status.get("name") or "").strip()
        if reference and name:
            mapping[reference] = name
    return mapping


def _ordered_status_names(workflow: dict, status_names_by_ref: dict[str, str]) -> list[str]:
    layout_statuses = workflow.get("statuses")
    if not isinstance(layout_statuses, list):
        return []
    ordered: list[tuple[float, str]] = []
    for index, item in enumerate(layout_statuses):
        if not isinstance(item, dict):
            continue
        reference = str(item.get("statusReference") or "").strip()
        name = status_names_by_ref.get(reference)
        if not name:
            continue
        layout = item.get("layout") if isinstance(item.get("layout"), dict) else {}
        x = float(layout.get("x") or index)
        ordered.append((x, name))
    ordered.sort(key=lambda pair: pair[0])
    seen: set[str] = set()
    names: list[str] = []
    for _, name in ordered:
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _extract_workflow_rows(
    payload: dict,
    *,
    workflow: dict,
) -> dict:
    status_names_by_ref = _status_reference_map(payload)
    status_order = _ordered_status_names(workflow, status_names_by_ref)
    entity_id = str(workflow.get("id") or "").strip()
    name = str(workflow.get("name") or "").strip()
    description = workflow.get("description")
    if not isinstance(description, str):
        description = None
    return {
        "jira_entity_id": entity_id or name,
        "name": name,
        "description": description,
        "status_order_json": status_order,
        "raw_json": workflow,
    }


def _upsert_workflow(db: Session, values: dict) -> JiraWorkflow | None:
    name = values.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    row = db.execute(select(JiraWorkflow).where(JiraWorkflow.name == name)).scalar_one_or_none()
    if row is None:
        row = JiraWorkflow(
            jira_entity_id=str(values.get("jira_entity_id") or name),
            name=name,
            description=values.get("description"),
            status_order_json=values.get("status_order_json") or [],
            raw_json=values.get("raw_json"),
        )
        db.add(row)
    else:
        row.jira_entity_id = str(values.get("jira_entity_id") or row.jira_entity_id)
        row.description = values.get("description")
        row.status_order_json = values.get("status_order_json") or []
        row.raw_json = values.get("raw_json")
        row.synced_at = datetime.now(timezone.utc)
    db.flush()
    return row


def _workflow_status_refs(workflow: dict) -> frozenset[str]:
    refs: set[str] = set()
    for item in workflow.get("statuses") or []:
        if not isinstance(item, dict):
            continue
        reference = str(item.get("statusReference") or "").strip()
        if reference:
            refs.add(reference)
    return frozenset(refs)


def _issue_type_status_ids(issue_type: dict) -> frozenset[str]:
    ids: set[str] = set()
    for status in issue_type.get("statuses") or []:
        if not isinstance(status, dict):
            continue
        status_id = str(status.get("id") or "").strip()
        if status_id:
            ids.add(status_id)
    return frozenset(ids)


def _parse_named_project_workflow(name: str) -> tuple[str, str] | None:
    match = _NAMED_PROJECT_WORKFLOW.match(name.strip())
    if match is None:
        return None
    return match.group(1), match.group(2)


def _best_workflow_name_for_statuses(
    issue_status_ids: frozenset[str],
    workflows_by_name: dict[str, tuple[dict, dict]],
) -> str | None:
    if not issue_status_ids:
        return None
    best_name: str | None = None
    best_overlap = 0
    best_ref_size = 0
    for name, (_, workflow) in workflows_by_name.items():
        refs = _workflow_status_refs(workflow)
        if not refs:
            continue
        overlap = len(refs & issue_status_ids)
        if overlap < len(issue_status_ids):
            continue
        if overlap > best_overlap or (overlap == best_overlap and len(refs) < best_ref_size):
            best_overlap = overlap
            best_ref_size = len(refs)
            best_name = name
    return best_name


def _sync_jira_workflows_via_search(
    db: Session,
    client: JiraAnalyticsClient,
    *,
    projects: list[JiraProject],
    counts: WorkflowSyncCounts,
) -> WorkflowSyncCounts:
    """Fallback when workflow scheme APIs return 403 for the configured token."""
    workflows_by_name: dict[str, tuple[dict, dict]] = {}
    try:
        for page in client.iter_workflow_search_pages():
            values = page.get("values")
            if not isinstance(values, list):
                continue
            for workflow in values:
                if not isinstance(workflow, dict):
                    continue
                name = str(workflow.get("name") or "").strip()
                if name:
                    workflows_by_name[name] = (page, workflow)
    except Exception as exc:
        counts.errors.append(f"workflow search fetch failed: {exc}")
        logger.exception("workflow search fetch failed")
        return counts

    counts.workflow_names_collected = len(workflows_by_name)
    if not workflows_by_name:
        db.execute(delete(JiraProjectWorkflowMapping))
        db.flush()
        return counts

    workflow_id_by_name: dict[str, int] = {}
    for name, (page_payload, workflow_payload) in workflows_by_name.items():
        row = _upsert_workflow(
            db,
            _extract_workflow_rows(page_payload, workflow=workflow_payload),
        )
        if row is None:
            continue
        workflow_id_by_name[name] = row.id
        counts.workflows_upserted += 1

    project_by_jira_id = {
        str(project.jira_project_id): project
        for project in projects
        if project.jira_project_id
    }
    mapping_specs: list[tuple[int, str, str | None, str]] = []

    for jira_project_id, project in project_by_jira_id.items():
        try:
            issue_types = client.get_project_issue_type_statuses(jira_project_id=jira_project_id)
        except Exception as exc:
            counts.errors.append(
                f"project statuses fetch failed for {project.key}: {exc}"
            )
            logger.exception("project statuses fetch failed for %s", project.key)
            continue

        for issue_type in issue_types:
            issue_type_id = str(issue_type.get("id") or "").strip()
            if not issue_type_id:
                continue
            issue_type_name = str(issue_type.get("name") or "").strip() or None
            workflow_name = _best_workflow_name_for_statuses(
                _issue_type_status_ids(issue_type),
                workflows_by_name,
            )
            if workflow_name is None:
                continue
            mapping_specs.append((project.id, issue_type_id, issue_type_name, workflow_name))

        for workflow_name, (_, workflow_payload) in workflows_by_name.items():
            parsed = _parse_named_project_workflow(workflow_name)
            if parsed is None:
                continue
            workflow_project_id, workflow_issue_type_id = parsed
            if workflow_project_id != jira_project_id:
                continue
            scope = workflow_payload.get("scope")
            if isinstance(scope, dict) and str(scope.get("type") or "").upper() != "PROJECT":
                continue
            issue_type_name = None
            for issue_type in issue_types:
                if str(issue_type.get("id") or "").strip() == workflow_issue_type_id:
                    issue_type_name = str(issue_type.get("name") or "").strip() or None
                    break
            mapping_specs.append(
                (project.id, workflow_issue_type_id, issue_type_name, workflow_name)
            )

    db.execute(delete(JiraProjectWorkflowMapping))
    seen_mappings: set[tuple[int, str]] = set()
    for project_id, issue_type_id, issue_type_name, workflow_name in mapping_specs:
        key = (project_id, issue_type_id)
        if key in seen_mappings:
            continue
        workflow_id = workflow_id_by_name.get(workflow_name)
        if workflow_id is None:
            continue
        seen_mappings.add(key)
        db.add(
            JiraProjectWorkflowMapping(
                project_id=project_id,
                issue_type_id=issue_type_id,
                workflow_id=workflow_id,
                issue_type_name=issue_type_name,
            )
        )
        counts.mappings_upserted += 1
    db.flush()
    logger.info(
        "workflow sync used search fallback: workflows=%s mappings=%s",
        counts.workflows_upserted,
        counts.mappings_upserted,
    )
    return counts


def sync_jira_workflows(db: Session, client: JiraAnalyticsClient) -> WorkflowSyncCounts:
    counts = WorkflowSyncCounts()
    projects = [
        project
        for project in db.execute(select(JiraProject)).scalars().all()
        if not is_excluded_project_key(project.key)
    ]
    if not projects:
        return counts

    project_by_jira_id = {
        str(project.jira_project_id): project
        for project in projects
        if project.jira_project_id
    }
    jira_project_ids = list(project_by_jira_id.keys())
    counts.projects_scanned = len(jira_project_ids)

    workflow_names: set[str] = set()
    mapping_specs: list[tuple[int, str, str | None, str]] = []

    chunk_size = 20
    for offset in range(0, len(jira_project_ids), chunk_size):
        chunk = jira_project_ids[offset : offset + chunk_size]
        try:
            associations = client.get_workflow_scheme_project_associations(project_ids=chunk)
        except Exception as exc:
            logger.warning("workflow scheme fetch failed: %s", exc)
            continue
        for association in associations:
            scheme = association.get("workflowScheme")
            if not isinstance(scheme, dict):
                continue
            project_ids_raw = association.get("projectIds")
            if not isinstance(project_ids_raw, list):
                continue
            default_workflow = str(scheme.get("defaultWorkflow") or "").strip()
            if default_workflow:
                workflow_names.add(default_workflow)
            issue_type_mappings = scheme.get("issueTypeMappings")
            if not isinstance(issue_type_mappings, dict):
                issue_type_mappings = {}
            issue_types = scheme.get("issueTypes")
            issue_type_names: dict[str, str] = {}
            if isinstance(issue_types, dict):
                for type_id, details in issue_types.items():
                    if isinstance(details, dict):
                        issue_type_names[str(type_id)] = str(details.get("name") or "").strip()

            for jira_project_id in project_ids_raw:
                project = project_by_jira_id.get(str(jira_project_id))
                if project is None:
                    continue
                if default_workflow:
                    mapping_specs.append(
                        (project.id, DEFAULT_WORKFLOW_ISSUE_TYPE_KEY, None, default_workflow)
                    )
                for issue_type_id, workflow_name in issue_type_mappings.items():
                    name = str(workflow_name or "").strip()
                    if not name:
                        continue
                    workflow_names.add(name)
                    mapping_specs.append(
                        (
                            project.id,
                            str(issue_type_id),
                            issue_type_names.get(str(issue_type_id)),
                            name,
                        )
                    )

    counts.workflow_names_collected = len(workflow_names)
    if not workflow_names:
        if counts.errors:
            logger.warning(
                "workflow scheme sync unavailable; falling back to workflow search API"
            )
        return _sync_jira_workflows_via_search(
            db,
            client,
            projects=projects,
            counts=counts,
        )

    workflows_by_name: dict[str, dict] = {}
    name_list = sorted(workflow_names)
    for offset in range(0, len(name_list), 20):
        batch = name_list[offset : offset + 20]
        try:
            payload = client.bulk_get_workflows(workflow_names=batch)
        except Exception as exc:
            counts.errors.append(f"workflow bulk fetch failed: {exc}")
            logger.exception("workflow bulk fetch failed for %s", batch)
            continue
        workflows = payload.get("workflows")
        if not isinstance(workflows, list):
            continue
        for workflow in workflows:
            if not isinstance(workflow, dict):
                continue
            name = str(workflow.get("name") or "").strip()
            if name:
                workflows_by_name[name] = (payload, workflow)

    workflow_id_by_name: dict[str, int] = {}
    for name in workflow_names:
        entry = workflows_by_name.get(name)
        if entry is None:
            counts.errors.append(f"workflow definition missing from Jira API: {name}")
            continue
        payload, workflow_payload = entry
        row = _upsert_workflow(db, _extract_workflow_rows(payload, workflow=workflow_payload))
        if row is None:
            continue
        workflow_id_by_name[name] = row.id
        counts.workflows_upserted += 1

    db.execute(delete(JiraProjectWorkflowMapping))
    for project_id, issue_type_id, issue_type_name, workflow_name in mapping_specs:
        workflow_id = workflow_id_by_name.get(workflow_name)
        if workflow_id is None:
            continue
        db.add(
            JiraProjectWorkflowMapping(
                project_id=project_id,
                issue_type_id=issue_type_id,
                workflow_id=workflow_id,
                issue_type_name=issue_type_name,
            )
        )
        counts.mappings_upserted += 1
    db.flush()
    return counts


def scoped_workflow_ids(db: Session) -> set[int]:
    stmt = (
        select(JiraProjectWorkflowMapping.workflow_id)
        .join(JiraProject, JiraProject.id == JiraProjectWorkflowMapping.project_id)
        .where(JiraProject.key.notin_(tuple(excluded_project_keys())))
    )
    return {workflow_id for workflow_id in db.execute(stmt).scalars().all() if workflow_id}
