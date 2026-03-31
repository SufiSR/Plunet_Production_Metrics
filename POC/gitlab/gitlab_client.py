"""
GitLab POC client – fetches repository tags via REST API v4.

API: GET /projects/:id/repository/tags
Project id: URL-encoded path, e.g. dev%2Fplunet
https://docs.gitlab.com/ee/api/tags.html
"""

import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx

# Matches standard Jira issue keys, e.g. BM-1234, API-56, REST-789
_JIRA_KEY_RE = re.compile(r'\b([A-Z][A-Z0-9]+-\d+)\b')


def _encode_project_path(project_path: str) -> str:
    """GitLab expects the path with slashes as %2F."""
    return quote(project_path.strip(), safe="")


def _prerelease_pattern(markers: list[str]) -> re.Pattern[str]:
    """Tag names with -<marker> then . or digit or end are not customer releases."""
    parts = [re.escape(m) for m in markers if m]
    inner = "|".join(parts) if parts else "rc|beta"
    return re.compile(rf"-(?:{inner})(?:[.\d]|$)", re.IGNORECASE)


def _is_customer_release(tag_name: str | None, prerelease_re: re.Pattern[str]) -> bool:
    if not tag_name or not str(tag_name).strip():
        return False
    return prerelease_re.search(tag_name) is None


