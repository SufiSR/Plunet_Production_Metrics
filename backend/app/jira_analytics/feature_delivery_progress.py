"""Derive PMGT feature delivery progress from linked implementer issue statuses."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jira_analytics.models import JiraIssue, JiraIssueRelation

IMPLEMENTED_BY_INWARD = "is implemented by"


class _ImplementerBucket(str, Enum):
    DONE = "done"
    IN_PROGRESS = "in_progress"
    BEFORE_IN_PROGRESS = "before_in_progress"


def _classify_implementer_status(
    status_name: str | None,
    status_category_key: str | None,
) -> _ImplementerBucket:
    category = (status_category_key or "").strip().lower()
    name = (status_name or "").strip().lower()
    if category == "done" or name in {"done", "closed", "resolved"}:
        return _ImplementerBucket.DONE
    if category == "indeterminate" or name == "in progress":
        return _ImplementerBucket.IN_PROGRESS
    return _ImplementerBucket.BEFORE_IN_PROGRESS


def compute_delivery_progress(buckets: Iterable[_ImplementerBucket]) -> str | None:
    """Roll up implementer statuses into feature-level delivery progress."""
    items = list(buckets)
    if not items:
        return None
    if all(bucket == _ImplementerBucket.DONE for bucket in items):
        return "Done"
    if any(bucket == _ImplementerBucket.IN_PROGRESS for bucket in items):
        return "In progress"
    if all(bucket == _ImplementerBucket.BEFORE_IN_PROGRESS for bucket in items):
        return "In preparation"
    # Mixed done + not-started (no active in-progress implementer) still means delivery started.
    return "In progress"


def delivery_progress_by_root_issue_id(
    db: Session,
    root_issue_ids: list[int],
) -> dict[int, str]:
    if not root_issue_ids:
        return {}
    inward = func.lower(func.coalesce(JiraIssueRelation.inward_description, ""))
    stmt = (
        select(
            JiraIssueRelation.source_issue_id,
            JiraIssue.status_name,
            JiraIssue.status_category_key,
        )
        .join(JiraIssue, JiraIssue.id == JiraIssueRelation.target_issue_id)
        .where(
            JiraIssueRelation.source_issue_id.in_(root_issue_ids),
            JiraIssueRelation.direction == "inward",
            inward == IMPLEMENTED_BY_INWARD.lower(),
            JiraIssueRelation.target_issue_id.is_not(None),
        )
    )
    buckets_by_root: dict[int, list[_ImplementerBucket]] = {}
    for root_issue_id, status_name, status_category_key in db.execute(stmt).all():
        root_id = int(root_issue_id)
        buckets_by_root.setdefault(root_id, []).append(
            _classify_implementer_status(status_name, status_category_key)
        )
    out: dict[int, str] = {}
    for root_id, buckets in buckets_by_root.items():
        progress = compute_delivery_progress(buckets)
        if progress is not None:
            out[root_id] = progress
    return out
