from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.jira_analytics.feature_hours_service import (
    _feature_root_metadata_by_issue_id,
    _fetch_allocated_effort,
    _month_periods,
)
from app.jira_analytics.models import (
    JiraFeatureFamily,
    JiraFeatureFamilyMember,
    JiraFeatureFamilySuggestionDecision,
    JiraFeatureRoot,
)
from app.jira_analytics.project_scope import apply_feature_root_scope
from app.schemas.jira_feature_family_admin import (
    FeatureFamilyAdminItem,
    FeatureFamilyCreate,
    FeatureFamilyDetailResponse,
    FeatureFamilyFeatureItem,
    FeatureFamilyFeatureListResponse,
    FeatureFamilyListResponse,
    FeatureFamilyMembersPut,
    FeatureFamilyPatch,
    FeatureFamilySuggestionItem,
    FeatureFamilySuggestionsResponse,
)

STOP_WORDS = {
    "and",
    "der",
    "die",
    "das",
    "for",
    "from",
    "mit",
    "the",
    "und",
    "with",
}


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _family_item(row: JiraFeatureFamily, member_count: int = 0) -> FeatureFamilyAdminItem:
    keywords = row.suggestion_keywords if isinstance(row.suggestion_keywords, list) else []
    return FeatureFamilyAdminItem(
        id=row.id,
        name=row.name,
        description=row.description,
        suggestion_keywords=[str(item) for item in keywords],
        title_match_pattern=row.title_match_pattern,
        active=row.active,
        member_count=member_count,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _feature_display_name(root: JiraFeatureRoot, fallback: str | None = None) -> str:
    return (root.name or fallback or root.root_key).strip() or root.root_key


def _feature_hours_by_root(db: Session, *, months: int = 12) -> dict[int, float]:
    periods = _month_periods(months=months, anchor=date.today())
    totals: dict[int, float] = defaultdict(float)
    for row in _fetch_allocated_effort(db, periods=periods):
        if row.feature_root_id is not None:
            totals[row.feature_root_id] += row.hours
    return {root_id: round(hours, 2) for root_id, hours in totals.items()}


def _assignments_by_feature(db: Session) -> dict[int, tuple[int, str]]:
    rows = db.execute(
        select(
            JiraFeatureFamilyMember.feature_root_id,
            JiraFeatureFamily.id,
            JiraFeatureFamily.name,
        ).join(JiraFeatureFamily, JiraFeatureFamily.id == JiraFeatureFamilyMember.family_id)
    ).all()
    return {int(feature_id): (int(family_id), str(name)) for feature_id, family_id, name in rows}


def _feature_items(
    db: Session,
    roots: list[JiraFeatureRoot],
    *,
    include_assignment: bool = True,
) -> list[FeatureFamilyFeatureItem]:
    meta_by_issue = _feature_root_metadata_by_issue_id(db, roots)
    hours_by_root = _feature_hours_by_root(db)
    assignments = _assignments_by_feature(db) if include_assignment else {}
    items: list[FeatureFamilyFeatureItem] = []
    for root in roots:
        meta = meta_by_issue.get(root.root_issue_id)
        assigned = assignments.get(root.id)
        name = _feature_display_name(root, meta.feature_name if meta else None)
        items.append(
            FeatureFamilyFeatureItem(
                feature_root_id=root.id,
                root_key=root.root_key,
                name=name,
                start_date=meta.start_date if meta else None,
                target_end_date=meta.target_end_date if meta else None,
                delivery_progress=meta.delivery_progress if meta else None,
                team_name=meta.team_name if meta else None,
                total_hours=hours_by_root.get(root.id, 0),
                assigned_family_id=assigned[0] if assigned else None,
                assigned_family_name=assigned[1] if assigned else None,
            )
        )
    return sorted(items, key=lambda item: item.name.lower())


def list_feature_families(db: Session) -> FeatureFamilyListResponse:
    counts = dict(
        db.execute(
            select(
                JiraFeatureFamilyMember.family_id,
                func.count(JiraFeatureFamilyMember.feature_root_id),
            ).group_by(JiraFeatureFamilyMember.family_id)
        ).all()
    )
    families = db.execute(
        select(JiraFeatureFamily).order_by(
            JiraFeatureFamily.active.desc(),
            func.lower(JiraFeatureFamily.name),
        )
    ).scalars().all()
    return FeatureFamilyListResponse(
        items=[_family_item(family, int(counts.get(family.id, 0))) for family in families]
    )


def create_feature_family(db: Session, body: FeatureFamilyCreate) -> FeatureFamilyDetailResponse:
    family = JiraFeatureFamily(
        name=body.name,
        description=body.description,
        suggestion_keywords=body.suggestion_keywords,
        title_match_pattern=body.title_match_pattern,
        active=True,
    )
    db.add(family)
    db.flush()
    return get_feature_family_detail(db, family.id)


def patch_feature_family(
    db: Session,
    family_id: int,
    body: FeatureFamilyPatch,
) -> FeatureFamilyDetailResponse:
    family = db.get(JiraFeatureFamily, family_id)
    if family is None:
        raise LookupError("feature_family_not_found")
    if body.name is not None:
        family.name = body.name
    if "description" in body.model_fields_set:
        family.description = body.description
    if body.suggestion_keywords is not None:
        family.suggestion_keywords = body.suggestion_keywords
    if "title_match_pattern" in body.model_fields_set:
        family.title_match_pattern = body.title_match_pattern
    if body.active is not None:
        family.active = body.active
    db.flush()
    return get_feature_family_detail(db, family.id)


def get_feature_family_detail(db: Session, family_id: int) -> FeatureFamilyDetailResponse:
    family = db.get(JiraFeatureFamily, family_id)
    if family is None:
        raise LookupError("feature_family_not_found")
    roots = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureRoot)
            .join(
                JiraFeatureFamilyMember,
                JiraFeatureFamilyMember.feature_root_id == JiraFeatureRoot.id,
            )
            .where(JiraFeatureFamilyMember.family_id == family_id)
            .order_by(func.lower(func.coalesce(JiraFeatureRoot.name, JiraFeatureRoot.root_key)))
        )
    ).scalars().all()
    members = _feature_items(db, roots)
    return FeatureFamilyDetailResponse(
        family=_family_item(family, len(members)),
        members=members,
    )


