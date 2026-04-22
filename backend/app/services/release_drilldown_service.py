from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.services.cfr_bug_filter import cfr_eligible_production_bug_predicate


def _lane(major: int | None, minor: int | None, patch: int | None) -> str:
    if major is None or minor is None or patch is None:
        return "unknown"
    if patch > 0:
        return "patch"
    if minor > 0:
        return "minor"
    return "major"


@dataclass(frozen=True)
class CustomerReleaseRow:
    repository_id: int
    repository_path: str
    tag_name: str
    committed_at: datetime
    version_major: int | None
    version_minor: int | None
    version_patch: int | None
    mr_count: int
    lane: str


@dataclass(frozen=True)
class ReleaseMrRow:
    gitlab_mr_id: int
    title: str | None
    target_branch: str
    merged_at: datetime
    lead_time_hours: float | None
    release_wait_time_hours: float | None
    jira_key: str | None


@dataclass(frozen=True)
class FailedCustomerReleaseRow:
    repository_id: int
    repository_path: str
    tag_name: str
    committed_at: datetime
    version_major: int | None
    version_minor: int | None
    version_patch: int | None
    mr_count: int
    lane: str
    issue_count: int


@dataclass(frozen=True)
class CustomerReleaseBugRow:
    jira_key: str
    summary: str | None
    status: str | None
    priority: str | None
    healthmemo: str | None


@dataclass(frozen=True)
class MttrAlphaIncidentWindow:
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True)
class MttrAlphaPathCountRow:
    resolution_path: str
    count: int


@dataclass(frozen=True)
class MttrAlphaIncidentDetailRow:
    jira_key: str
    summary: str | None
    status: str | None
    priority: str | None
    healthmemo: str | None
    created_at: datetime | None
    first_fix_release_date: datetime | None
    first_fix_release_tag: str | None
    mttr_alpha_minutes: int | None
    mttr_alpha_resolution_path: str | None


@dataclass(frozen=True)
class MttrAlphaReleaseRow:
    first_fix_release_tag: str
    first_fix_release_date: datetime
    issue_count: int
    median_minutes: int | None


