from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.jira_analytics.extractors import _is_pmgt_issue_key
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraIssueRelation,
    JiraProject,
)

DEFAULT_ROOT_PROJECT_KEYS = ("PMGT",)
DEFAULT_ROOT_ISSUE_TYPES = ("Project", "Idea", "Epic", "Feature")
DEFAULT_TRAVERSED_RELATION_SOURCES = (
    "connected_pmgt_issue",
    "parent",
    "subtask",
    "epic_link",
    "issue_link",
)
REVERSE_TRAVERSAL_SOURCES = frozenset(
    {
        "parent",
        "epic_link",
        "connected_pmgt_issue",
        "issue_link",
    }
)
HIERARCHY_RELATION_BASES = frozenset(
    {
        "parent",
        "subtask",
        "epic_link",
        "parent_field",
        "epic_link_field",
    }
)
IMPLEMENTATION_LINK_TYPES = frozenset(
    {
        "implements",
        "is implemented by",
        "implementation",
        "is part of",
        "includes",
    }
)
# Attachment at or above this level wins over weaker cross-links to another PMGT tree.
STRONG_ATTACHMENT_THRESHOLD = 70


@dataclass(slots=True)
class FeatureMembershipCounts:
    roots_upserted: int = 0
    memberships_written: int = 0


@dataclass(frozen=True, slots=True)
class _TraversalEdge:
    target_issue_id: int
    reason: str
    relation_id: int | None = None
    link_type_name: str = ""
    target_key: str | None = None


@dataclass(frozen=True, slots=True)
class _MembershipCandidate:
    feature_root_id: int
    feature_root_key: str
    member_issue_id: int
    depth: int
    path_issue_keys: list[str]
    path_relation_ids: list[int]
    inclusion_reason: str
    nearest_parent_issue_id: int | None
    direct_relation_id: int | None
    attachment_strength: int
    path_min_strength: int


def _relation_base(reason: str) -> str:
    return reason.removesuffix("_reverse")


def _edge_strength(*, reason: str, link_type_name: str, target_key: str | None) -> int:
    base = _relation_base(reason)
    if base == "connected_pmgt_issue" and _is_pmgt_issue_key(target_key):
        return 100
    if base in HIERARCHY_RELATION_BASES:
        return 80
    if base == "issue_link":
        if link_type_name.strip().lower() in IMPLEMENTATION_LINK_TYPES:
            return 70
        return 50
    if base == "connected_pmgt_issue":
        return 60
    return 40


def _collect_direct_attachment_candidates(
    db: Session,
    *,
    issue: JiraIssue,
    root_by_key: dict[str, JiraFeatureRoot],
    root_by_issue_id: dict[int, JiraFeatureRoot],
    issue_by_id: dict[int, JiraIssue],
) -> list[_MembershipCandidate]:
    """Links declared on the issue itself to a PMGT root (supersede weak cross-tree paths)."""
    direct: list[_MembershipCandidate] = []
    relations = db.execute(
        select(JiraIssueRelation).where(
            JiraIssueRelation.source_issue_id == issue.id,
            JiraIssueRelation.is_feature_membership_edge.is_(True),
        )
    ).scalars()
    for relation in relations:
        target_key = relation.target_key
        if not target_key or not _is_pmgt_issue_key(target_key):
            continue
        root = root_by_key.get(target_key)
        if root is None:
            continue
        strength = _edge_strength(
            reason=relation.relation_source,
            link_type_name=relation.link_type_name,
            target_key=target_key,
        )
        direct.append(
            _MembershipCandidate(
                feature_root_id=root.id,
                feature_root_key=root.root_key,
                member_issue_id=issue.id,
                depth=1,
                path_issue_keys=[root.root_key, issue.key],
                path_relation_ids=[relation.id] if relation.id else [],
                inclusion_reason=relation.relation_source,
                nearest_parent_issue_id=None,
                direct_relation_id=relation.id,
                attachment_strength=strength,
                path_min_strength=strength,
            )
        )

    visited_parents: set[int] = set()
    parent_id = issue.parent_issue_id
    depth = 0
    path_keys = [issue.key]
    while parent_id is not None and parent_id not in visited_parents:
        visited_parents.add(parent_id)
        depth += 1
        parent = issue_by_id.get(parent_id)
        if parent is None:
            break
        path_keys.insert(0, parent.key)
        root = root_by_issue_id.get(parent.id)
        if root is not None:
            strength = 80
            direct.append(
                _MembershipCandidate(
                    feature_root_id=root.id,
                    feature_root_key=root.root_key,
                    member_issue_id=issue.id,
                    depth=depth,
                    path_issue_keys=[root.root_key, *path_keys],
                    path_relation_ids=[],
                    inclusion_reason="parent_chain",
                    nearest_parent_issue_id=parent_id,
                    direct_relation_id=None,
                    attachment_strength=strength,
                    path_min_strength=strength,
                )
            )
            break
        parent_id = parent.parent_issue_id
    return direct


