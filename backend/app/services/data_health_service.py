from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.schemas.data_health import (
    DataHealthResponse,
    DataHealthSummary,
    JiraHealthBreakdownRow,
    UnmatchedMergeRequestRow,
    VersionMismatchRow,
)
from app.schemas.releases import OffsetPagination


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


def _normalize_version_key(value: str) -> set[str]:
    normalized = value.strip().lower()
    if not normalized:
        return set()
    candidates = {normalized}
    if normalized.startswith("v"):
        without_v = normalized[1:]
        if without_v:
            candidates.add(without_v)
    else:
        candidates.add(f"v{normalized}")
    return candidates


def _gitlab_web_url_project_path(project_path: str) -> str:
    parts = [p for p in project_path.strip().strip("/").split("/") if p]
    return "/".join(quote(part, safe="") for part in parts)


def _build_gitlab_mr_url(*, base_url: str, project_path: str, gitlab_mr_id: int) -> str:
    root = base_url.rstrip("/")
    path_part = _gitlab_web_url_project_path(project_path)
    return f"{root}/{path_part}/-/merge_requests/{gitlab_mr_id}"


def _build_jira_browse_url(*, base_url: str, jira_key: str) -> str:
    return f"{base_url.rstrip('/')}/browse/{quote(jira_key, safe='')}"


@dataclass(frozen=True)
class DataHealthBundle:
    response: DataHealthResponse


def _count_total_bugs(db: Session) -> int:
    return int(db.execute(select(func.count(ProductionBug.id))).scalar_one())


def _is_ignored_healthmemo(healthmemo: str | None) -> bool:
    return str(healthmemo or "").strip().lower() == "ignored"


def _count_healthy_bugs(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(ProductionBug.id)).where(
                or_(
                    ProductionBug.healthy.is_(True),
                    func.lower(func.trim(ProductionBug.healthmemo)) == "ignored",
                )
            )
        ).scalar_one()
    )


def _list_jira_health_breakdown(db: Session, *, total_bugs: int) -> list[JiraHealthBreakdownRow]:
    rows = db.execute(
        select(
            ProductionBug.healthy,
            ProductionBug.healthmemo,
            func.count(ProductionBug.id).label("count"),
        )
        .group_by(ProductionBug.healthy, ProductionBug.healthmemo)
        .order_by(ProductionBug.healthy.desc(), func.count(ProductionBug.id).desc())
    ).all()
    if total_bugs <= 0:
        return []
    return [
        JiraHealthBreakdownRow(
            healthy=bool(healthy) or _is_ignored_healthmemo(healthmemo),
            healthmemo=healthmemo,
            count=int(count),
            share_pct=round((int(count) / total_bugs) * 100.0, 2),
        )
        for healthy, healthmemo, count in rows
    ]


def _mr_unmatched_reason(mr: MergeRequest) -> str | None:
    if not mr.first_customer_tag:
        return "no_customer_release_tag"
    if not mr.jira_key:
        return "missing_jira_key"
    if mr.lead_time_match_status and mr.lead_time_match_status != "matched":
        return f"lead_time_{mr.lead_time_match_status}"
    return None


def _count_unmatched_merge_requests(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(MergeRequest.id)).where(
                MergeRequest.first_customer_tag.is_(None),
                MergeRequest.merged_at.is_not(None),
            )
        ).scalar_one()
    ) + int(
        db.execute(
            select(func.count(MergeRequest.id)).where(
                MergeRequest.first_customer_tag.is_not(None),
                MergeRequest.merged_at.is_not(None),
                (
                    MergeRequest.jira_key.is_(None)
                    | (MergeRequest.jira_key == "")
                    | (
                        MergeRequest.lead_time_match_status.is_not(None)
                        & (MergeRequest.lead_time_match_status != "matched")
                    )
                ),
            )
        ).scalar_one()
    )


def _list_unmatched_merge_requests(
    db: Session,
    *,
    page: int,
    size: int,
    jira_base_url: str,
    gitlab_base_url: str,
) -> list[UnmatchedMergeRequestRow]:
    rows = db.execute(
        select(MergeRequest, Repository.path)
        .join(Repository, Repository.id == MergeRequest.repository_id)
        .where(MergeRequest.merged_at.is_not(None))
        .order_by(MergeRequest.merged_at.desc())
        .offset(page * size)
        .limit(size * 5)
    ).all()

    items: list[UnmatchedMergeRequestRow] = []
    for mr, repo_path in rows:
        reason = _mr_unmatched_reason(mr)
        if reason is None:
            continue
        jira_url = (
            _build_jira_browse_url(base_url=jira_base_url, jira_key=mr.jira_key)
            if jira_base_url and mr.jira_key
            else None
        )
        gitlab_url = (
            _build_gitlab_mr_url(
                base_url=gitlab_base_url,
                project_path=str(repo_path),
                gitlab_mr_id=int(mr.gitlab_mr_id),
            )
            if gitlab_base_url and repo_path
            else None
        )
        items.append(
            UnmatchedMergeRequestRow(
                repository_id=int(mr.repository_id),
                repository_path=str(repo_path),
                gitlab_mr_id=int(mr.gitlab_mr_id),
                title=mr.title,
                merged_at=mr.merged_at,
                jira_key=mr.jira_key,
                reason=reason,
                gitlab_merge_request_url=gitlab_url,
                jira_browse_url=jira_url,
            )
        )
        if len(items) >= size:
            break
    return items


