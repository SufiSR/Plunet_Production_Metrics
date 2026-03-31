from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config_schema import ConfigurationSchema
from app.models.app_configuration import AppConfiguration
from app.models.release import Release
from app.models.repository import Repository
from app.models.sync_log import SyncLog

_DEFAULT_MARKERS = ["rc", "beta"]
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
    db: Session,
    defaults: ConfigurationSchema,
) -> tuple[list[str], list[str]]:
    project_paths = list(defaults.gitlab.project_paths)
    markers = [m.strip().lower() for m in defaults.gitlab.non_customer_release_markers if m.strip()]

    app_config = db.get(AppConfiguration, 1)
    if app_config and isinstance(app_config.settings_json, dict):
        settings = app_config.settings_json
        configured_paths = settings.get("gitlab_project_paths")
        if isinstance(configured_paths, list):
            project_paths = [str(path).strip() for path in configured_paths if str(path).strip()]
        gitlab_settings = settings.get("gitlab")
        if isinstance(gitlab_settings, dict):
            nested_paths = gitlab_settings.get("project_paths")
            if isinstance(nested_paths, list):
                project_paths = [str(path).strip() for path in nested_paths if str(path).strip()]
            configured_markers = gitlab_settings.get("non_customer_release_markers")
            if isinstance(configured_markers, list):
                markers = [
                    str(marker).strip().lower()
                    for marker in configured_markers
                    if str(marker).strip()
                ]

    if not markers:
        markers = list(_DEFAULT_MARKERS)
    return project_paths, markers


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


def collect_gitlab_tags_and_releases(
    db: Session,
    *,
    config: ConfigurationSchema,
    gitlab_token: str,
    per_page: int = 100,
) -> int:
    started_at = datetime.now(timezone.utc)  # noqa: UP017
    sync_log = SyncLog(source="gitlab", started_at=started_at, status="running")
    db.add(sync_log)
    db.flush()

    project_paths, markers = _merged_gitlab_settings(db, config)
    marker_re = _markers_regex(markers)
    processed = 0

    try:
        with GitLabTagsClient(base_url=config.gitlab.base_url, token=gitlab_token) as gitlab:
            for project_path in project_paths:
                project = gitlab.get_project(project_path)
                repository = _upsert_repository(db, project_path, project)
                for tag in gitlab.list_tags(project_path=project_path, per_page=per_page):
                    tag_name = tag.get("name")
                    raw_commit = tag.get("commit")
                    commit = raw_commit if isinstance(raw_commit, dict) else {}
                    commit_sha = str(commit.get("id") or "").strip()
                    committed_at = _parse_dt(commit.get("committed_date"))
                    if not isinstance(tag_name, str) or not commit_sha or committed_at is None:
                        continue
                    _upsert_release(
                        db,
                        repository_id=repository.id,
                        tag_name=tag_name,
                        customer_release=_is_customer_release(tag_name, marker_re),
                        commit_sha=commit_sha,
                        committed_at=committed_at,
                    )
                    processed += 1

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