def _resolve_primary_membership(
    candidates: list[_MembershipCandidate],
    *,
    root_by_id: dict[int, JiraFeatureRoot],
    issue_by_id: dict[int, JiraIssue],
) -> _MembershipCandidate | None:
    if not candidates:
        return None
    if len({candidate.feature_root_id for candidate in candidates}) > 1:
        not_archived = [
            candidate
            for candidate in candidates
            if not _root_is_archived(root_by_id.get(candidate.feature_root_id), issue_by_id)
        ]
        if not_archived:
            candidates = not_archived
        project_candidates = [
            candidate
            for candidate in candidates
            if _root_issue_type(candidate, root_by_id) == "project"
        ]
        if project_candidates:
            candidates = project_candidates
    strong = [
        candidate
        for candidate in candidates
        if candidate.attachment_strength >= STRONG_ATTACHMENT_THRESHOLD
    ]
    pool = strong if strong else candidates
    return max(
        pool,
        key=lambda candidate: (
            candidate.attachment_strength,
            candidate.path_min_strength,
            -candidate.depth,
            candidate.feature_root_key,
        ),
    )


def _root_issue_type(
    candidate: _MembershipCandidate,
    root_by_id: dict[int, JiraFeatureRoot],
) -> str:
    root = root_by_id.get(candidate.feature_root_id)
    return (root.root_issue_type_name if root else "").strip().lower()


def _truthy_jira_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "archived"}
    if isinstance(value, dict):
        raw = value.get("value") or value.get("name") or value.get("id")
        return _truthy_jira_value(raw)
    return bool(value)


def _root_is_archived(
    root: JiraFeatureRoot | None,
    issue_by_id: dict[int, JiraIssue],
) -> bool:
    if root is None:
        return False
    issue = issue_by_id.get(root.root_issue_id)
    fields = issue.raw_fields_json if issue and isinstance(issue.raw_fields_json, dict) else {}
    return _truthy_jira_value(fields.get("customfield_10251"))


def detect_feature_roots(
    db: Session,
    *,
    root_project_keys: tuple[str, ...] = DEFAULT_ROOT_PROJECT_KEYS,
    root_issue_types: tuple[str, ...] = DEFAULT_ROOT_ISSUE_TYPES,
) -> int:
    stmt = (
        select(JiraIssue, JiraProject)
        .join(JiraProject, JiraProject.id == JiraIssue.project_id)
        .where(
            JiraProject.key.in_(root_project_keys),
            JiraIssue.issue_type_name.in_(root_issue_types),
        )
    )
    count = 0
    seen_ids: set[int] = set()
    for issue, project in db.execute(stmt).all():
        seen_ids.add(issue.id)
        root = db.execute(
            select(JiraFeatureRoot).where(JiraFeatureRoot.root_issue_id == issue.id)
        ).scalar_one_or_none()
        if root is None:
            root = JiraFeatureRoot(
                root_issue_id=issue.id,
                root_key=issue.key,
                root_project_key=project.key,
                detection_rule="project_issue_type",
                active=True,
            )
            db.add(root)
        root.root_key = issue.key
        root.root_project_key = project.key
        root.root_issue_type_name = issue.issue_type_name
        root.name = issue.summary
        root.active = True
        count += 1
    if root_project_keys and root_issue_types:
        for stale in db.execute(select(JiraFeatureRoot)).scalars():
            if stale.root_issue_id not in seen_ids and stale.detection_rule == "project_issue_type":
                stale.active = False
    db.flush()
    return count