def _count_version_mismatches(db: Session) -> int:
    release_rows = db.execute(select(Release.tag_name)).all()
    release_keys: set[str] = set()
    for (tag_name,) in release_rows:
        if tag_name:
            release_keys.update(_normalize_version_key(str(tag_name)))

    count = 0
    for bug in db.execute(select(ProductionBug)).scalars():
        versions = [v for v in (bug.affects_versions or []) if v] + [v for v in (bug.fix_versions or []) if v]
        if not versions:
            continue
        unmatched = []
        for version in versions:
            normalized = _normalize_version_key(str(version))
            if normalized and not (normalized & release_keys):
                unmatched.append(str(version))
        if unmatched:
            count += 1
    return count


def _list_version_mismatches(
    db: Session,
    *,
    page: int,
    size: int,
    jira_base_url: str,
) -> list[VersionMismatchRow]:
    release_rows = db.execute(select(Release.tag_name)).all()
    release_keys: set[str] = set()
    for (tag_name,) in release_rows:
        if tag_name:
            release_keys.update(_normalize_version_key(str(tag_name)))

    bugs = db.execute(select(ProductionBug).order_by(ProductionBug.created_at.desc().nullslast())).scalars().all()
    start = page * size
    end = start + size

    mismatches: list[VersionMismatchRow] = []
    for bug in bugs:
        affects_versions = [str(v) for v in (bug.affects_versions or []) if v]
        fix_versions = [str(v) for v in (bug.fix_versions or []) if v]
        versions = affects_versions + fix_versions
        if not versions:
            continue
        unmatched_versions: list[str] = []
        for version in versions:
            normalized = _normalize_version_key(version)
            if normalized and not (normalized & release_keys):
                unmatched_versions.append(version)
        if not unmatched_versions:
            continue
        mismatches.append(
            VersionMismatchRow(
                jira_key=bug.jira_key,
                summary=bug.summary,
                last_updated_at=bug.updated_at,
                healthmemo=bug.healthmemo,
                affects_versions=affects_versions,
                fix_versions=fix_versions,
                unmatched_versions=unmatched_versions,
                reason="jira_versions_not_found_in_release_tags",
                jira_browse_url=(
                    _build_jira_browse_url(base_url=jira_base_url, jira_key=bug.jira_key)
                    if jira_base_url
                    else None
                ),
            )
        )
    mismatches.sort(
        key=lambda row: (
            row.last_updated_at is not None,
            row.last_updated_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return mismatches[start:end]


def build_data_health_response(
    db: Session,
    *,
    unmatched_page: int,
    unmatched_size: int,
    mismatch_page: int,
    mismatch_size: int,
    jira_base_url: str,
    gitlab_base_url: str,
) -> DataHealthResponse:
    total_bugs = _count_total_bugs(db)
    healthy_bugs = _count_healthy_bugs(db)
    healthy_pct = round((healthy_bugs / total_bugs) * 100.0, 2) if total_bugs > 0 else 0.0

    unmatched_total = _count_unmatched_merge_requests(db)
    mismatches_total = _count_version_mismatches(db)

    jira_breakdown = _list_jira_health_breakdown(db, total_bugs=total_bugs)
    unmatched_rows = _list_unmatched_merge_requests(
        db,
        page=unmatched_page,
        size=unmatched_size,
        jira_base_url=jira_base_url.strip(),
        gitlab_base_url=gitlab_base_url.strip(),
    )
    mismatch_rows = _list_version_mismatches(
        db,
        page=mismatch_page,
        size=mismatch_size,
        jira_base_url=jira_base_url.strip(),
    )

    return DataHealthResponse(
        generated_at=datetime.now(timezone.utc),
        summary=DataHealthSummary(
            total_bugs=total_bugs,
            healthy_bugs=healthy_bugs,
            healthy_bugs_pct=healthy_pct,
            unmatched_mr_count=unmatched_total,
            version_mismatch_count=mismatches_total,
        ),
        jira_health_breakdown=jira_breakdown,
        unmatched_merge_requests=unmatched_rows,
        unmatched_merge_requests_pagination=_offset_pagination(
            page=unmatched_page,
            size=unmatched_size,
            total=unmatched_total,
        ),
        version_mismatches=mismatch_rows,
        version_mismatches_pagination=_offset_pagination(
            page=mismatch_page,
            size=mismatch_size,
            total=mismatches_total,
        ),
    )