def _parse_committed_datetime(committed_date: str | None) -> datetime | None:
    if not committed_date:
        return None
    try:
        return datetime.fromisoformat(committed_date.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_tag(raw: dict, prerelease_re: re.Pattern[str]) -> dict:
    """Normalize API response for JSON export."""
    commit = raw.get("commit") or {}
    name = raw.get("name")
    return {
        "name": name,
        "customer_release": _is_customer_release(name if isinstance(name, str) else None, prerelease_re),
        "target": raw.get("target"),
        "message": raw.get("message"),
        "protected": raw.get("protected"),
        "commit_id": commit.get("id"),
        "commit_short_id": commit.get("short_id"),
        "commit_title": commit.get("title"),
        "committed_date": commit.get("committed_date"),
        "created_at": commit.get("created_at"),
    }


def _extract_jira_key(
    title: str | None,
    source_branch: str | None,
    description: str | None,
) -> tuple[str | None, str | None]:
    """
    Extract the first Jira issue key from MR title (primary), source branch, or description (fallbacks).
    Returns (jira_key, source) where source is 'title' | 'branch' | 'description' | None.

    Note: `references` in the GitLab API only contains GitLab-internal MR references (!NNNN),
    not Jira issue references. Key extraction from text fields is the only available approach
    without the paid GitLab Jira integration plugin.
    """
    for text, source in (
        (title, "title"),
        (source_branch, "branch"),
        (description, "description"),
    ):
        if text:
            m = _JIRA_KEY_RE.search(text)
            if m:
                return m.group(1), source
    return None, None


def _parse_mr(raw: dict) -> dict:
    merge_commit_sha = raw.get("merge_commit_sha")
    squash_commit_sha = raw.get("squash_commit_sha")
    # sha = current HEAD of the MR branch (differs from merge/squash commit)
    head_sha = raw.get("sha")
    chosen_commit_sha = merge_commit_sha or squash_commit_sha
    title = raw.get("title")
    source_branch = raw.get("source_branch")
    description = raw.get("description")
    jira_key, jira_key_source = _extract_jira_key(title, source_branch, description)
    return {
        "id": raw.get("id"),
        "iid": raw.get("iid"),
        "title": title,
        "description": description,
        "web_url": raw.get("web_url"),
        "state": raw.get("state"),
        "author": (raw.get("author") or {}).get("username"),
        "source_branch": source_branch,
        "target_branch": raw.get("target_branch"),
        "created_at": raw.get("created_at"),
        "merged_at": raw.get("merged_at"),
        "head_sha": head_sha,
        "merge_commit_sha": merge_commit_sha,
        "squash_commit_sha": squash_commit_sha,
        "effective_commit_sha": chosen_commit_sha,
        "jira_key": jira_key,
        "jira_key_source": jira_key_source,
    }


def fetch_project_tags(
    base_url: str,
    token: str,
    project_path: str,
    per_page: int = 100,
    lookback_years: int = 2,
    non_customer_release_markers: list[str] | None = None,
    timeout_seconds: float = 60.0,
) -> dict:
    """
    Fetch all tags with pagination, then keep those with committed_date >= lookback_from.

    customer_release is false when tag name matches prerelease markers (e.g. v10.1.0-rc.1, 10.1.0-beta).
    """
    markers = [m.lower() for m in (non_customer_release_markers or ["rc", "beta"]) if str(m).strip()]
    if not markers:
        markers = ["rc", "beta"]
    prerelease_re = _prerelease_pattern(markers)

    encoded = _encode_project_path(project_path)
    api_root = base_url.rstrip("/") + "/api/v4"
    url = f"{api_root}/projects/{encoded}/repository/tags"

    headers = {"PRIVATE-TOKEN": token}

    all_tags: list[dict] = []
    page = 1

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        while True:
            response = client.get(
                url,
                headers=headers,
                params={"page": page, "per_page": per_page},
            )
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise TypeError(f"Unexpected tags response: {type(batch)}")

            for item in batch:
                all_tags.append(_parse_tag(item, prerelease_re))

            if len(batch) < per_page:
                break
            page += 1

    total_raw = len(all_tags)
    lookback_from = date.today() - timedelta(days=lookback_years * 365)
    lookback_from_dt = datetime(
        lookback_from.year,
        lookback_from.month,
        lookback_from.day,
        tzinfo=timezone.utc,
    )

    def within_lookback(tag: dict) -> bool:
        dt = _parse_committed_datetime(tag.get("committed_date"))
        if dt is None:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= lookback_from_dt

    filtered = [t for t in all_tags if within_lookback(t)]

    return {
        "project_path": project_path,
        "base_url": base_url.rstrip("/"),
        "lookback_years": lookback_years,
        "lookback_from": lookback_from.isoformat(),
        "non_customer_release_markers": markers,
        "total_raw": total_raw,
        "total": len(filtered),
        "tags": filtered,
    }


def fetch_merged_merge_requests(
    base_url: str,
    token: str,
    project_path: str,
    target_branch: str | None = "main",
    per_page: int = 100,
    lookback_years: int = 2,
    timeout_seconds: float = 60.0,
) -> dict:
    """
    Fetch merged MRs and filter by merged_at >= lookback_from.
    """
    encoded = _encode_project_path(project_path)
    api_root = base_url.rstrip("/") + "/api/v4"
    url = f"{api_root}/projects/{encoded}/merge_requests"

    headers = {"PRIVATE-TOKEN": token}
    all_mrs: list[dict] = []
    page = 1

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        while True:
            params = {
                "state": "merged",
                "order_by": "updated_at",
                "sort": "desc",
                "page": page,
                "per_page": per_page,
            }
            if target_branch:
                params["target_branch"] = target_branch

            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise TypeError(f"Unexpected merge requests response: {type(batch)}")

            for item in batch:
                all_mrs.append(_parse_mr(item))

            if len(batch) < per_page:
                break
            page += 1

    total_raw = len(all_mrs)
    lookback_from = date.today() - timedelta(days=lookback_years * 365)
    lookback_from_dt = datetime(
        lookback_from.year,
        lookback_from.month,
        lookback_from.day,
        tzinfo=timezone.utc,
    )

    def within_lookback(mr: dict) -> bool:
        merged_at = _parse_committed_datetime(mr.get("merged_at"))
        if merged_at is None:
            return False
        if merged_at.tzinfo is None:
            merged_at = merged_at.replace(tzinfo=timezone.utc)
        return merged_at >= lookback_from_dt

    filtered = [mr for mr in all_mrs if within_lookback(mr)]
    return {
        "project_path": project_path,
        "base_url": base_url.rstrip("/"),
        "target_branch": target_branch,
        "lookback_years": lookback_years,
        "lookback_from": lookback_from.isoformat(),
        "total_raw": total_raw,
        "total": len(filtered),
        "merge_requests": filtered,
    }


def fetch_merged_merge_requests_for_branches(
    base_url: str,
    token: str,
    project_path: str,
    target_branches: list[str],
    per_page: int = 100,
    lookback_years: int = 2,
    timeout_seconds: float = 60.0,
) -> dict:
    """
    Fetch merged MRs for multiple target branches and de-duplicate by MR id.
    """
    branches = [b.strip() for b in target_branches if b and b.strip()]
    if not branches:
        branches = ["master"]

    by_id: dict[int, dict] = {}
    total_raw = 0
    per_branch_totals: dict[str, int] = {}
    lookback_from: str | None = None
    for branch in branches:
        result = fetch_merged_merge_requests(
            base_url=base_url,
            token=token,
            project_path=project_path,
            target_branch=branch,
            per_page=per_page,
            lookback_years=lookback_years,
            timeout_seconds=timeout_seconds,
        )
        total_raw += result.get("total_raw", 0)
        per_branch_totals[branch] = result.get("total", 0)
        lookback_from = result.get("lookback_from")
        for mr in result.get("merge_requests", []):
            mr_id = mr.get("id")
            if isinstance(mr_id, int):
                by_id[mr_id] = mr

    merged = sorted(
        by_id.values(),
        key=lambda mr: (mr.get("merged_at") or ""),
        reverse=True,
    )

    return {
        "project_path": project_path,
        "base_url": base_url.rstrip("/"),
        "target_branches": branches,
        "lookback_years": lookback_years,
        "lookback_from": lookback_from,
        "total_raw": total_raw,
        "total": len(merged),
        "per_branch_totals": per_branch_totals,
        "merge_requests": merged,
    }


def _fetch_mr_first_commit_at(
    client: httpx.Client,
    api_root: str,
    encoded_project: str,
    token: str,
    mr_iid: int,
) -> str | None:
    """
    Return ISO timestamp of the earliest commit in the MR, or None.

    Calls GET /projects/:id/merge_requests/:iid/commits (paginated).
    The earliest committed_date across all commits in the MR is the
    'work started' timestamp needed for the full Lead Time for Changes
    (first_commit_at → first customer release tag).
    """
    url = f"{api_root}/projects/{encoded_project}/merge_requests/{mr_iid}/commits"
    page = 1
    per_page = 100
    earliest: datetime | None = None

    while True:
        response = client.get(
            url,
            headers={"PRIVATE-TOKEN": token},
            params={"page": page, "per_page": per_page},
        )
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            break
        for commit in batch:
            raw_date = commit.get("committed_date") or commit.get("created_at")
            dt = _parse_committed_datetime(raw_date)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if earliest is None or dt < earliest:
                    earliest = dt
        if len(batch) < per_page:
            break
        page += 1

    return earliest.isoformat() if earliest else None


def enrich_mr_first_commit_timestamps(
    base_url: str,
    token: str,
    project_path: str,
    merge_requests: list[dict],
    timeout_seconds: float = 60.0,
) -> list[dict]:
    """
    Add first_commit_at to each MR dict (ISO timestamp of the earliest commit in the MR).

    Calls GET /projects/:id/merge_requests/:iid/commits once per MR.
    This is the additional API call needed to compute the full Lead Time for Changes:
        first_commit_at → first customer release tag
    (as opposed to release wait time: merged_at → first customer release tag).

    Returns new dicts; original list is not mutated.
    Note: ~1 API call per MR; respect the GitLab rate limit (20 req/s) if needed.
    """
    encoded = _encode_project_path(project_path)
    api_root = base_url.rstrip("/") + "/api/v4"

    enriched: list[dict] = []
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        for mr in merge_requests:
            mr_iid = mr.get("iid")
            first_commit_at: str | None = None
            if isinstance(mr_iid, int):
                first_commit_at = _fetch_mr_first_commit_at(
                    client=client,
                    api_root=api_root,
                    encoded_project=encoded,
                    token=token,
                    mr_iid=mr_iid,
                )
            enriched.append({**mr, "first_commit_at": first_commit_at})

    return enriched


def _fetch_commit_tag_refs(
    client: httpx.Client,
    api_root: str,
    project_path: str,
    token: str,
    commit_sha: str,
) -> set[str]:
    """
    Return tag names that reference the commit according to GitLab refs API.
    """
    encoded = _encode_project_path(project_path)
    url = f"{api_root}/projects/{encoded}/repository/commits/{commit_sha}/refs"
    response = client.get(
        url,
        headers={"PRIVATE-TOKEN": token},
        params={"type": "tag"},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        return set()
    return {
        str(item.get("name")).strip()
        for item in data
        if isinstance(item, dict) and item.get("type") == "tag" and item.get("name")
    }


def compute_lead_time_from_mrs_and_tags(
    base_url: str,
    token: str,
    project_path: str,
    merge_requests: list[dict],
    tags: list[dict],
    timeout_seconds: float = 60.0,
) -> dict:
    """
    Compute lead-time mapping for each MR to its earliest customer release tag.

    Produces two complementary time spans per MR:
      - release_wait_time: merged_at → first_customer_tag_date
            How long "ready" code sits before shipping. (Release Wait Time KPI)
      - lead_time_from_first_commit: first_commit_at → first_customer_tag_date
            Full development cycle from work start to customer delivery.
            Requires MRs pre-enriched via enrich_mr_first_commit_timestamps().
            NULL when first_commit_at is absent.
    """
    api_root = base_url.rstrip("/") + "/api/v4"
    customer_tags_by_name = {t["name"]: t for t in tags if t.get("customer_release") and t.get("name")}
    tag_refs_cache: dict[str, set[str]] = {}

    results: list[dict] = []
    matched = 0
    unmatched = 0

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        for mr in merge_requests:
            commit_sha = mr.get("effective_commit_sha")
            merged_at = _parse_committed_datetime(mr.get("merged_at"))
            first_commit_at_raw: str | None = mr.get("first_commit_at")
            first_commit_dt = _parse_committed_datetime(first_commit_at_raw)
            if first_commit_dt is not None and first_commit_dt.tzinfo is None:
                first_commit_dt = first_commit_dt.replace(tzinfo=timezone.utc)

            if not commit_sha or merged_at is None:
                unmatched += 1
                results.append(
                    {
                        "mr_iid": mr.get("iid"),
                        "mr_id": mr.get("id"),
                        "mr_title": mr.get("title"),
                        "target_branch": mr.get("target_branch"),
                        "first_commit_at": first_commit_at_raw,
                        "merged_at": mr.get("merged_at"),
                        "effective_commit_sha": commit_sha,
                        "jira_key": mr.get("jira_key"),
                        "jira_key_source": mr.get("jira_key_source"),
                        "first_customer_tag": None,
                        "first_customer_tag_date": None,
                        "release_wait_time_hours": None,
                        "release_wait_time_days": None,
                        "lead_time_from_first_commit_hours": None,
                        "lead_time_from_first_commit_days": None,
                        "match_status": "no_effective_commit_or_merged_at",
                    }
                )
                continue

            if merged_at.tzinfo is None:
                merged_at = merged_at.replace(tzinfo=timezone.utc)

            if commit_sha not in tag_refs_cache:
                tag_refs_cache[commit_sha] = _fetch_commit_tag_refs(
                    client=client,
                    api_root=api_root,
                    project_path=project_path,
                    token=token,
                    commit_sha=commit_sha,
                )

            tag_names = tag_refs_cache[commit_sha]
            candidate_tags: list[tuple[datetime, dict]] = []
            for tag_name in tag_names:
                tag = customer_tags_by_name.get(tag_name)
                if not tag:
                    continue
                tag_dt = _parse_committed_datetime(tag.get("committed_date"))
                if tag_dt is None:
                    continue
                if tag_dt.tzinfo is None:
                    tag_dt = tag_dt.replace(tzinfo=timezone.utc)
                if tag_dt >= merged_at:
                    candidate_tags.append((tag_dt, tag))

            if not candidate_tags:
                unmatched += 1
                results.append(
                    {
                        "mr_iid": mr.get("iid"),
                        "mr_id": mr.get("id"),
                        "mr_title": mr.get("title"),
                        "target_branch": mr.get("target_branch"),
                        "first_commit_at": first_commit_at_raw,
                        "merged_at": mr.get("merged_at"),
                        "effective_commit_sha": commit_sha,
                        "jira_key": mr.get("jira_key"),
                        "jira_key_source": mr.get("jira_key_source"),
                        "first_customer_tag": None,
                        "first_customer_tag_date": None,
                        "release_wait_time_hours": None,
                        "release_wait_time_days": None,
                        "lead_time_from_first_commit_hours": None,
                        "lead_time_from_first_commit_days": None,
                        "match_status": "no_customer_tag_ref_found",
                    }
                )
                continue

            first_dt, first_tag = sorted(candidate_tags, key=lambda x: x[0])[0]
            wait_seconds = (first_dt - merged_at).total_seconds()

            lead_from_commit_hours: float | None = None
            lead_from_commit_days: float | None = None
            if first_commit_dt is not None:
                lead_seconds = (first_dt - first_commit_dt).total_seconds()
                lead_from_commit_hours = round(lead_seconds / 3600, 2)
                lead_from_commit_days = round(lead_seconds / 86400, 2)

            matched += 1
            results.append(
                {
                    "mr_iid": mr.get("iid"),
                    "mr_id": mr.get("id"),
                    "mr_title": mr.get("title"),
                    "target_branch": mr.get("target_branch"),
                    "first_commit_at": first_commit_at_raw,
                    "merged_at": mr.get("merged_at"),
                    "effective_commit_sha": commit_sha,
                    "jira_key": mr.get("jira_key"),
                    "jira_key_source": mr.get("jira_key_source"),
                    "first_customer_tag": first_tag.get("name"),
                    "first_customer_tag_date": first_tag.get("committed_date"),
                    "release_wait_time_hours": round(wait_seconds / 3600, 2),
                    "release_wait_time_days": round(wait_seconds / 86400, 2),
                    "lead_time_from_first_commit_hours": lead_from_commit_hours,
                    "lead_time_from_first_commit_days": lead_from_commit_days,
                    "match_status": "matched",
                }
            )

    return {
        "project_path": project_path,
        "total_merge_requests": len(merge_requests),
        "matched": matched,
        "unmatched": unmatched,
        "lead_time_records": results,
    }