def _build_traversal_adjacency(
    db: Session,
    *,
    issue_by_id: dict[int, JiraIssue],
    relation_sources: tuple[str, ...],
    link_types: tuple[str, ...] | None,
    excluded_link_types: tuple[str, ...],
) -> dict[int, list[_TraversalEdge]]:
    stmt = select(JiraIssueRelation).where(
        JiraIssueRelation.target_issue_id.is_not(None),
        JiraIssueRelation.is_feature_membership_edge.is_(True),
        JiraIssueRelation.relation_source.in_(relation_sources),
    )
    if link_types:
        stmt = stmt.where(JiraIssueRelation.link_type_name.in_(link_types))
    if excluded_link_types:
        stmt = stmt.where(JiraIssueRelation.link_type_name.not_in(excluded_link_types))

    adjacency: dict[int, list[_TraversalEdge]] = {}
    seen_pairs: set[tuple[int, int, str]] = set()

    def _add_edge(
        source_id: int,
        target_id: int,
        *,
        reason: str,
        relation_id: int | None,
        link_type_name: str,
        target_key: str | None,
    ) -> None:
        if target_id not in issue_by_id:
            return
        key = (source_id, target_id, reason)
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        target_issue = issue_by_id[target_id]
        adjacency.setdefault(source_id, []).append(
            _TraversalEdge(
                target_issue_id=target_id,
                reason=reason,
                relation_id=relation_id,
                link_type_name=link_type_name,
                target_key=target_key or target_issue.key,
            )
        )

    for relation in db.execute(stmt).scalars():
        source_id = relation.source_issue_id
        target_id = relation.target_issue_id
        if target_id is None:
            continue
        target_issue = issue_by_id.get(target_id)
        target_key = relation.target_key or (target_issue.key if target_issue else None)
        link_type_name = relation.link_type_name or ""
        _add_edge(
            source_id,
            target_id,
            reason=relation.relation_source,
            relation_id=relation.id,
            link_type_name=link_type_name,
            target_key=target_key,
        )
        if relation.relation_source in REVERSE_TRAVERSAL_SOURCES:
            source_issue = issue_by_id.get(source_id)
            _add_edge(
                target_id,
                source_id,
                reason=f"{relation.relation_source}_reverse",
                relation_id=relation.id,
                link_type_name=link_type_name,
                target_key=source_issue.key if source_issue else None,
            )

    for issue in issue_by_id.values():
        if issue.parent_issue_id and issue.parent_issue_id in issue_by_id:
            _add_edge(
                issue.parent_issue_id,
                issue.id,
                reason="parent_field",
                relation_id=None,
                link_type_name="Parent",
                target_key=issue.key,
            )

    detail_rows = db.execute(
        select(JiraIssueDetail.issue_id, JiraIssueDetail.epic_link_issue_id).where(
            JiraIssueDetail.epic_link_issue_id.is_not(None)
        )
    ).all()
    for issue_id, epic_id in detail_rows:
        if epic_id in issue_by_id and issue_id in issue_by_id:
            epic = issue_by_id[epic_id]
            member = issue_by_id[issue_id]
            _add_edge(
                int(epic_id),
                int(issue_id),
                reason="epic_link_field",
                relation_id=None,
                link_type_name="Epic Link",
                target_key=member.key,
            )

    return adjacency


