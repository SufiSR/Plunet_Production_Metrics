from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import Select, String, asc, cast, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.issue_worklog import IssueWorklog
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.models.sync_log import SyncLog
from app.schemas.admin_raw_table import RawTableColumn, RawTableResponse
from app.schemas.releases import OffsetPagination


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class TableColumnSpec:
    key: str
    label: str
    expression: ColumnElement[Any]
    searchable: bool = True
    sortable: bool = True


@dataclass(frozen=True)
class TableSpec:
    key: str
    query: Select[Any]
    columns: list[TableColumnSpec]
    default_sort_key: str
    default_sort_direction: SortDirection = SortDirection.DESC


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


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _search_predicate(columns: list[TableColumnSpec], term: str) -> ColumnElement[bool]:
    lowered_term = f"%{term.lower()}%"
    searchable = [c for c in columns if c.searchable]
    if not searchable:
        return cast(True, String).is_not(None)
    return or_(*[func.lower(cast(col.expression, String)).like(lowered_term) for col in searchable])


def _sync_log_spec() -> TableSpec:
    columns = [
        TableColumnSpec("source", "Source", SyncLog.source),
        TableColumnSpec("started_at", "Started At", SyncLog.started_at),
        TableColumnSpec("finished_at", "Finished At", SyncLog.finished_at),
        TableColumnSpec("status", "Status", SyncLog.status),
        TableColumnSpec("records_processed", "Records Processed", SyncLog.records_processed),
        TableColumnSpec("error_message", "Error", SyncLog.error_message),
    ]
    return TableSpec(
        key="sync_log",
        query=select(*[c.expression.label(c.key) for c in columns]).select_from(SyncLog),
        columns=columns,
        default_sort_key="started_at",
    )


def _repository_spec() -> TableSpec:
    columns = [
        TableColumnSpec("name", "Name", Repository.name),
        TableColumnSpec("path", "Path", Repository.path),
        TableColumnSpec("default_branch", "Default Branch", Repository.default_branch),
        TableColumnSpec("active", "Active", Repository.active),
        TableColumnSpec("updated_at", "Updated At", Repository.updated_at),
    ]
    return TableSpec(
        key="repository",
        query=select(*[c.expression.label(c.key) for c in columns]).select_from(Repository),
        columns=columns,
        default_sort_key="name",
        default_sort_direction=SortDirection.ASC,
    )


def _release_spec() -> TableSpec:
    columns = [
        TableColumnSpec("repository", "Repository", Repository.path),
        TableColumnSpec("tag_name", "Tag", Release.tag_name),
        TableColumnSpec("customer_release", "Customer Release", Release.customer_release),
        TableColumnSpec("committed_at", "Committed At", Release.committed_at),
    ]
    return TableSpec(
        key="release",
        query=select(*[c.expression.label(c.key) for c in columns])
        .select_from(Release)
        .join(Repository, Repository.id == Release.repository_id),
        columns=columns,
        default_sort_key="committed_at",
    )


def _production_bug_spec() -> TableSpec:
    columns = [
        TableColumnSpec("jira_key", "Jira Key", ProductionBug.jira_key),
        TableColumnSpec("summary", "Summary", ProductionBug.summary),
        TableColumnSpec("status", "Status", ProductionBug.status),
        TableColumnSpec("priority", "Priority", ProductionBug.priority),
        TableColumnSpec("healthy", "Healthy", ProductionBug.healthy),
        TableColumnSpec("created_at", "Created At", ProductionBug.created_at),
        TableColumnSpec("closed_at", "Closed At", ProductionBug.closed_at),
    ]
    return TableSpec(
        key="production_bug",
        query=select(*[c.expression.label(c.key) for c in columns]).select_from(ProductionBug),
        columns=columns,
        default_sort_key="created_at",
    )


def _merge_request_spec() -> TableSpec:
    columns = [
        TableColumnSpec("repository", "Repository", Repository.path),
        TableColumnSpec("gitlab_mr_id", "MR ID", MergeRequest.gitlab_mr_id),
        TableColumnSpec("title", "Title", MergeRequest.title),
        TableColumnSpec("author", "Author", MergeRequest.author),
        TableColumnSpec("target_branch", "Target Branch", MergeRequest.target_branch),
        TableColumnSpec("jira_key", "Jira Key", MergeRequest.jira_key),
        TableColumnSpec("merged_at", "Merged At", MergeRequest.merged_at),
    ]
    return TableSpec(
        key="merge_request",
        query=select(*[c.expression.label(c.key) for c in columns])
        .select_from(MergeRequest)
        .join(Repository, Repository.id == MergeRequest.repository_id),
        columns=columns,
        default_sort_key="merged_at",
    )


def _issue_worklog_spec() -> TableSpec:
    columns = [
        TableColumnSpec("bug_jira_key", "Bug Jira Key", ProductionBug.jira_key),
        TableColumnSpec("jira_account_id", "Jira Account ID", IssueWorklog.jira_account_id),
        TableColumnSpec("author", "Author", IssueWorklog.author),
        TableColumnSpec("started", "Started", IssueWorklog.started),
        TableColumnSpec("time_spent_seconds", "Time Spent (s)", IssueWorklog.time_spent_seconds),
        TableColumnSpec("created_at", "Created At", IssueWorklog.created_at),
    ]
    return TableSpec(
        key="issue_worklog",
        query=select(*[c.expression.label(c.key) for c in columns])
        .select_from(IssueWorklog)
        .join(ProductionBug, ProductionBug.id == IssueWorklog.bug_id),
        columns=columns,
        default_sort_key="started",
    )


TABLE_SPECS: dict[str, TableSpec] = {
    spec.key: spec
    for spec in [
        _sync_log_spec(),
        _repository_spec(),
        _release_spec(),
        _production_bug_spec(),
        _merge_request_spec(),
        _issue_worklog_spec(),
    ]
}


def list_admin_raw_table_rows(
    db: Session,
    *,
    table_name: str,
    page: int,
    size: int,
    search: str | None,
    sort_by: str | None,
    sort_dir: SortDirection,
) -> RawTableResponse:
    spec = TABLE_SPECS.get(table_name)
    if spec is None:
        raise ValueError(f"Unsupported table '{table_name}'")

    visible_columns = spec.columns
    sortable_columns = {column.key: column for column in visible_columns if column.sortable}
    selected_sort = sort_by if sort_by in sortable_columns else spec.default_sort_key
    sort_column = sortable_columns[selected_sort]
    sort_expression = (
        desc(sort_column.expression)
        if sort_dir == SortDirection.DESC
        else asc(sort_column.expression)
    )

    filtered = spec.query
    if search and search.strip():
        filtered = filtered.where(_search_predicate(visible_columns, search.strip()))

    total_query = select(func.count()).select_from(filtered.order_by(None).subquery())
    total = int(db.execute(total_query).scalar_one())
    paged = filtered.order_by(sort_expression).offset(page * size).limit(size)
    result = db.execute(paged).mappings().all()

    rows = [{key: _serialize_value(value) for key, value in dict(row).items()} for row in result]

    return RawTableResponse(
        table=table_name,
        columns=[
            RawTableColumn(key=column.key, label=column.label, sortable=column.sortable)
            for column in visible_columns
        ],
        rows=rows,
        pagination=_offset_pagination(page=page, size=size, total=total),
    )
