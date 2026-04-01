from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from time import sleep
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config_schema import ConfigurationSchema
from app.models.merge_request import MergeRequest
from app.models.release import Release
from app.models.repository import Repository
from app.models.sync_log import SyncLog

_DEFAULT_MARKERS = ["rc", "beta"]
_DEFAULT_TARGET_BRANCHES = ["master", "9.x", "10.x", "11.x"]
_JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_VERSION_RE = re.compile(
    r"^[vV]?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass(slots=True)
class ParsedVersion:
    major: int | None
    minor: int | None
    patch: int | None
    pre_release: str | None


def parse_tag_version(tag_name: str | None) -> ParsedVersion:
    if not tag_name:
        return ParsedVersion(None, None, None, None)
    match = _VERSION_RE.match(tag_name.strip())
    if not match:
        return ParsedVersion(None, None, None, None)
    return ParsedVersion(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        pre_release=match.group("pre"),
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)  # noqa: UP017
    return parsed


def _hours_between(start: datetime, end: datetime) -> Decimal:
    hours = (end - start).total_seconds() / 3600.0
    return Decimal(str(hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _is_retryable_http_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


def _markers_regex(markers: list[str]) -> re.Pattern[str]:
    escaped = [re.escape(marker) for marker in markers if marker]
    joined = "|".join(escaped) if escaped else "rc|beta"
    return re.compile(rf"-(?:{joined})(?:[.\d]|$)", re.IGNORECASE)


def _is_customer_release(tag_name: str | None, marker_re: re.Pattern[str]) -> bool:
    if not tag_name or not tag_name.strip():
        return False
    return marker_re.search(tag_name) is None


def _merged_gitlab_settings(
    defaults: ConfigurationSchema,
) -> tuple[list[str], list[str], list[str]]:
    project_paths = list(defaults.gitlab.project_paths)
    target_branches = [branch.strip() for branch in defaults.gitlab.target_branches if branch.strip()]
    markers = [m.strip().lower() for m in defaults.gitlab.non_customer_release_markers if m.strip()]

    if not markers:
        markers = list(_DEFAULT_MARKERS)
    if not target_branches:
        target_branches = list(_DEFAULT_TARGET_BRANCHES)
    return project_paths, target_branches, markers


def _extract_jira_key(
    title: str | None,
    source_branch: str | None,
    description: str | None,
) -> tuple[str | None, str | None]:
    for text, source in (
        (title, "title"),
        (source_branch, "branch"),
        (description, "description"),
    ):
        if text:
            match = _JIRA_KEY_RE.search(text)
            if match:
                return match.group(1), source
    return None, None


def _effective_commit_sha(
    merge_commit_sha: str | None,
    squash_commit_sha: str | None,
) -> str | None:
    return (merge_commit_sha or squash_commit_sha or "").strip() or None


def _parse_merge_request(raw: dict[str, Any]) -> dict[str, Any] | None:
    merged_at = _parse_dt(str(raw.get("merged_at") or ""))
    created_at = _parse_dt(str(raw.get("created_at") or ""))
    target_branch = str(raw.get("target_branch") or "").strip()
    mr_id = raw.get("iid") or raw.get("id")
    if not isinstance(mr_id, int) or merged_at is None or created_at is None or not target_branch:
        return None

    title = str(raw.get("title") or "").strip() or None
    description = str(raw.get("description") or "").strip() or None
    source_branch = str(raw.get("source_branch") or "").strip() or None
    author_payload = raw.get("author")
    author = None
    if isinstance(author_payload, dict):
        author = str(author_payload.get("username") or "").strip() or None
    head_sha = str(raw.get("sha") or "").strip() or None
    merge_commit_sha = str(raw.get("merge_commit_sha") or "").strip() or None
    squash_commit_sha = str(raw.get("squash_commit_sha") or "").strip() or None
    jira_key, jira_key_source = _extract_jira_key(title, source_branch, description)

    return {
        "gitlab_mr_id": mr_id,
        "title": title,
        "description": description,
        "author": author,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "created_at": created_at,
        "merged_at": merged_at,
        "head_sha": head_sha,
        "merge_commit_sha": merge_commit_sha,
        "squash_commit_sha": squash_commit_sha,
        "effective_commit_sha": _effective_commit_sha(merge_commit_sha, squash_commit_sha),
        "jira_key": jira_key,
        "jira_key_source": jira_key_source,
    }


def _lookback_from(days: int) -> datetime:
    lookback_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    return datetime(
        lookback_date.year,
        lookback_date.month,
        lookback_date.day,
        tzinfo=timezone.utc,
    )


def _deduplicate_merge_requests(
    merge_requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for merge_request in merge_requests:
        mr_id = merge_request.get("gitlab_mr_id")
        if isinstance(mr_id, int):
            by_id[mr_id] = merge_request
    return sorted(by_id.values(), key=lambda item: item["merged_at"], reverse=True)


class GitLabTagsClient:
    def __init__(self, base_url: str, token: str, timeout_seconds: float = 30.0) -> None:
        self.api_root = f"{base_url.rstrip('/')}/api/v4"
        self.client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"PRIVATE-TOKEN": token},
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> GitLabTagsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retryable_http_exception),
        reraise=True,
    )
    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(url, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if _is_retryable_http_exception(exc):
                raise
            raise RuntimeError(
                f"GitLab API request failed: {exc.response.status_code} {url}"
            ) from exc
        return response.json()

    def get_project(self, project_path: str) -> dict[str, Any]:
        encoded = quote(project_path.strip(), safe="")
        payload = self._get_json(f"{self.api_root}/projects/{encoded}")
        if not isinstance(payload, dict):
            raise TypeError(f"Unexpected GitLab project response for {project_path}")
        return payload

    def list_tags(self, project_path: str, per_page: int = 100) -> list[dict[str, Any]]:
        encoded = quote(project_path.strip(), safe="")
        url = f"{self.api_root}/projects/{encoded}/repository/tags"
        page = 1
        tags: list[dict[str, Any]] = []

        while True:
            payload = self._get_json(url, params={"page": page, "per_page": per_page})
            if not isinstance(payload, list):
                raise TypeError(f"Unexpected tags response for {project_path}")
            tags.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < per_page:
                break
            page += 1
        return tags

    def list_merged_merge_requests(
        self,
        project_path: str,
        *,
        target_branch: str,
        lookback_days: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        encoded = quote(project_path.strip(), safe="")
        url = f"{self.api_root}/projects/{encoded}/merge_requests"
        page = 1
        merge_requests: list[dict[str, Any]] = []
        lookback_start = _lookback_from(lookback_days)

        while True:
            payload = self._get_json(
                url,
                params={
                    "state": "merged",
                    "order_by": "updated_at",
                    "sort": "desc",
                    "target_branch": target_branch,
                    "updated_after": lookback_start.isoformat(),
                    "page": page,
                    "per_page": per_page,
                },
            )
            if not isinstance(payload, list):
                raise TypeError(f"Unexpected merge request response for {project_path}")

            for item in payload:
                if not isinstance(item, dict):
                    continue
                parsed = _parse_merge_request(item)
                if parsed is None:
                    continue
                if parsed["merged_at"] >= lookback_start:
                    merge_requests.append(parsed)

            if len(payload) < per_page:
                break
            page += 1

        return merge_requests

    def list_merge_request_commits(
        self,
        project_path: str,
        *,
        merge_request_iid: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        encoded = quote(project_path.strip(), safe="")
        url = f"{self.api_root}/projects/{encoded}/merge_requests/{merge_request_iid}/commits"
        page = 1
        commits: list[dict[str, Any]] = []
        while True:
            payload = self._get_json(url, params={"page": page, "per_page": per_page})
            if not isinstance(payload, list):
                raise TypeError(
                    f"Unexpected MR commits response for {project_path}#{merge_request_iid}"
                )
            commits.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < per_page:
                break
            page += 1
        return commits

    def list_commit_tag_refs(
        self,
        project_path: str,
        *,
        commit_sha: str,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        encoded = quote(project_path.strip(), safe="")
        encoded_sha = quote(commit_sha.strip(), safe="")
        url = f"{self.api_root}/projects/{encoded}/repository/commits/{encoded_sha}/refs"
        page = 1
        refs: list[dict[str, Any]] = []
        while True:
            payload = self._get_json(
                url, params={"type": "tag", "page": page, "per_page": per_page}
            )
            if not isinstance(payload, list):
                raise TypeError(
                    f"Unexpected commit refs response for {project_path}#{commit_sha}"
                )
            refs.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < per_page:
                break
            page += 1
        return refs


def _upsert_repository(db: Session, project_path: str, project: dict[str, Any]) -> Repository:
    gitlab_id = int(project["id"])
    repository = db.execute(
        select(Repository).where(Repository.gitlab_id == gitlab_id)
    ).scalar_one_or_none()
    if repository is None:
        repository = Repository(
            id=gitlab_id,
            gitlab_id=gitlab_id,
            name=str(project.get("name") or project_path.split("/")[-1]),
            path=str(project.get("path_with_namespace") or project_path),
            default_branch=str(project.get("default_branch") or "master"),
            active=True,
        )
        db.add(repository)
        db.flush()
        return repository

    repository.name = str(project.get("name") or repository.name)
    repository.path = str(project.get("path_with_namespace") or repository.path)
    repository.default_branch = str(project.get("default_branch") or repository.default_branch)
    repository.active = True
    db.flush()
    return repository


def _upsert_release(
    db: Session,
    repository_id: int,
    tag_name: str,
    customer_release: bool,
    commit_sha: str,
    committed_at: datetime,
) -> None:
    parsed = parse_tag_version(tag_name)
    release = db.execute(
        select(Release).where(Release.repository_id == repository_id, Release.tag_name == tag_name)
    ).scalar_one_or_none()
    if release is None:
        db.add(
            Release(
                repository_id=repository_id,
                tag_name=tag_name,
                version_major=parsed.major,
                version_minor=parsed.minor,
                version_patch=parsed.patch,
                pre_release=parsed.pre_release,
                customer_release=customer_release,
                commit_sha=commit_sha,
                committed_at=committed_at,
            )
        )
        return

    release.version_major = parsed.major
    release.version_minor = parsed.minor
    release.version_patch = parsed.patch
    release.pre_release = parsed.pre_release
    release.customer_release = customer_release
    release.commit_sha = commit_sha
    release.committed_at = committed_at


def _reconcile_repository_releases(
    db: Session,
    *,
    repository_id: int,
    seen_tag_names: set[str],
) -> int:
    if seen_tag_names:
        existing_tags = set(
            db.execute(select(Release.tag_name).where(Release.repository_id == repository_id)).scalars().all()
        )
        stale_tags = existing_tags - seen_tag_names
        if not stale_tags:
            return 0
        result = db.execute(
            delete(Release).where(
                Release.repository_id == repository_id,
                Release.tag_name.in_(stale_tags),
            )
        )
        return int(result.rowcount or 0)
    result = db.execute(delete(Release).where(Release.repository_id == repository_id))
    return int(result.rowcount or 0)


def _upsert_merge_request(
    db: Session,
    repository_id: int,
    payload: dict[str, Any],
) -> None:
    merge_request = db.execute(
        select(MergeRequest).where(
            MergeRequest.repository_id == repository_id,
            MergeRequest.gitlab_mr_id == payload["gitlab_mr_id"],
        )
    ).scalar_one_or_none()

    if merge_request is None:
        db.add(
            MergeRequest(
                repository_id=repository_id,
                gitlab_mr_id=payload["gitlab_mr_id"],
                title=payload["title"],
                description=payload["description"],
                author=payload["author"],
                source_branch=payload["source_branch"],
                target_branch=payload["target_branch"],
                created_at=payload["created_at"],
                merged_at=payload["merged_at"],
                head_sha=payload["head_sha"],
                merge_commit_sha=payload["merge_commit_sha"],
                squash_commit_sha=payload["squash_commit_sha"],
                effective_commit_sha=payload["effective_commit_sha"],
                jira_key=payload["jira_key"],
                jira_key_source=payload["jira_key_source"],
            )
        )
        return

    merge_request.title = payload["title"]
    merge_request.description = payload["description"]
    merge_request.author = payload["author"]
    merge_request.source_branch = payload["source_branch"]
    merge_request.target_branch = payload["target_branch"]
    merge_request.created_at = payload["created_at"]
    merge_request.merged_at = payload["merged_at"]
    merge_request.head_sha = payload["head_sha"]
    merge_request.merge_commit_sha = payload["merge_commit_sha"]
    merge_request.squash_commit_sha = payload["squash_commit_sha"]
    merge_request.effective_commit_sha = payload["effective_commit_sha"]
    merge_request.jira_key = payload["jira_key"]
    merge_request.jira_key_source = payload["jira_key_source"]


def _apply_cooldown(seconds: float) -> None:
    if seconds > 0:
        sleep(seconds)


def _sync_first_commit_timestamps(
    db: Session,
    gitlab: GitLabTagsClient,
    *,
    repository: Repository,
    project_path: str,
    cooldown_seconds: float,
    per_page: int,
    lookback_days: int,
) -> int:
    updated = 0
    lookback_start = _lookback_from(lookback_days)
    merge_requests = db.execute(
        select(MergeRequest).where(
            MergeRequest.repository_id == repository.id,
            or_(
                MergeRequest.first_commit_at.is_(None),
                MergeRequest.updated_at >= lookback_start,
                MergeRequest.merged_at >= lookback_start,
            ),
        )
    ).scalars()
    for merge_request in merge_requests:
        commits = gitlab.list_merge_request_commits(
            project_path,
            merge_request_iid=int(merge_request.gitlab_mr_id),
            per_page=per_page,
        )
        committed_dates = [
            parsed
            for parsed in (_parse_dt(str(item.get("committed_date") or "")) for item in commits)
            if parsed is not None
        ]
        if committed_dates:
            merge_request.first_commit_at = min(committed_dates)
            updated += 1
        _apply_cooldown(cooldown_seconds)
    return updated


def _map_merge_requests_to_customer_releases(
    db: Session,
    gitlab: GitLabTagsClient,
    *,
    repository: Repository,
    project_path: str,
    cooldown_seconds: float,
    per_page: int,
) -> int:
    mapped = 0
    releases = db.execute(
        select(Release).where(
            Release.repository_id == repository.id,
            Release.customer_release.is_(True),
        )
    ).scalars()
    releases_by_tag = {release.tag_name: release for release in releases}
    merge_requests = db.execute(
        select(MergeRequest).where(MergeRequest.repository_id == repository.id)
    ).scalars()

    for merge_request in merge_requests:
        merge_request.first_customer_tag = None
        merge_request.first_customer_tag_date = None
        merge_request.release_wait_time_hours = None
        merge_request.lead_time_hours = None
        if not merge_request.effective_commit_sha:
            merge_request.lead_time_match_status = "no_effective_commit_sha"
            continue

        refs = gitlab.list_commit_tag_refs(
            project_path,
            commit_sha=merge_request.effective_commit_sha,
            per_page=per_page,
        )
        _apply_cooldown(cooldown_seconds)
        if not refs:
            merge_request.lead_time_match_status = "no_tag_ref_found"
            continue

        matching_releases: list[Release] = []
        for ref in refs:
            ref_type = str(ref.get("type") or "").strip()
            if ref_type and ref_type != "tag":
                continue
            tag_name = str(ref.get("name") or "").strip()
            if not tag_name:
                continue
            release = releases_by_tag.get(tag_name)
            if release is not None and release.committed_at is not None:
                matching_releases.append(release)

        if not matching_releases:
            merge_request.lead_time_match_status = "no_customer_tag_ref_found"
            continue

        eligible_releases = [
            release for release in matching_releases if release.committed_at >= merge_request.merged_at
        ]
        if not eligible_releases:
            merge_request.lead_time_match_status = "no_customer_tag_after_merge"
            continue

        first_release = min(eligible_releases, key=lambda rel: rel.committed_at)
        merge_request.first_customer_tag = first_release.tag_name
        merge_request.first_customer_tag_date = first_release.committed_at
        merge_request.release_wait_time_hours = _hours_between(
            merge_request.merged_at, first_release.committed_at
        )
        if merge_request.first_commit_at is not None:
            merge_request.lead_time_hours = _hours_between(
                merge_request.first_commit_at, first_release.committed_at
            )
            merge_request.lead_time_match_status = "matched"
        else:
            merge_request.lead_time_hours = None
            merge_request.lead_time_match_status = "first_commit_missing"
        mapped += 1
    return mapped


def collect_gitlab_tags_and_releases(
    db: Session,
    *,
    config: ConfigurationSchema,
    gitlab_token: str,
    per_page: int = 100,
    mr_mapping_cooldown_seconds: float = 0.05,
) -> int:
    started_at = datetime.now(timezone.utc)  # noqa: UP017
    sync_log = SyncLog(source="gitlab", started_at=started_at, status="running")
    db.add(sync_log)
    db.flush()

    project_paths, target_branches, markers = _merged_gitlab_settings(config)
    marker_re = _markers_regex(markers)
    processed = 0

    try:
        with GitLabTagsClient(base_url=config.gitlab.base_url, token=gitlab_token) as gitlab:
            for project_path in project_paths:
                project = gitlab.get_project(project_path)
                repository = _upsert_repository(db, project_path, project)
                seen_release_tags: set[str] = set()
                for tag in gitlab.list_tags(project_path=project_path, per_page=per_page):
                    tag_name = tag.get("name")
                    raw_commit = tag.get("commit")
                    commit = raw_commit if isinstance(raw_commit, dict) else {}
                    commit_sha = str(commit.get("id") or "").strip()
                    committed_at = _parse_dt(commit.get("committed_date"))
                    if not isinstance(tag_name, str) or not commit_sha or committed_at is None:
                        continue
                    seen_release_tags.add(tag_name)
                    _upsert_release(
                        db,
                        repository_id=repository.id,
                        tag_name=tag_name,
                        customer_release=_is_customer_release(tag_name, marker_re),
                        commit_sha=commit_sha,
                        committed_at=committed_at,
                    )
                    processed += 1
                processed += _reconcile_repository_releases(
                    db,
                    repository_id=repository.id,
                    seen_tag_names=seen_release_tags,
                )

                merge_requests: list[dict[str, Any]] = []
                for target_branch in target_branches:
                    merge_requests.extend(
                        gitlab.list_merged_merge_requests(
                            project_path=project_path,
                            target_branch=target_branch,
                            lookback_days=config.backend.lookback_days,
                            per_page=per_page,
                        )
                    )

                for merge_request in _deduplicate_merge_requests(merge_requests):
                    _upsert_merge_request(db, repository_id=repository.id, payload=merge_request)
                    processed += 1

                processed += _sync_first_commit_timestamps(
                    db,
                    gitlab,
                    repository=repository,
                    project_path=project_path,
                    cooldown_seconds=mr_mapping_cooldown_seconds,
                    per_page=per_page,
                    lookback_days=config.backend.lookback_days,
                )
                processed += _map_merge_requests_to_customer_releases(
                    db,
                    gitlab,
                    repository=repository,
                    project_path=project_path,
                    cooldown_seconds=mr_mapping_cooldown_seconds,
                    per_page=per_page,
                )

        sync_log.status = "success"
        sync_log.finished_at = datetime.now(timezone.utc)  # noqa: UP017
        sync_log.records_processed = processed
        db.commit()
        return processed
    except Exception as exc:
        db.rollback()
        sync_log.status = "failed"
        sync_log.finished_at = datetime.now(timezone.utc)  # noqa: UP017
        sync_log.error_message = str(exc)[:4000]
        db.add(sync_log)
        db.commit()
        raise