def rebuild_feature_memberships(
    db: Session,
    *,
    max_depth: int = 10,
    relation_sources: tuple[str, ...] = DEFAULT_TRAVERSED_RELATION_SOURCES,
    link_types: tuple[str, ...] | None = None,
    excluded_link_types: tuple[str, ...] = ("Duplicates", "Relates"),
) -> int:
    db.execute(delete(JiraFeatureMembership))
    roots = (
        db.execute(select(JiraFeatureRoot).where(JiraFeatureRoot.active.is_(True))).scalars().all()
    )
    root_by_id = {root.id: root for root in roots}
    root_by_issue_id = {root.root_issue_id: root for root in roots}
    root_by_key = {root.root_key: root for root in roots}
    issue_by_id = {issue.id: issue for issue in db.execute(select(JiraIssue)).scalars()}
    adjacency = _build_traversal_adjacency(
        db,
        issue_by_id=issue_by_id,
        relation_sources=relation_sources,
        link_types=link_types,
        excluded_link_types=excluded_link_types,
    )

    candidates_by_member: dict[int, list[_MembershipCandidate]] = {}

    for root in roots:
        root_issue = issue_by_id.get(root.root_issue_id)
        if root_issue is None:
            continue
        queue: deque[
            tuple[
                int,
                int,
                list[str],
                list[int],
                int | None,
                int | None,
                str,
                int,
                int,
            ]
        ] = deque()
        queue.append((root_issue.id, 0, [root_issue.key], [], None, None, "root", 100, 100))
        visited: set[int] = set()
        while queue:
            (
                issue_id,
                depth,
                path_keys,
                path_relations,
                nearest_parent_id,
                direct_relation_id,
                reason,
                path_min_strength,
                attachment_strength,
            ) = queue.popleft()
            if issue_id in visited:
                continue
            visited.add(issue_id)

            candidates_by_member.setdefault(issue_id, []).append(
                _MembershipCandidate(
                    feature_root_id=root.id,
                    feature_root_key=root.root_key,
                    member_issue_id=issue_id,
                    depth=depth,
                    path_issue_keys=list(path_keys),
                    path_relation_ids=list(path_relations),
                    inclusion_reason=reason,
                    nearest_parent_issue_id=nearest_parent_id,
                    direct_relation_id=direct_relation_id,
                    attachment_strength=attachment_strength,
                    path_min_strength=path_min_strength,
                )
            )

            if depth >= max_depth:
                continue
            for edge in adjacency.get(issue_id, []):
                target = issue_by_id.get(edge.target_issue_id)
                if target is None or target.id in visited:
                    continue
                edge_strength = _edge_strength(
                    reason=edge.reason,
                    link_type_name=edge.link_type_name,
                    target_key=edge.target_key,
                )
                next_min_strength = min(path_min_strength, edge_strength)
                queue.append(
                    (
                        target.id,
                        depth + 1,
                        path_keys + [target.key],
                        path_relations + ([edge.relation_id] if edge.relation_id else []),
                        issue_id,
                        edge.relation_id,
                        edge.reason,
                        next_min_strength,
                        edge_strength,
                    )
                )

    written = 0
    for member_issue_id, candidates in candidates_by_member.items():
        issue = issue_by_id.get(member_issue_id)
        if issue is not None:
            candidates = [
                *candidates,
                *_collect_direct_attachment_candidates(
                    db,
                    issue=issue,
                    root_by_key=root_by_key,
                    root_by_issue_id=root_by_issue_id,
                    issue_by_id=issue_by_id,
                ),
            ]
        own_root = root_by_issue_id.get(member_issue_id)
        if own_root is not None:
            winner = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.feature_root_id == own_root.id and candidate.depth == 0
                ),
                None,
            )
        else:
            winner = _resolve_primary_membership(
                candidates,
                root_by_id=root_by_id,
                issue_by_id=issue_by_id,
            )
        if winner is None:
            continue
        db.add(
            JiraFeatureMembership(
                feature_root_id=winner.feature_root_id,
                member_issue_id=winner.member_issue_id,
                depth=winner.depth,
                path_issue_keys=winner.path_issue_keys,
                path_relation_ids=winner.path_relation_ids or None,
                inclusion_reason=winner.inclusion_reason,
                nearest_parent_issue_id=winner.nearest_parent_issue_id,
                direct_relation_id=winner.direct_relation_id,
                contains_cycle=False,
            )
        )
        written += 1
    db.flush()
    return written


def refresh_feature_memberships(
    db: Session,
    *,
    root_project_keys: tuple[str, ...] = DEFAULT_ROOT_PROJECT_KEYS,
    root_issue_types: tuple[str, ...] = DEFAULT_ROOT_ISSUE_TYPES,
    max_depth: int = 10,
    relation_sources: tuple[str, ...] = DEFAULT_TRAVERSED_RELATION_SOURCES,
    link_types: tuple[str, ...] | None = None,
    excluded_link_types: tuple[str, ...] = ("Duplicates", "Relates"),
) -> FeatureMembershipCounts:
    roots = detect_feature_roots(
        db,
        root_project_keys=root_project_keys,
        root_issue_types=root_issue_types,
    )
    memberships = rebuild_feature_memberships(
        db,
        max_depth=max_depth,
        relation_sources=relation_sources,
        link_types=link_types,
        excluded_link_types=excluded_link_types,
    )
    db.commit()
    return FeatureMembershipCounts(roots_upserted=roots, memberships_written=memberships)
