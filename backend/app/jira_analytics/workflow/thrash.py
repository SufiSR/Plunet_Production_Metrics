from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jira_analytics.models import JiraIssue, JiraIssueStatusTransition
from app.jira_analytics.project_scope import apply_issue_scope

_QA_ISSUE_TYPE = "qa"
_QA_TITLE_IGNORE_MARKERS = ("autotest", "testresult")


@dataclass(slots=True)
class ThrashSummary:
    issue_id: int
    issue_key: str
    summary: str | None
    status_changes: int
    reopens: int
    ping_pong_count: int
    thrash_score: float


def is_excluded_qa_autotest_issue(
    issue_type_name: str | None,
    summary: str | None,
) -> bool:
    if (issue_type_name or "").strip().casefold() != _QA_ISSUE_TYPE:
        return False
    title = (summary or "").casefold()
    return any(marker in title for marker in _QA_TITLE_IGNORE_MARKERS)


def thrash_by_issue(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ThrashSummary]:
    stmt = apply_issue_scope(
        select(
            JiraIssueStatusTransition.issue_id,
            JiraIssue.key,
            JiraIssue.summary,
            JiraIssue.issue_type_name,
            JiraIssueStatusTransition.from_status_name,
            JiraIssueStatusTransition.to_status_name,
        )
        .join(JiraIssue, JiraIssue.id == JiraIssueStatusTransition.issue_id)
        .order_by(JiraIssueStatusTransition.issue_id, JiraIssueStatusTransition.changed_at)
    )
    if date_from is not None:
        range_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(JiraIssueStatusTransition.changed_at >= range_start)
    if date_to is not None:
        range_end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        stmt = stmt.where(JiraIssueStatusTransition.changed_at <= range_end)

    rows = db.execute(stmt).all()
    by_issue: dict[int, list[tuple]] = defaultdict(list)
    keys: dict[int, str] = {}
    summaries: dict[int, str | None] = {}
    issue_types: dict[int, str | None] = {}
    for issue_id, key, summary, issue_type_name, from_s, to_s in rows:
        keys[issue_id] = key
        summaries[issue_id] = summary
        issue_types[issue_id] = issue_type_name
        by_issue[issue_id].append((from_s, to_s))

    out: list[ThrashSummary] = []
    for issue_id, transitions in by_issue.items():
        if is_excluded_qa_autotest_issue(issue_types.get(issue_id), summaries.get(issue_id)):
            continue
        changes = len(transitions)
        reopens = sum(
            1
            for from_s, to_s in transitions
            if (from_s or "").lower() in {"done", "closed", "resolved"}
            and (to_s or "").lower() not in {"done", "closed", "resolved"}
        )
        ping_pong = 0
        for i in range(2, len(transitions)):
            a = (transitions[i - 2][1] or "").lower()
            b = (transitions[i - 1][1] or "").lower()
            c = (transitions[i][1] or "").lower()
            if a and a == c and a != b:
                ping_pong += 1
        score = changes + reopens * 3 + ping_pong * 2
        out.append(
            ThrashSummary(
                issue_id=issue_id,
                issue_key=keys[issue_id],
                summary=summaries.get(issue_id),
                status_changes=changes,
                reopens=reopens,
                ping_pong_count=ping_pong,
                thrash_score=float(score),
            )
        )
    return sorted(out, key=lambda x: -x.thrash_score)
