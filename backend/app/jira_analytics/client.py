from __future__ import annotations

import logging
from time import sleep
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def is_retryable_http_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


class JiraAnalyticsClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        user_email: str | None = None,
        timeout_seconds: float = 30.0,
        page_cooldown_seconds: float = 0.0,
        per_issue_cooldown_seconds: float = 0.05,
    ) -> None:
        self.api_root = f"{base_url.rstrip('/')}/rest/api/3"
        self.page_cooldown_seconds = max(page_cooldown_seconds, 0.0)
        self.per_issue_cooldown_seconds = max(per_issue_cooldown_seconds, 0.0)
        email = (user_email or "").strip()
        headers: dict[str, str] = {"Accept": "application/json"}
        auth: httpx.Auth | None = None
        if email:
            auth = httpx.BasicAuth(email, token)
        else:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers=headers,
            auth=auth,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> JiraAnalyticsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _cooldown(self, seconds: float) -> None:
        if seconds > 0:
            sleep(seconds)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(is_retryable_http_exception),
        reraise=True,
    )
    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(url, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if is_retryable_http_exception(exc):
                raise
            raise RuntimeError(
                f"Jira API request failed: {exc.response.status_code} {url}"
            ) from exc
        return response.json()

    def search_issues(
        self,
        *,
        jql: str,
        fields: list[str],
        max_results: int = 100,
        expand: str | None = "names,schema",
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        next_page_token: str | None = None
        page_num = 0
        while True:
            page_num += 1
            params: dict[str, Any] = {
                "jql": jql,
                "fields": ",".join(fields),
                "maxResults": max_results,
            }
            if expand:
                params["expand"] = expand
            if next_page_token:
                params["nextPageToken"] = next_page_token
            logger.info("jira analytics search: fetching page %s", page_num)
            payload = self._get_json(f"{self.api_root}/search/jql", params=params)
            page_issues = payload.get("issues")
            if isinstance(page_issues, list):
                issues.extend(item for item in page_issues if isinstance(item, dict))
            next_page_token = str(payload.get("nextPageToken") or "").strip() or None
            logger.info(
                "jira analytics search: page %s complete (total=%s has_next=%s)",
                page_num,
                len(issues),
                bool(next_page_token),
            )
            self._cooldown(self.page_cooldown_seconds)
            if next_page_token is None:
                break
        return issues

    def get_issue(
        self,
        issue_key: str,
        *,
        fields: list[str],
        expand: str | None = "names,schema",
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {"fields": ",".join(fields)}
        if expand:
            params["expand"] = expand
        payload = self._get_json(
            f"{self.api_root}/issue/{quote(issue_key.strip(), safe='')}",
            params=params,
        )
        self._cooldown(self.per_issue_cooldown_seconds)
        return payload if isinstance(payload, dict) else None

    def list_issue_worklogs(
        self,
        issue_key: str,
        *,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        worklogs: list[dict[str, Any]] = []
        start_at = 0
        while True:
            payload = self._get_json(
                f"{self.api_root}/issue/{quote(issue_key.strip(), safe='')}/worklog",
                params={"startAt": start_at, "maxResults": max_results},
            )
            chunk = payload.get("worklogs")
            if isinstance(chunk, list):
                worklogs.extend(item for item in chunk if isinstance(item, dict))
            total = int(payload.get("total") or 0)
            fetched = int(payload.get("maxResults") or max_results)
            start_at += fetched
            self._cooldown(self.page_cooldown_seconds)
            if start_at >= total:
                break
        self._cooldown(self.per_issue_cooldown_seconds)
        return worklogs

    def list_issue_changelog(
        self,
        issue_key: str,
        *,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        histories: list[dict[str, Any]] = []
        start_at = 0
        while True:
            payload = self._get_json(
                f"{self.api_root}/issue/{quote(issue_key.strip(), safe='')}/changelog",
                params={"startAt": start_at, "maxResults": max_results},
            )
            chunk = payload.get("values")
            if isinstance(chunk, list):
                histories.extend(item for item in chunk if isinstance(item, dict))
            total = int(payload.get("total") or 0)
            fetched = int(payload.get("maxResults") or max_results)
            start_at += fetched
            self._cooldown(self.page_cooldown_seconds)
            if start_at >= total:
                break
        self._cooldown(self.per_issue_cooldown_seconds)
        return histories

    def get_workflow_scheme_project_associations(
        self,
        *,
        project_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not project_ids:
            return []
        params: list[tuple[str, str]] = [("projectId", project_id) for project_id in project_ids]
        payload = self._get_json(f"{self.api_root}/workflowscheme/project", params=params)
        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            return []
        return [item for item in values if isinstance(item, dict)]

    def bulk_get_workflows(
        self,
        *,
        workflow_names: list[str],
    ) -> dict[str, Any]:
        names = [name.strip() for name in workflow_names if name and name.strip()]
        if not names:
            return {}
        payload = self._post_json(
            f"{self.api_root}/workflows",
            json_body={"workflowNames": names},
        )
        return payload if isinstance(payload, dict) else {}

    def search_workflows_page(
        self,
        *,
        start_at: int = 0,
        max_results: int = 50,
    ) -> dict[str, Any]:
        payload = self._get_json(
            f"{self.api_root}/workflows/search",
            params={"startAt": start_at, "maxResults": max_results},
        )
        return payload if isinstance(payload, dict) else {}

    def iter_workflow_search_pages(self, *, max_results: int = 50) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        start_at = 0
        while True:
            payload = self.search_workflows_page(start_at=start_at, max_results=max_results)
            pages.append(payload)
            values = payload.get("values")
            if not isinstance(values, list) or not values:
                break
            if payload.get("isLast"):
                break
            start_at += len(values)
            self._cooldown(self.page_cooldown_seconds)
        return pages

    def get_project_issue_type_statuses(self, *, jira_project_id: str) -> list[dict[str, Any]]:
        payload = self._get_json(f"{self.api_root}/project/{jira_project_id}/statuses")
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(is_retryable_http_exception),
        reraise=True,
    )
    def _post_json(self, url: str, *, json_body: dict[str, Any]) -> Any:
        response = self.client.post(url, json=json_body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if is_retryable_http_exception(exc):
                raise
            raise RuntimeError(
                f"Jira API request failed: {exc.response.status_code} {url}"
            ) from exc
        return response.json()
