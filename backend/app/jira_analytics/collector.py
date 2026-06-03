from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.jira_analytics.client import JiraAnalyticsClient
from app.jira_analytics.extractors import (
    REQUIRED_FIELD_IDS,
    RelationPayload,
    extract_field_values,
    extract_issue_core,
    extract_issue_detail,
    extract_project,
    extract_relations,
    extract_sprints,
    extract_status_transitions,
    extract_worklog,
    user_identity,
)
from app.jira_analytics.models import (
    JiraIssue,
    JiraIssueDetail,
    JiraIssueFieldValue,
    JiraIssueRelation,
    JiraIssueSprint,
    JiraIssueStatusTransition,
    JiraProject,
    JiraSprint,
    JiraUser,
    JiraWorklog,
)
from app.jira_analytics.project_scope import excluded_project_keys
from app.services.collector_progress_log import log_every_n

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class JiraAnalyticsCounts:
    issues_seen: int = 0
    issues_upserted: int = 0
    users_upserted: int = 0
    projects_upserted: int = 0
    field_values_upserted: int = 0
    worklogs_upserted: int = 0
    status_transitions_upserted: int = 0
    sprints_upserted: int = 0
    relations_upserted: int = 0
    errors: list[str] = field(default_factory=list)

    def as_records_processed(self) -> dict[str, int]:
        return {
            "issues_seen": self.issues_seen,
            "issues_upserted": self.issues_upserted,
            "users_upserted": self.users_upserted,
            "projects_upserted": self.projects_upserted,
            "field_values_upserted": self.field_values_upserted,
            "worklogs_upserted": self.worklogs_upserted,
            "status_transitions_upserted": self.status_transitions_upserted,
            "sprints_upserted": self.sprints_upserted,
            "relations_upserted": self.relations_upserted,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assign(row: object, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if hasattr(row, key):
            setattr(row, key, value)


def _upsert_user(db: Session, payload: dict[str, Any] | None) -> JiraUser | None:
    if not payload:
        return None
    account_id = str(payload.get("account_id") or "").strip()
    if not account_id:
        return None
    row = db.execute(select(JiraUser).where(JiraUser.account_id == account_id)).scalar_one_or_none()
    if row is None:
        row = JiraUser(account_id=account_id)
        db.add(row)
    _assign(row, payload)
    db.flush()
    return row


def _upsert_project(db: Session, payload: dict[str, Any] | None) -> JiraProject | None:
    if not payload:
        return None
    project_id = str(payload.get("jira_project_id") or "").strip()
    if not project_id:
        return None
    row = db.execute(
        select(JiraProject).where(JiraProject.jira_project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        row = JiraProject(jira_project_id=project_id, key=str(payload.get("key") or ""))
        db.add(row)
    _assign(row, payload)
    db.flush()
    return row


def _clear_stale_issue_key_holder(db: Session, *, key: str, keep_issue_id: int) -> None:
    """Remove duplicate rows that block updating the canonical issue key."""
    stale = db.execute(
        select(JiraIssue).where(JiraIssue.key == key, JiraIssue.id != keep_issue_id)
    ).scalar_one_or_none()
    if stale is not None:
        db.delete(stale)
        db.flush()


def _resolve_issue_row(db: Session, core: dict[str, Any]) -> JiraIssue:
    """Resolve the DB row by Jira issue id first, then issue key (handles key moves)."""
    jira_issue_id = core["jira_issue_id"]
    key = core["key"]
    row_by_id = db.execute(
        select(JiraIssue).where(JiraIssue.jira_issue_id == jira_issue_id)
    ).scalar_one_or_none()
    row_by_key = db.execute(select(JiraIssue).where(JiraIssue.key == key)).scalar_one_or_none()

    if row_by_id is not None and row_by_key is not None and row_by_id.id != row_by_key.id:
        db.delete(row_by_key)
        db.flush()
        row = row_by_id
    elif row_by_id is not None:
        row = row_by_id
    elif row_by_key is not None:
        row = row_by_key
    else:
        row = JiraIssue(
            jira_issue_id=jira_issue_id,
            key=key,
            last_seen_at=_now(),
        )
        db.add(row)
        db.flush()
        return row

    if row.key != key:
        _clear_stale_issue_key_holder(db, key=key, keep_issue_id=row.id)
    return row


def _upsert_issue(
    db: Session,
    raw_issue: dict[str, Any],
    *,
    counts: JiraAnalyticsCounts,
) -> JiraIssue | None:
    fields = raw_issue.get("fields")
    if not isinstance(fields, dict):
        return None
    project = _upsert_project(db, extract_project(fields))
    if project:
        counts.projects_upserted += 1
    users = {
        "assignee_user_id": _upsert_user(db, user_identity(fields.get("assignee"))),
        "creator_user_id": _upsert_user(db, user_identity(fields.get("creator"))),
        "reporter_user_id": _upsert_user(db, user_identity(fields.get("reporter"))),
    }
    counts.users_upserted += sum(1 for user in users.values() if user is not None)
    core = extract_issue_core(raw_issue)
    if core is None:
        return None
    row = _resolve_issue_row(db, core)
    parent = None
    parent_key = core.get("parent_key")
    if parent_key:
        parent = db.execute(
            select(JiraIssue).where(JiraIssue.key == parent_key)
        ).scalar_one_or_none()
    core["project_id"] = project.id if project else None
    core["assignee_user_id"] = users["assignee_user_id"].id if users["assignee_user_id"] else None
    core["creator_user_id"] = users["creator_user_id"].id if users["creator_user_id"] else None
    core["reporter_user_id"] = users["reporter_user_id"].id if users["reporter_user_id"] else None
    core["parent_issue_id"] = parent.id if parent else None
    core["last_seen_at"] = _now()
    _assign(row, core)
    db.flush()
    return row


def _upsert_issue_detail(db: Session, issue: JiraIssue, fields: dict[str, Any]) -> int:
    row = db.get(JiraIssueDetail, issue.id)
    if row is None:
        row = JiraIssueDetail(issue_id=issue.id)
        db.add(row)
    values = extract_issue_detail(fields)
    verifier = _upsert_user(db, user_identity(fields.get("customfield_10104")))
    maintainer = _upsert_user(db, user_identity(fields.get("customfield_10159")))
    epic_key = values.get("epic_link_key")
    epic = (
        db.execute(select(JiraIssue).where(JiraIssue.key == epic_key)).scalar_one_or_none()
        if epic_key
        else None
    )
    values["to_be_verified_by_user_id"] = verifier.id if verifier else None
    values["maintainer_user_id"] = maintainer.id if maintainer else None
    values["epic_link_issue_id"] = epic.id if epic else None
    _assign(row, values)
    db.flush()
    return 1


def _upsert_field_values(db: Session, issue: JiraIssue, raw_issue: dict[str, Any]) -> int:
    fields = raw_issue.get("fields")
    if not isinstance(fields, dict):
        return 0
    rows = extract_field_values(
        fields,
        raw_issue.get("names") if isinstance(raw_issue.get("names"), dict) else None,
        raw_issue.get("schema") if isinstance(raw_issue.get("schema"), dict) else None,
    )
    count = 0
    for values in rows:
        row = db.execute(
            select(JiraIssueFieldValue).where(
                JiraIssueFieldValue.issue_id == issue.id,
                JiraIssueFieldValue.field_id == values["field_id"],
            )
        ).scalar_one_or_none()
        if row is None:
            row = JiraIssueFieldValue(issue_id=issue.id, field_id=values["field_id"])
            db.add(row)
        _assign(row, values)
        count += 1
    db.flush()
    return count


def _upsert_sprints(db: Session, issue: JiraIssue, fields: dict[str, Any]) -> int:
    count = 0
    for values in extract_sprints(fields):
        sprint = db.execute(
            select(JiraSprint).where(JiraSprint.jira_sprint_id == values["jira_sprint_id"])
        ).scalar_one_or_none()
        if sprint is None:
            sprint = JiraSprint(jira_sprint_id=values["jira_sprint_id"])
            db.add(sprint)
        _assign(sprint, values)
        db.flush()
        link = db.get(JiraIssueSprint, {"issue_id": issue.id, "sprint_id": sprint.id})
        if link is None:
            link = JiraIssueSprint(
                issue_id=issue.id,
                sprint_id=sprint.id,
                source_field_id="customfield_10020",
            )
            db.add(link)
        link.last_seen_at = _now()
        count += 1
    db.flush()
    return count


def _upsert_worklogs(db: Session, issue: JiraIssue, worklogs: list[dict[str, Any]]) -> int:
    count = 0
    for raw in worklogs:
        values = extract_worklog(raw)
        if values is None:
            continue
        author = _upsert_user(db, values.pop("author"))
        row = db.execute(
            select(JiraWorklog).where(
                JiraWorklog.issue_id == issue.id,
                JiraWorklog.jira_worklog_id == values["jira_worklog_id"],
            )
        ).scalar_one_or_none()
        if row is None:
            row = JiraWorklog(issue_id=issue.id, jira_worklog_id=values["jira_worklog_id"])
            db.add(row)
        values["author_user_id"] = author.id if author else None
        _assign(row, values)
        count += 1
    db.flush()
    return count


def _upsert_status_transitions(
    db: Session,
    issue: JiraIssue,
    histories: list[dict[str, Any]],
) -> int:
    count = 0
    for values in extract_status_transitions(histories):
        author = _upsert_user(db, values.pop("author"))
        row = db.execute(
            select(JiraIssueStatusTransition).where(
                JiraIssueStatusTransition.issue_id == issue.id,
                JiraIssueStatusTransition.jira_history_id == values["jira_history_id"],
                JiraIssueStatusTransition.history_item_index == values["history_item_index"],
            )
        ).scalar_one_or_none()
        if row is None:
            row = JiraIssueStatusTransition(
                issue_id=issue.id,
                jira_history_id=values["jira_history_id"],
                history_item_index=values["history_item_index"],
                changed_at=values["changed_at"],
            )
            db.add(row)
        values["changed_by_user_id"] = author.id if author else None
        _assign(row, values)
        count += 1
    db.flush()
    return count


def _find_relation_row(
    db: Session,
    issue: JiraIssue,
    relation: RelationPayload,
) -> JiraIssueRelation | None:
    link_id = str(relation.jira_link_id or "").strip() or None
    if link_id:
        return db.execute(
            select(JiraIssueRelation).where(
                JiraIssueRelation.source_issue_id == issue.id,
                JiraIssueRelation.jira_link_id == link_id,
            )
        ).scalar_one_or_none()
    return db.execute(
        select(JiraIssueRelation).where(
            JiraIssueRelation.source_issue_id == issue.id,
            JiraIssueRelation.target_key == relation.target_key,
            JiraIssueRelation.relation_source == relation.relation_source,
            JiraIssueRelation.link_type_name == relation.link_type_name,
            JiraIssueRelation.direction == relation.direction,
            JiraIssueRelation.jira_link_id.is_(None),
        )
    ).scalar_one_or_none()


def _upsert_relations(db: Session, issue: JiraIssue, raw_issue: dict[str, Any]) -> int:
    count = 0
    seen_link_ids: set[str] = set()
    seen_direct_keys: set[tuple[str | None, str, str, str]] = set()
    for relation in extract_relations(raw_issue):
        link_id = str(relation.jira_link_id or "").strip() or None
        if link_id:
            if link_id in seen_link_ids:
                continue
            seen_link_ids.add(link_id)
        else:
            direct_key = (
                relation.target_key,
                relation.relation_source,
                relation.link_type_name,
                relation.direction,
            )
            if direct_key in seen_direct_keys:
                continue
            seen_direct_keys.add(direct_key)

        target = None
        if relation.target_key:
            target = db.execute(
                select(JiraIssue).where(JiraIssue.key == relation.target_key)
            ).scalar_one_or_none()
        row = _find_relation_row(db, issue, relation)
        if row is None:
            row = JiraIssueRelation(
                source_issue_id=issue.id,
                target_key=relation.target_key,
                relation_source=relation.relation_source,
                link_type_name=relation.link_type_name,
                direction=relation.direction,
                jira_link_id=link_id,
            )
            db.add(row)
        _assign(row, asdict(relation) | {"target_issue_id": target.id if target else None})
        count += 1
    db.flush()
    return count


def upsert_issue_payload(
    db: Session,
    raw_issue: dict[str, Any],
    *,
    worklogs: list[dict[str, Any]] | None = None,
    histories: list[dict[str, Any]] | None = None,
    counts: JiraAnalyticsCounts | None = None,
) -> JiraIssue | None:
    counts = counts or JiraAnalyticsCounts()
    fields = raw_issue.get("fields")
    if not isinstance(fields, dict):
        return None
    issue = _upsert_issue(db, raw_issue, counts=counts)
    if issue is None:
        return None
    counts.issues_upserted += 1
    _upsert_issue_detail(db, issue, fields)
    counts.field_values_upserted += _upsert_field_values(db, issue, raw_issue)
    counts.sprints_upserted += _upsert_sprints(db, issue, fields)
    counts.worklogs_upserted += _upsert_worklogs(db, issue, worklogs or [])
    counts.status_transitions_upserted += _upsert_status_transitions(db, issue, histories or [])
    counts.relations_upserted += _upsert_relations(db, issue, raw_issue)
    return issue


def resolve_relation_targets(db: Session) -> int:
    rows = db.execute(
        select(JiraIssueRelation).where(
            JiraIssueRelation.target_issue_id.is_(None),
            JiraIssueRelation.target_key.is_not(None),
        )
    ).scalars()
    updated = 0
    for relation in rows:
        target = db.execute(
            select(JiraIssue).where(JiraIssue.key == relation.target_key)
        ).scalar_one_or_none()
        if target is None:
            continue
        relation.target_issue_id = target.id
        updated += 1
    db.flush()
    return updated


def build_default_jql(config: ConfigurationSchema, *, lookback_days: int | None = None) -> str:
    days = lookback_days if lookback_days is not None else config.jira_analytics.scheduled_lookback_days
    lookback_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    jql = f'updated >= "{lookback_date.strftime("%Y-%m-%d")}"'
    excluded = sorted(
        {
            project.strip().upper()
            for project in [*config.jira.excluded_projects, *excluded_project_keys()]
            if project.strip()
        }
    )
    if excluded:
        quoted = ",".join(f'"{project}"' for project in excluded)
        jql += f" AND project NOT IN ({quoted})"
    return jql


def collect_jira_analytics(
    db: Session,
    *,
    config: ConfigurationSchema,
    jira_token: str,
    jira_user_email: str | None = None,
    jql: str | None = None,
    lookback_days: int | None = None,
    per_issue_cooldown_seconds: float = 0.05,
    page_cooldown_seconds: float = 0.0,
) -> JiraAnalyticsCounts:
    counts = JiraAnalyticsCounts()
    fields = list(REQUIRED_FIELD_IDS)
    with JiraAnalyticsClient(
        config.jira.base_url,
        jira_token,
        user_email=jira_user_email,
        per_issue_cooldown_seconds=per_issue_cooldown_seconds,
        page_cooldown_seconds=page_cooldown_seconds,
    ) as client:
        issues = client.search_issues(
            jql=jql or build_default_jql(config, lookback_days=lookback_days),
            fields=fields,
            expand="names,schema",
        )
        counts.issues_seen = len(issues)
        for index, raw_issue in enumerate(issues, start=1):
            key = str(raw_issue.get("key") or "").strip()
            try:
                worklogs = client.list_issue_worklogs(key) if key else []
                histories = client.list_issue_changelog(key) if key else []
                upsert_issue_payload(
                    db,
                    raw_issue,
                    worklogs=worklogs,
                    histories=histories,
                    counts=counts,
                )
            except Exception as exc:
                db.rollback()
                counts.errors.append(f"{key or '<unknown>'}: {exc}")
                logger.exception("jira analytics issue enrichment failed for %s", key)
            log_every_n(
                logger,
                prefix="jira analytics issue enrichment",
                index=index,
                total=len(issues),
            )
        counts.relations_upserted += resolve_relation_targets(db)
        db.commit()
    return counts