def _to_period_datetimes(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


def latest_mttr_alpha_incident_window(
    session: Session, *, period_type: str
) -> MttrAlphaIncidentWindow | None:
    row = session.execute(
        select(Release.committed_at)
        .where(Release.customer_release.is_(True))
        .order_by(Release.committed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    anchor = row.date()
    pt = period_type.upper()
    if pt == "WEEK":
        p_start = anchor - timedelta(days=anchor.weekday())
        p_end = p_start + timedelta(days=6)
    elif pt == "MONTH":
        p_start = date(anchor.year, anchor.month, 1)
        if anchor.month == 12:
            p_end = date(anchor.year + 1, 1, 1) - timedelta(days=1)
        else:
            p_end = date(anchor.year, anchor.month + 1, 1) - timedelta(days=1)
    elif pt == "QUARTER":
        q_month = ((anchor.month - 1) // 3) * 3 + 1
        p_start = date(anchor.year, q_month, 1)
        if q_month == 10:
            p_end = date(anchor.year + 1, 1, 1) - timedelta(days=1)
        else:
            p_end = date(anchor.year, q_month + 3, 1) - timedelta(days=1)
    else:
        raise ValueError(f"Unsupported period type: {period_type}")
    start_dt, end_dt = _to_period_datetimes(p_start, p_end)
    return MttrAlphaIncidentWindow(period_start=start_dt, period_end=end_dt)


def count_mttr_alpha_incidents_in_window(
    session: Session, *, period_start: datetime, period_end: datetime
) -> int:
    return int(
        session.execute(
            select(func.count(ProductionBug.id)).where(
                ProductionBug.healthy.is_(True),
                ProductionBug.jira_created_at_valid.is_(True),
                ProductionBug.first_fix_release_date.is_not(None),
                ProductionBug.first_fix_release_date >= period_start,
                ProductionBug.first_fix_release_date < period_end,
                ProductionBug.mttr_alpha_minutes.is_not(None),
            )
        ).scalar_one()
    )


def median_mttr_alpha_minutes_in_window(
    session: Session, *, period_start: datetime, period_end: datetime
) -> int | None:
    values = (
        session.execute(
            select(ProductionBug.mttr_alpha_minutes).where(
                ProductionBug.healthy.is_(True),
                ProductionBug.jira_created_at_valid.is_(True),
                ProductionBug.first_fix_release_date.is_not(None),
                ProductionBug.first_fix_release_date >= period_start,
                ProductionBug.first_fix_release_date < period_end,
                ProductionBug.mttr_alpha_minutes.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    xs = [int(v) for v in values if v is not None]
    if not xs:
        return None
    xs.sort()
    n = len(xs)
    mid = n // 2
    if n % 2 == 1:
        return xs[mid]
    return int(round((xs[mid - 1] + xs[mid]) / 2.0))


def list_mttr_alpha_resolution_path_counts(
    session: Session, *, period_start: datetime, period_end: datetime
) -> list[MttrAlphaPathCountRow]:
    rows = session.execute(
        select(
            func.coalesce(ProductionBug.mttr_alpha_resolution_path, "unknown").label("path"),
            func.count(ProductionBug.id).label("count"),
        )
        .where(
            ProductionBug.healthy.is_(True),
            ProductionBug.jira_created_at_valid.is_(True),
            ProductionBug.first_fix_release_date.is_not(None),
            ProductionBug.first_fix_release_date >= period_start,
            ProductionBug.first_fix_release_date < period_end,
            ProductionBug.mttr_alpha_minutes.is_not(None),
        )
        .group_by("path")
        .order_by(func.count(ProductionBug.id).desc(), "path")
    ).all()
    return [
        MttrAlphaPathCountRow(resolution_path=str(path), count=int(count))
        for path, count in rows
    ]


def list_mttr_alpha_incidents_page(
    session: Session,
    *,
    period_start: datetime,
    period_end: datetime,
    page: int,
    size: int,
    first_fix_release_tag: str | None = None,
) -> list[MttrAlphaIncidentDetailRow]:
    q = (
        select(ProductionBug)
        .where(
            ProductionBug.healthy.is_(True),
            ProductionBug.jira_created_at_valid.is_(True),
            ProductionBug.first_fix_release_date.is_not(None),
            ProductionBug.first_fix_release_date >= period_start,
            ProductionBug.first_fix_release_date < period_end,
            ProductionBug.mttr_alpha_minutes.is_not(None),
        )
        .order_by(ProductionBug.mttr_alpha_minutes.desc(), ProductionBug.jira_key.asc())
        .offset(page * size)
        .limit(size)
    )
    if first_fix_release_tag:
        q = q.where(ProductionBug.first_fix_release_tag == first_fix_release_tag)
    return [
        MttrAlphaIncidentDetailRow(
            jira_key=bug.jira_key,
            summary=bug.summary,
            status=bug.status,
            priority=bug.priority,
            healthmemo=bug.healthmemo,
            created_at=bug.created_at,
            first_fix_release_date=bug.first_fix_release_date,
            first_fix_release_tag=bug.first_fix_release_tag,
            mttr_alpha_minutes=bug.mttr_alpha_minutes,
            mttr_alpha_resolution_path=bug.mttr_alpha_resolution_path,
        )
        for bug in session.execute(q).scalars().all()
    ]


def count_mttr_alpha_incidents_for_release_tag(
    session: Session,
    *,
    period_start: datetime,
    period_end: datetime,
    first_fix_release_tag: str | None = None,
) -> int:
    q = select(func.count(ProductionBug.id)).where(
        ProductionBug.healthy.is_(True),
        ProductionBug.jira_created_at_valid.is_(True),
        ProductionBug.first_fix_release_date.is_not(None),
        ProductionBug.first_fix_release_date >= period_start,
        ProductionBug.first_fix_release_date < period_end,
        ProductionBug.mttr_alpha_minutes.is_not(None),
    )
    if first_fix_release_tag:
        q = q.where(ProductionBug.first_fix_release_tag == first_fix_release_tag)
    return int(session.execute(q).scalar_one())


def list_mttr_alpha_releases_page(
    session: Session,
    *,
    period_start: datetime,
    period_end: datetime,
    page: int,
    size: int,
) -> list[MttrAlphaReleaseRow]:
    rows = session.execute(
        select(
            ProductionBug.first_fix_release_tag,
            func.max(ProductionBug.first_fix_release_date).label("release_date"),
            func.count(ProductionBug.id).label("issue_count"),
        )
        .where(
            ProductionBug.healthy.is_(True),
            ProductionBug.jira_created_at_valid.is_(True),
            ProductionBug.first_fix_release_date.is_not(None),
            ProductionBug.first_fix_release_date >= period_start,
            ProductionBug.first_fix_release_date < period_end,
            ProductionBug.mttr_alpha_minutes.is_not(None),
            ProductionBug.first_fix_release_tag.is_not(None),
        )
        .group_by(ProductionBug.first_fix_release_tag)
        .order_by(func.max(ProductionBug.first_fix_release_date).desc())
        .offset(page * size)
        .limit(size)
    ).all()
    out: list[MttrAlphaReleaseRow] = []
    for tag, release_date, issue_count in rows:
        med_values = (
            session.execute(
                select(ProductionBug.mttr_alpha_minutes).where(
                    ProductionBug.healthy.is_(True),
                    ProductionBug.jira_created_at_valid.is_(True),
                    ProductionBug.first_fix_release_date.is_not(None),
                    ProductionBug.first_fix_release_date >= period_start,
                    ProductionBug.first_fix_release_date < period_end,
                    ProductionBug.mttr_alpha_minutes.is_not(None),
                    ProductionBug.first_fix_release_tag == tag,
                )
            )
            .scalars()
            .all()
        )
        xs = sorted(int(v) for v in med_values if v is not None)
        med: int | None = None
        if xs:
            n = len(xs)
            mid = n // 2
            med = xs[mid] if n % 2 == 1 else int(round((xs[mid - 1] + xs[mid]) / 2.0))
        out.append(
            MttrAlphaReleaseRow(
                first_fix_release_tag=str(tag),
                first_fix_release_date=release_date,
                issue_count=int(issue_count),
                median_minutes=med,
            )
        )
    return out


def count_customer_releases(session: Session, *, repository_id: int | None) -> int:
    q = (
        select(func.count(Release.id))
        .join(Repository, Repository.id == Release.repository_id)
        .where(Release.customer_release.is_(True), Repository.active.is_(True))
    )
    if repository_id is not None:
        q = q.where(Release.repository_id == repository_id)
    return int(session.execute(q).scalar_one())


def list_customer_releases_page(
    session: Session,
    *,
    repository_id: int | None,
    page: int,
    size: int,
) -> list[CustomerReleaseRow]:
    mr_group = (
        select(
            MergeRequest.repository_id.label("repo_id"),
            MergeRequest.first_customer_tag.label("tag"),
            func.count(MergeRequest.id).label("cnt"),
        )
        .where(MergeRequest.first_customer_tag.is_not(None))
        .group_by(MergeRequest.repository_id, MergeRequest.first_customer_tag)
        .subquery()
    )

    q = (
        select(
            Release,
            Repository.path,
            func.coalesce(mr_group.c.cnt, 0).label("mr_count"),
        )
        .join(Repository, Repository.id == Release.repository_id)
        .outerjoin(
            mr_group,
            and_(
                mr_group.c.repo_id == Release.repository_id,
                mr_group.c.tag == Release.tag_name,
            ),
        )
        .where(Release.customer_release.is_(True), Repository.active.is_(True))
        .order_by(Release.committed_at.desc())
        .offset(page * size)
        .limit(size)
    )
    if repository_id is not None:
        q = q.where(Release.repository_id == repository_id)

    rows: list[CustomerReleaseRow] = []
    for release, path, mr_count in session.execute(q).all():
        mc = int(mr_count or 0)
        rows.append(
            CustomerReleaseRow(
                repository_id=int(release.repository_id),
                repository_path=str(path),
                tag_name=release.tag_name,
                committed_at=release.committed_at,
                version_major=release.version_major,
                version_minor=release.version_minor,
                version_patch=release.version_patch,
                mr_count=mc,
                lane=_lane(
                    release.version_major,
                    release.version_minor,
                    release.version_patch,
                ),
            )
        )
    return rows


def find_previous_customer_release(
    session: Session, *, repository_id: int, committed_at: datetime
) -> Release | None:
    return session.execute(
        select(Release)
        .where(
            Release.repository_id == repository_id,
            Release.customer_release.is_(True),
            Release.committed_at < committed_at,
        )
        .order_by(Release.committed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def count_merge_requests_with_jira_key(
    session: Session, *, repository_id: int, tag_name: str
) -> int:
    return int(
        session.execute(
            select(func.count(MergeRequest.id)).where(
                MergeRequest.repository_id == repository_id,
                MergeRequest.first_customer_tag == tag_name,
                MergeRequest.jira_key.is_not(None),
                MergeRequest.jira_key != "",
            )
        ).scalar_one()
    )


def _gitlab_web_url_project_path(project_path: str) -> str:
    """GitLab compare/browse URLs use literal slashes between namespaces.

    Only encode characters per path segment.
    """
    parts = [p for p in project_path.strip().strip("/").split("/") if p]
    return "/".join(quote(part, safe="") for part in parts)


def build_gitlab_compare_url(
    *, base_url: str, project_path: str, from_tag: str, to_tag: str
) -> str:
    root = base_url.rstrip("/")
    path_part = _gitlab_web_url_project_path(project_path)
    return f"{root}/{path_part}/-/compare/{quote(from_tag, safe='')}...{quote(to_tag, safe='')}"


def get_customer_release_or_none(
    session: Session, *, repository_id: int, tag_name: str
) -> Release | None:
    return session.execute(
        select(Release)
        .join(Repository, Repository.id == Release.repository_id)
        .where(
            Release.repository_id == repository_id,
            Release.tag_name == tag_name,
            Release.customer_release.is_(True),
            Repository.active.is_(True),
        )
    ).scalar_one_or_none()


def count_merge_requests_for_release(
    session: Session, *, repository_id: int, tag_name: str
) -> int:
    return int(
        session.execute(
            select(func.count(MergeRequest.id)).where(
                MergeRequest.repository_id == repository_id,
                MergeRequest.first_customer_tag == tag_name,
            )
        ).scalar_one()
    )


def list_merge_requests_for_release_page(
    session: Session,
    *,
    repository_id: int,
    tag_name: str,
    page: int,
    size: int,
) -> list[ReleaseMrRow]:
    q = (
        select(MergeRequest)
        .where(
            MergeRequest.repository_id == repository_id,
            MergeRequest.first_customer_tag == tag_name,
        )
        .order_by(MergeRequest.merged_at.desc())
        .offset(page * size)
        .limit(size)
    )
    out: list[ReleaseMrRow] = []
    for mr in session.execute(q).scalars().all():
        lt = mr.lead_time_hours
        rw = mr.release_wait_time_hours
        out.append(
            ReleaseMrRow(
                gitlab_mr_id=int(mr.gitlab_mr_id),
                title=mr.title,
                target_branch=mr.target_branch,
                merged_at=mr.merged_at,
                lead_time_hours=float(lt) if lt is not None else None,
                release_wait_time_hours=float(rw) if rw is not None else None,
                jira_key=mr.jira_key,
            )
        )
    return out


def build_jira_browse_url(*, base_url: str, jira_key: str) -> str:
    root = base_url.rstrip("/")
    return f"{root}/browse/{quote(jira_key, safe='')}"


def count_failed_customer_releases(session: Session, *, repository_id: int | None) -> int:
    q = (
        select(func.count(func.distinct(Release.id)))
        .select_from(Release)
        .join(Repository, Repository.id == Release.repository_id)
        .join(BugRelease, BugRelease.release_id == Release.id)
        .join(ProductionBug, ProductionBug.id == BugRelease.bug_id)
        .where(
            Release.customer_release.is_(True),
            Repository.active.is_(True),
            cfr_eligible_production_bug_predicate(),
        )
    )
    if repository_id is not None:
        q = q.where(Release.repository_id == repository_id)
    return int(session.execute(q).scalar_one())


def list_failed_customer_releases_page(
    session: Session,
    *,
    repository_id: int | None,
    page: int,
    size: int,
) -> list[FailedCustomerReleaseRow]:
    issue_counts = (
        select(
            BugRelease.release_id.label("release_id"),
            func.count(func.distinct(ProductionBug.id)).label("issue_count"),
        )
        .join(ProductionBug, ProductionBug.id == BugRelease.bug_id)
        .where(cfr_eligible_production_bug_predicate())
        .group_by(BugRelease.release_id)
        .subquery()
    )
    mr_group = (
        select(
            MergeRequest.repository_id.label("repo_id"),
            MergeRequest.first_customer_tag.label("tag"),
            func.count(MergeRequest.id).label("cnt"),
        )
        .where(MergeRequest.first_customer_tag.is_not(None))
        .group_by(MergeRequest.repository_id, MergeRequest.first_customer_tag)
        .subquery()
    )
    q = (
        select(
            Release,
            Repository.path,
            func.coalesce(mr_group.c.cnt, 0).label("mr_count"),
            issue_counts.c.issue_count,
        )
        .join(Repository, Repository.id == Release.repository_id)
        .join(issue_counts, issue_counts.c.release_id == Release.id)
        .outerjoin(
            mr_group,
            and_(
                mr_group.c.repo_id == Release.repository_id,
                mr_group.c.tag == Release.tag_name,
            ),
        )
        .where(Release.customer_release.is_(True), Repository.active.is_(True))
        .order_by(Release.committed_at.desc())
        .offset(page * size)
        .limit(size)
    )
    if repository_id is not None:
        q = q.where(Release.repository_id == repository_id)

    rows: list[FailedCustomerReleaseRow] = []
    for release, path, mr_count, issue_count in session.execute(q).all():
        mc = int(mr_count or 0)
        ic = int(issue_count or 0)
        rows.append(
            FailedCustomerReleaseRow(
                repository_id=int(release.repository_id),
                repository_path=str(path),
                tag_name=release.tag_name,
                committed_at=release.committed_at,
                version_major=release.version_major,
                version_minor=release.version_minor,
                version_patch=release.version_patch,
                mr_count=mc,
                lane=_lane(
                    release.version_major,
                    release.version_minor,
                    release.version_patch,
                ),
                issue_count=ic,
            )
        )
    return rows


def count_production_bugs_for_customer_release(
    session: Session, *, repository_id: int, tag_name: str
) -> int:
    return int(
        session.execute(
            select(func.count(func.distinct(ProductionBug.id)))
            .select_from(BugRelease)
            .join(ProductionBug, ProductionBug.id == BugRelease.bug_id)
            .join(Release, Release.id == BugRelease.release_id)
            .where(
                Release.repository_id == repository_id,
                Release.tag_name == tag_name,
                Release.customer_release.is_(True),
                cfr_eligible_production_bug_predicate(),
            )
        ).scalar_one()
    )


def list_production_bugs_for_customer_release_page(
    session: Session,
    *,
    repository_id: int,
    tag_name: str,
    page: int,
    size: int,
) -> list[CustomerReleaseBugRow]:
    q = (
        select(ProductionBug)
        .join(BugRelease, BugRelease.bug_id == ProductionBug.id)
        .join(Release, Release.id == BugRelease.release_id)
        .where(
            Release.repository_id == repository_id,
            Release.tag_name == tag_name,
            Release.customer_release.is_(True),
            cfr_eligible_production_bug_predicate(),
        )
        .order_by(ProductionBug.jira_key.asc())
        .offset(page * size)
        .limit(size)
    )
    out: list[CustomerReleaseBugRow] = []
    for bug in session.execute(q).scalars().all():
        out.append(
            CustomerReleaseBugRow(
                jira_key=bug.jira_key,
                summary=bug.summary,
                status=bug.status,
                priority=bug.priority,
                healthmemo=bug.healthmemo,
            )
        )
    return out