def put_feature_family_members(
    db: Session,
    family_id: int,
    body: FeatureFamilyMembersPut,
) -> FeatureFamilyDetailResponse:
    family = db.get(JiraFeatureFamily, family_id)
    if family is None:
        raise LookupError("feature_family_not_found")
    feature_ids = sorted(set(body.feature_root_ids))
    if feature_ids:
        existing = set(
            db.execute(
                apply_feature_root_scope(
                    select(JiraFeatureRoot.id).where(JiraFeatureRoot.id.in_(feature_ids))
                )
            ).scalars().all()
        )
        missing = sorted(set(feature_ids) - existing)
        if missing:
            raise ValueError(f"Unknown feature roots: {missing}")
    db.execute(
        delete(JiraFeatureFamilyMember).where(
            JiraFeatureFamilyMember.family_id == family_id
        )
    )
    if feature_ids:
        db.execute(
            delete(JiraFeatureFamilyMember).where(
                JiraFeatureFamilyMember.feature_root_id.in_(feature_ids)
            )
        )
    for feature_id in feature_ids:
        db.add(JiraFeatureFamilyMember(family_id=family_id, feature_root_id=feature_id))
    db.flush()
    return get_feature_family_detail(db, family_id)


def list_feature_family_features(
    db: Session,
    *,
    search: str | None = None,
    unassigned_only: bool = False,
) -> FeatureFamilyFeatureListResponse:
    stmt = apply_feature_root_scope(select(JiraFeatureRoot).where(JiraFeatureRoot.active.is_(True)))
    if search and search.strip():
        q = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(JiraFeatureRoot.root_key).like(q)
            | func.lower(func.coalesce(JiraFeatureRoot.name, "")).like(q)
        )
    if unassigned_only:
        stmt = stmt.where(
            JiraFeatureRoot.id.notin_(select(JiraFeatureFamilyMember.feature_root_id))
        )
    roots = db.execute(
        stmt.order_by(func.lower(func.coalesce(JiraFeatureRoot.name, JiraFeatureRoot.root_key)))
    ).scalars().all()
    return FeatureFamilyFeatureListResponse(items=_feature_items(db, roots))


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    cleaned = re.sub(r"\[[^\]]+\]|\([^)]*\)", " ", text.lower())
    cleaned = re.sub(r"\b[a-z]+-\d+\b", " ", cleaned)
    cleaned = re.sub(r"\b\d+(?:\.\d+)+\b", " ", cleaned)
    return {
        token
        for token in re.findall(r"[a-z0-9äöüß]+", cleaned)
        if len(token) >= 3 and token not in STOP_WORDS
    }


def _family_tokens(family: JiraFeatureFamily) -> set[str]:
    keywords = family.suggestion_keywords if isinstance(family.suggestion_keywords, list) else []
    return _tokens(" ".join([family.name, family.title_match_pattern or "", *map(str, keywords)]))


def _fingerprint(
    family: JiraFeatureFamily,
    root: JiraFeatureRoot,
    matched_tokens: list[str],
) -> str:
    raw = f"{family.id}:{root.id}:{family.name}:{root.root_key}:{','.join(matched_tokens)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _suggestion_id(family_id: int, feature_root_id: int, fingerprint: str) -> str:
    return f"{family_id}-{feature_root_id}-{fingerprint}"


