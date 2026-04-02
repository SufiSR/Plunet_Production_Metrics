from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config_schema import ConfigurationSchema
from app.models.issue_worklog import IssueWorklog
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.sync_log import SyncLog

logger = logging.getLogger(__name__)

_SEMVER_RE = re.compile(r"^[vV]?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)")


@dataclass(slots=True)
class HealthResult:
    healthy: bool
    healthmemo: str
    parent_affects_versions: list[str]
    parent_fix_versions: list[str]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value
    if len(normalized) >= 5 and normalized[-5] in {"+", "-"} and normalized[-3] != ":":
        normalized = f"{normalized[:-2]}:{normalized[-2:]}"
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _lookback_from(days: int) -> datetime:
    lookback_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    return datetime(
        lookback_date.year,
        lookback_date.month,
        lookback_date.day,
        tzinfo=timezone.utc,
    )


def _is_retryable_http_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


def _to_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            result.append(text)
    return result


def _extract_named_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text = str(value.get("name") or "").strip()
            if text:
                names.append(text)
    return names


def _parse_semver(value: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(value.strip())
    if not match:
        return None
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def _max_semver(values: list[str]) -> tuple[int, int, int] | None:
    parsed = [
        version for version in (_parse_semver(value) for value in values)
        if version is not None
    ]
    if not parsed:
        return None
    return max(parsed)


def _all_customers_are_plunet(customers: list[str]) -> bool:
    if not customers:
        return False
    return all("plunet" in customer.lower() for customer in customers)


def _evaluate_primary_health(
    *,
    affects_versions: list[str],
    fix_versions: list[str],
    indicator_cf10114: str | None,
    customer_names: list[str],
) -> list[str]:
    reasons: list[str] = []
    if not affects_versions:
        reasons.append("unhealthy - affected_version missing")
    if not indicator_cf10114 and not customer_names and not fix_versions:
        reasons.append("unhealthy - customer missing and fix_version missing")
    if not indicator_cf10114 and _all_customers_are_plunet(customer_names):
        reasons.append("unhealthy - Customer set to Plunet only")
    return reasons


def _has_next_minor_marker(values: list[str]) -> bool:
    marker = "next minor - please branch from master"
    return any(marker in value.lower() for value in values)


def evaluate_issue_health(
    *,
    issue_type: str,
    parent_type: str | None,
    parent_summary: str | None,
    affects_versions: list[str],
    fix_versions: list[str],
    indicator_cf10114: str | None,
    customer_names: list[str],
    parent_affects_versions: list[str],
    parent_fix_versions: list[str],
    parent_indicator_cf10114: str | None,
    parent_customer_names: list[str],
) -> HealthResult:
    reasons = _evaluate_primary_health(
        affects_versions=affects_versions,
        fix_versions=fix_versions,
        indicator_cf10114=indicator_cf10114,
        customer_names=customer_names,
    )
    if not reasons:
        return HealthResult(True, "post-production", parent_affects_versions, parent_fix_versions)

    parent_summary_lower = str(parent_summary or "").lower()
    parent_type_lower = str(parent_type or "").lower()
    if "test" in parent_summary_lower or parent_type_lower in {
        "techsupport",
        "new feature",
        "analysis",
        "epic",
        "improvement",
    }:
        return HealthResult(
            True,
            f"pre-production - parent is {parent_type or 'unknown'}",
            parent_affects_versions,
            parent_fix_versions,
        )

    max_fix = _max_semver(fix_versions)
    max_affects = _max_semver(affects_versions)
    if max_fix is not None and max_affects is not None and max_fix > max_affects:
        return HealthResult(
            True,
            "post-production due to higher fix_version",
            parent_affects_versions,
            parent_fix_versions,
        )

    healthmemo = " and ".join(reasons)
    result = HealthResult(False, healthmemo, parent_affects_versions, parent_fix_versions)

    if issue_type in {"Bug", "Bug Subtask"} and str(parent_type or "").lower() == "bug":
        parent_reasons = _evaluate_primary_health(
            affects_versions=parent_affects_versions,
            fix_versions=parent_fix_versions,
            indicator_cf10114=parent_indicator_cf10114,
            customer_names=parent_customer_names,
        )
        if not parent_reasons:
            result = HealthResult(
                True,
                "post-production due to parent",
                parent_affects_versions,
                parent_fix_versions,
            )
        else:
            parent_max_fix = _max_semver(parent_fix_versions)
            parent_max_affects = _max_semver(parent_affects_versions)
            if (
                parent_max_fix is not None
                and parent_max_affects is not None
                and parent_max_fix > parent_max_affects
            ):
                result = HealthResult(
                    True,
                    "post-production due to parent",
                    parent_affects_versions,
                    parent_fix_versions,
                )

    if not result.healthy and _has_next_minor_marker(
        affects_versions + fix_versions + parent_affects_versions + parent_fix_versions
    ):
        return HealthResult(
            True,
            "post-production - next minor stated",
            parent_affects_versions,
            parent_fix_versions,
        )
    return result


def issue_changelog_histories_from_search_issue(
    issue: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    """Return (histories, needs_full_changelog_fetch).

    If the embedded changelog is truncated (``total`` > len(histories)), the second value is True.
    """
    changelog = issue.get("changelog")
    if not isinstance(changelog, dict):
        return [], True
    raw_histories = changelog.get("histories")
    if not isinstance(raw_histories, list):
        return [], True
    histories = [h for h in raw_histories if isinstance(h, dict)]
    total = int(changelog.get("total") or len(histories))
    incomplete = total > len(histories)
    return histories, incomplete


def first_ready_for_qa_at(
    changelog_items: list[dict[str, Any]],
    ready_status_names: list[str],
) -> datetime | None:
    allowed = {name.strip().lower() for name in ready_status_names if name.strip()}
    if not allowed:
        return None
    first_hit: datetime | None = None
    for history in changelog_items:
        created_at = _parse_dt(str(history.get("created") or ""))
        if created_at is None:
            continue
        items = history.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("field") or "").lower() != "status":
                continue
            to_name = str(item.get("toString") or "").strip().lower()
            if to_name and to_name in allowed:
                if first_hit is None or created_at < first_hit:
                    first_hit = created_at
    return first_hit


def parse_worklog_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    jira_worklog_id = str(raw.get("id") or "").strip()
    if not jira_worklog_id:
        return None
    time_spent_seconds = raw.get("timeSpentSeconds")
    if not isinstance(time_spent_seconds, int):
        return None
    author_payload = raw.get("author")
    author = None
    if isinstance(author_payload, dict):
        author = str(author_payload.get("displayName") or "").strip() or None
    started = _parse_dt(str(raw.get("started") or ""))
    return {
        "jira_worklog_id": jira_worklog_id,
        "author": author,
        "started": started,
        "time_spent_seconds": time_spent_seconds,
    }


class JiraBugsClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        user_email: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_root = f"{base_url.rstrip('/')}/rest/api/3"
        email = (user_email or "").strip()
        headers: dict[str, str] = {"Accept": "application/json"}
        auth: httpx.Auth | None = None
        if email:
            # Jira Cloud API tokens: Basic auth with Atlassian account email + API token.
            auth = httpx.BasicAuth(email, token)
        else:
            # OAuth 2.0 (3LO) access tokens use Bearer.
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers=headers,
            auth=auth,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> JiraBugsClient:
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
                f"Jira API request failed: {exc.response.status_code} {url}"
            ) from exc
        return response.json()

    def search_bugs(
        self,
        *,
        jql: str,
        fields: list[str],
        max_results: int = 100,
        expand: str | None = None,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        next_page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "jql": jql,
                "fields": ",".join(fields),
                "maxResults": max_results,
            }
            if expand:
                params["expand"] = expand
            if next_page_token:
                params["nextPageToken"] = next_page_token
            payload = self._get_json(f"{self.api_root}/search/jql", params=params)
            page_issues = payload.get("issues")
            if isinstance(page_issues, list):
                issues.extend(item for item in page_issues if isinstance(item, dict))
            next_page_token = str(payload.get("nextPageToken") or "").strip() or None
            if next_page_token is None:
                break
        return issues

    def get_issue(self, issue_key: str, *, fields: list[str]) -> dict[str, Any] | None:
        payload = self._get_json(
            f"{self.api_root}/issue/{quote(issue_key.strip(), safe='')}",
            params={"fields": ",".join(fields)},
        )
        return payload if isinstance(payload, dict) else None

    def list_issue_worklogs(
        self, issue_key: str, *, max_results: int = 100,
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
            if start_at >= total:
                break
        return worklogs

    def list_issue_changelog(
        self, issue_key: str, *, max_results: int = 100,
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
            if start_at >= total:
                break
        return histories


def _build_bug_jql(lookback_from: datetime, excluded_projects: list[str]) -> str:
    jql = (
        'issuetype in ("Bug","Bug Subtask") '
        f'AND updated >= "{lookback_from.strftime("%Y-%m-%d")}"'
    )
    projects = [project.strip() for project in excluded_projects if project.strip()]
    if projects:
        quoted = ",".join(f'"{project}"' for project in projects)
        jql += f" AND project NOT IN ({quoted})"
    return jql


def _merged_jira_settings(defaults: ConfigurationSchema) -> tuple[list[str], list[str]]:
    excluded_projects = list(defaults.jira.excluded_projects)
    ready_status_names = list(defaults.jira.ready_for_qa_status_names)
    return excluded_projects, ready_status_names


def _upsert_production_bug(
    db: Session,
    *,
    issue_key: str,
    fields: dict[str, Any],
    health: HealthResult,
    ready_for_qa_at: datetime | None,
    total_worklog_seconds: int,
) -> ProductionBug:
    bug = db.execute(
        select(ProductionBug).where(ProductionBug.jira_key == issue_key)
    ).scalar_one_or_none()
    if bug is None:
        bug = ProductionBug(jira_key=issue_key, healthy=health.healthy)
        db.add(bug)

    issue_type = str((fields.get("issuetype") or {}).get("name") or "").strip() or None
    status = str((fields.get("status") or {}).get("name") or "").strip() or None
    priority = str((fields.get("priority") or {}).get("name") or "").strip() or None
    parent_payload = fields.get("parent") if isinstance(fields.get("parent"), dict) else {}
    parent_fields = parent_payload.get("fields") if isinstance(parent_payload, dict) else {}
    if not isinstance(parent_fields, dict):
        parent_fields = {}

    customer_names = _to_string_list(fields.get("customfield_10123"))
    created_at = _parse_dt(str(fields.get("created") or ""))
    closed_at = _parse_dt(str(fields.get("resolutiondate") or ""))
    if created_at is None:
        logger.warning(
            "Jira issue %s has missing or unparseable created; "
        "excluding from creation-time metrics",
            issue_key,
        )
        bug.jira_created_at_valid = False
        bug.created_at = None
        mttr_minutes = None
        invalid_created_msg = "invalid or missing Jira created timestamp"
        bug.healthmemo = (
            f"{invalid_created_msg}; {health.healthmemo}"
            if health.healthmemo else invalid_created_msg
        )
    else:
        bug.jira_created_at_valid = True
        bug.created_at = created_at
        mttr_minutes = None
        if closed_at is not None and closed_at >= created_at:
            mttr_minutes = int((closed_at - created_at).total_seconds() // 60)
        bug.healthmemo = health.healthmemo

    bug.summary = str(fields.get("summary") or "").strip() or None
    bug.issue_type = issue_type
    bug.status = status
    bug.priority = priority
    bug.components = _extract_named_values(fields.get("components")) or None
    bug.affects_versions = _extract_named_values(fields.get("versions")) or None
    bug.fix_versions = _extract_named_values(fields.get("fixVersions")) or None
    bug.parent_key = str(parent_payload.get("key") or "").strip() or None
    bug.parent_type = str((parent_fields.get("issuetype") or {}).get("name") or "").strip() or None
    bug.indicator_cf10114 = str(fields.get("customfield_10114") or "").strip() or None
    bug.indicator_cf10123 = ", ".join(customer_names) if customer_names else None
    bug.healthy = health.healthy
    bug.updated_at = _parse_dt(str(fields.get("updated") or ""))
    bug.closed_at = closed_at
    bug.mttr_minutes = mttr_minutes
    bug.ready_for_qa_at = ready_for_qa_at
    bug.total_worklog_seconds = total_worklog_seconds
    db.flush()
    return bug


def _sync_issue_worklogs(
    db: Session, *, bug_id: int, parsed_worklogs: list[dict[str, Any]],
) -> None:
    incoming_by_id = {w["jira_worklog_id"]: w for w in parsed_worklogs}
    existing = db.execute(
        select(IssueWorklog).where(IssueWorklog.bug_id == bug_id)
    ).scalars().all()

    existing_ids: set[str] = set()
    for wl in existing:
        existing_ids.add(wl.jira_worklog_id)
        incoming = incoming_by_id.get(wl.jira_worklog_id)
        if incoming is not None:
            wl.author = incoming["author"]
            wl.started = incoming["started"]
            wl.time_spent_seconds = incoming["time_spent_seconds"]

    for wl_id, data in incoming_by_id.items():
        if wl_id not in existing_ids:
            db.add(
                IssueWorklog(
                    bug_id=bug_id,
                    jira_worklog_id=data["jira_worklog_id"],
                    author=data["author"],
                    started=data["started"],
                    time_spent_seconds=data["time_spent_seconds"],
                )
            )

    removed_ids = existing_ids - set(incoming_by_id.keys())
    if removed_ids:
        db.execute(
            delete(IssueWorklog).where(
                IssueWorklog.bug_id == bug_id,
                IssueWorklog.jira_worklog_id.in_(removed_ids),
            )
        )


def hydrate_merge_request_jira_ready_for_qa(
    db: Session,
    *,
    config: ConfigurationSchema,
    jira_token: str,
    jira_user_email: str = "",
    per_page: int = 100,
) -> int:
    """Fetch Ready-for-QA timestamps from Jira for MR-linked keys not covered by ProductionBug.

    Production bugs already carry ``ready_for_qa_at`` from the bug sync. This step covers
    feature / non-bug issues referenced only from GitLab MR titles/branches.
    """
    if not (jira_token or "").strip():
        return 0
    _, ready_status_names = _merged_jira_settings(config)
    with_bug_ready = set(
        db.execute(
            select(ProductionBug.jira_key).where(
                ProductionBug.jira_key.isnot(None),
                ProductionBug.ready_for_qa_at.isnot(None),
            )
        )
        .scalars()
        .all()
    )
    keys = sorted(
        {
            k
            for k in db.execute(
                select(MergeRequest.jira_key).where(MergeRequest.jira_key.isnot(None))
            )
            .scalars()
            .all()
            if k and k not in with_bug_ready
        }
    )
    if not keys:
        return 0
    touched = 0
    with JiraBugsClient(
        base_url=config.jira.base_url,
        token=jira_token,
        user_email=jira_user_email or None,
    ) as jira:
        for issue_key in keys:
            try:
                changelog_items = jira.list_issue_changelog(issue_key, max_results=per_page)
                rfq = first_ready_for_qa_at(changelog_items, ready_status_names)
                result = db.execute(
                    update(MergeRequest)
                    .where(MergeRequest.jira_key == issue_key)
                    .values(jira_ready_for_qa_at=rfq)
                )
                touched += int(result.rowcount or 0)
            except Exception:
                logger.exception("hydrate_jira_ready_for_qa failed for %s", issue_key)
    db.commit()
    return touched


def collect_jira_production_bugs(
    db: Session,
    *,
    config: ConfigurationSchema,
    jira_token: str,
    jira_user_email: str = "",
    per_page: int = 100,
) -> int:
    started_at = datetime.now(timezone.utc)
    sync_log = SyncLog(source="jira", started_at=started_at, status="running")
    db.add(sync_log)
    db.flush()

    excluded_projects, ready_status_names = _merged_jira_settings(config)
    lookback_from = _lookback_from(config.backend.lookback_days)
    jql = _build_bug_jql(lookback_from, excluded_projects)
    fields = [
        "summary",
        "issuetype",
        "status",
        "priority",
        "created",
        "updated",
        "resolutiondate",
        "versions",
        "fixVersions",
        "components",
        "parent",
        "customfield_10114",
        "customfield_10123",
    ]
    processed = 0
    parent_cache: dict[str, dict[str, Any]] = {}

    try:
        with JiraBugsClient(
            base_url=config.jira.base_url,
            token=jira_token,
            user_email=jira_user_email or None,
        ) as jira:
            issues = jira.search_bugs(
                jql=jql,
                fields=fields,
                max_results=per_page,
                expand="changelog",
            )
            for issue in issues:
                issue_key = str(issue.get("key") or "").strip()
                issue_fields = issue.get("fields")
                if not issue_key or not isinstance(issue_fields, dict):
                    continue

                issue_type = str((issue_fields.get("issuetype") or {}).get("name") or "").strip()
                parent_payload = issue_fields.get("parent")
                parent_fields = {}
                if isinstance(parent_payload, dict):
                    maybe_fields = parent_payload.get("fields")
                    if isinstance(maybe_fields, dict):
                        parent_fields = maybe_fields

                parent_key = (
                    str(parent_payload.get("key") or "").strip()
                    if isinstance(parent_payload, dict) else ""
                )
                parent_type = (
                    str((parent_fields.get("issuetype") or {}).get("name") or "").strip()
                    or None
                )
                parent_summary = str(parent_fields.get("summary") or "").strip() or None

                affects_versions = _extract_named_values(issue_fields.get("versions"))
                fix_versions = _extract_named_values(issue_fields.get("fixVersions"))
                indicator_cf10114 = str(issue_fields.get("customfield_10114") or "").strip() or None
                customer_names = _to_string_list(issue_fields.get("customfield_10123"))

                parent_affects_versions = _extract_named_values(parent_fields.get("versions"))
                parent_fix_versions = _extract_named_values(parent_fields.get("fixVersions"))
                parent_indicator_cf10114 = (
                    str(parent_fields.get("customfield_10114") or "").strip() or None
                )
                parent_customer_names = _to_string_list(parent_fields.get("customfield_10123"))

                if (
                    issue_type in {"Bug", "Bug Subtask"}
                    and str(parent_type or "").lower() == "bug"
                    and parent_key
                    and not parent_affects_versions
                    and not parent_fix_versions
                ):
                    parent_issue = parent_cache.get(parent_key)
                    if parent_issue is None:
                        parent_issue = jira.get_issue(parent_key, fields=fields) or {}
                        parent_cache[parent_key] = parent_issue
                    parent_issue_fields = (
                        parent_issue.get("fields")
                    if isinstance(parent_issue.get("fields"), dict) else {}
                    )
                    parent_affects_versions = _extract_named_values(
                        parent_issue_fields.get("versions")
                    )
                    parent_fix_versions = _extract_named_values(
                        parent_issue_fields.get("fixVersions")
                    )
                    parent_indicator_cf10114 = (
                        str(parent_issue_fields.get("customfield_10114") or "").strip() or None
                    )
                    parent_customer_names = _to_string_list(
                        parent_issue_fields.get("customfield_10123")
                    )
                    parent_type = (
                        str((parent_issue_fields.get("issuetype") or {}).get("name") or "").strip()
                        or parent_type
                    )
                    parent_summary = (
                        str(parent_issue_fields.get("summary") or "").strip()
                        or parent_summary
                    )

                health = evaluate_issue_health(
                    issue_type=issue_type,
                    parent_type=parent_type,
                    parent_summary=parent_summary,
                    affects_versions=affects_versions,
                    fix_versions=fix_versions,
                    indicator_cf10114=indicator_cf10114,
                    customer_names=customer_names,
                    parent_affects_versions=parent_affects_versions,
                    parent_fix_versions=parent_fix_versions,
                    parent_indicator_cf10114=parent_indicator_cf10114,
                    parent_customer_names=parent_customer_names,
                )

                changelog_items, changelog_incomplete = (
                    issue_changelog_histories_from_search_issue(issue)
                )
                if changelog_incomplete:
                    changelog_items = jira.list_issue_changelog(issue_key, max_results=per_page)
                ready_for_qa_at = first_ready_for_qa_at(changelog_items, ready_status_names)
                parsed_worklogs = [
                    parsed
                    for parsed in (
                        parse_worklog_entry(item)
                        for item in jira.list_issue_worklogs(issue_key, max_results=per_page)
                    )
                    if parsed is not None
                ]
                total_worklog_seconds = sum(
                    worklog["time_spent_seconds"] for worklog in parsed_worklogs
                )

                bug = _upsert_production_bug(
                    db,
                    issue_key=issue_key,
                    fields=issue_fields,
                    health=health,
                    ready_for_qa_at=ready_for_qa_at,
                    total_worklog_seconds=total_worklog_seconds,
                )
                _sync_issue_worklogs(db, bug_id=bug.id, parsed_worklogs=parsed_worklogs)
                processed += 1

        sync_log.status = "success"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.records_processed = processed
        db.commit()
        return processed
    except Exception as exc:
        db.rollback()
        finished_at = datetime.now(timezone.utc)
        db.add(
            SyncLog(
                source="jira",
                started_at=started_at,
                finished_at=finished_at,
                status="failed",
                error_message=str(exc)[:4000],
            )
        )
        db.commit()
        raise