def _parse_suggestion_id(suggestion_id: str) -> tuple[int, int, str]:
    parts = suggestion_id.split("-", 2)
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("Invalid suggestion id")
    return int(parts[0]), int(parts[1]), parts[2]


def list_feature_family_suggestions(db: Session) -> FeatureFamilySuggestionsResponse:
    families = db.execute(
        select(JiraFeatureFamily)
        .where(JiraFeatureFamily.active.is_(True))
        .order_by(func.lower(JiraFeatureFamily.name))
    ).scalars().all()
    roots = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureRoot)
            .where(JiraFeatureRoot.active.is_(True))
            .where(JiraFeatureRoot.id.notin_(select(JiraFeatureFamilyMember.feature_root_id)))
        )
    ).scalars().all()
    rejected = {
        (int(row.family_id), int(row.feature_root_id), row.suggestion_fingerprint)
        for row in db.execute(
            select(JiraFeatureFamilySuggestionDecision).where(
                JiraFeatureFamilySuggestionDecision.decision == "rejected"
            )
        ).scalars().all()
    }
    items: list[FeatureFamilySuggestionItem] = []
    for family in families:
        family_tokens = _family_tokens(family)
        if not family_tokens:
            continue
        for root in roots:
            feature_tokens = _tokens(root.name or root.root_key)
            matched = sorted(family_tokens & feature_tokens)
            if not matched:
                continue
            confidence = min(0.95, 0.45 + (len(matched) / max(len(family_tokens), 1)) * 0.5)
            fingerprint = _fingerprint(family, root, matched)
            if (family.id, root.id, fingerprint) in rejected:
                continue
            reason = f"matched tokens: {', '.join(matched)}"
            items.append(
                FeatureFamilySuggestionItem(
                    suggestion_id=_suggestion_id(family.id, root.id, fingerprint),
                    family_id=family.id,
                    family_name=family.name,
                    feature_root_id=root.id,
                    root_key=root.root_key,
                    feature_name=_feature_display_name(root),
                    confidence=round(confidence, 2),
                    reason=reason,
                    matched_tokens=matched,
                )
            )
    return FeatureFamilySuggestionsResponse(
        items=sorted(
            items,
            key=lambda item: (-item.confidence, item.family_name, item.feature_name),
        )
    )


def accept_feature_family_suggestion(
    db: Session,
    suggestion_id: str,
    *,
    reason: str | None = None,
) -> FeatureFamilyDetailResponse:
    family_id, feature_root_id, fingerprint = _parse_suggestion_id(suggestion_id)
    family = db.get(JiraFeatureFamily, family_id)
    root = db.get(JiraFeatureRoot, feature_root_id)
    if family is None or root is None:
        raise LookupError("suggestion_not_found")
    db.execute(
        delete(JiraFeatureFamilyMember).where(
            JiraFeatureFamilyMember.feature_root_id == root.id
        )
    )
    db.add(JiraFeatureFamilyMember(family_id=family.id, feature_root_id=root.id))
    _record_suggestion_decision(
        db,
        family_id=family.id,
        feature_root_id=root.id,
        fingerprint=fingerprint,
        decision="accepted",
        reason=reason,
    )
    db.flush()
    return get_feature_family_detail(db, family.id)


def reject_feature_family_suggestion(
    db: Session,
    suggestion_id: str,
    *,
    reason: str | None = None,
) -> FeatureFamilySuggestionsResponse:
    family_id, feature_root_id, fingerprint = _parse_suggestion_id(suggestion_id)
    if (
        db.get(JiraFeatureFamily, family_id) is None
        or db.get(JiraFeatureRoot, feature_root_id) is None
    ):
        raise LookupError("suggestion_not_found")
    _record_suggestion_decision(
        db,
        family_id=family_id,
        feature_root_id=feature_root_id,
        fingerprint=fingerprint,
        decision="rejected",
        reason=reason,
    )
    db.flush()
    return list_feature_family_suggestions(db)


def _record_suggestion_decision(
    db: Session,
    *,
    family_id: int,
    feature_root_id: int,
    fingerprint: str,
    decision: str,
    reason: str | None,
) -> None:
    existing = db.execute(
        select(JiraFeatureFamilySuggestionDecision).where(
            JiraFeatureFamilySuggestionDecision.family_id == family_id,
            JiraFeatureFamilySuggestionDecision.feature_root_id == feature_root_id,
            JiraFeatureFamilySuggestionDecision.suggestion_fingerprint == fingerprint,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            JiraFeatureFamilySuggestionDecision(
                family_id=family_id,
                feature_root_id=feature_root_id,
                suggestion_fingerprint=fingerprint,
                decision=decision,
                reason=reason,
            )
        )
    else:
        existing.decision = decision
        existing.reason = reason

