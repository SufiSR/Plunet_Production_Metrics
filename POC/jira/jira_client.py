"""
Jira POC collector – fetches production bugs relevant for DORA metrics.

A production bug is defined as:
  - Issue type: Bug or Bug Subtask
  - Created within the configured lookback window
  - Health is determined by affects_versions, customer indicators, fix_versions,
    and parent context (see _evaluate_health for full rule set)
"""

from datetime import date, datetime, timedelta, timezone

from atlassian import Jira


# ── helpers ──────────────────────────────────────────────────────────────────

def _as_customfield_id(cf_numeric_id: int) -> str:
    return f"customfield_{int(cf_numeric_id)}"


def _is_non_empty(value: object) -> bool:
    return value is not None and str(value).strip() != ""


def _as_text_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if _is_non_empty(v)]
    return [str(value).strip()] if _is_non_empty(value) else []


def _parse_version_tuple(version: str) -> tuple[int, ...] | None:
    nums: list[int] = []
    current = ""
    for ch in version:
        if ch.isdigit():
            current += ch
        else:
            if current:
                nums.append(int(current))
                current = ""
    if current:
        nums.append(int(current))
    if not nums:
        return None
    return tuple(nums)


def _has_higher_fix_version(fix_versions: list[str], affected_versions: list[str]) -> bool:
    if not fix_versions or not affected_versions:
        return False
    parsed_fix = [v for v in (_parse_version_tuple(x) for x in fix_versions) if v is not None]
    parsed_aff = [v for v in (_parse_version_tuple(x) for x in affected_versions) if v is not None]
    if not parsed_fix or not parsed_aff:
        return False
    return max(parsed_fix) > max(parsed_aff)


def _has_next_minor_marker(version_values: list[str]) -> bool:
    marker = "next minor - please branch from master"
    return any(marker in str(v).lower() for v in version_values)


def _evaluate_health(
    affects_versions: list[str],
    fix_versions: list[str],
    indicator_values: dict[str, object],
    parent_summary: str,
    parent_type: str,
) -> tuple[bool, str]:
    """
    Returns (is_healthy, healthmemo).

    Derives cf[10123] from indicator_values directly.
    """
    has_affected_versions = bool(affects_versions)
    has_customer_indicator = any(_is_non_empty(v) for v in indicator_values.values())

    cf_10114_value = indicator_values.get("customfield_10114")
    has_10114 = _is_non_empty(cf_10114_value)

    cf_10123_raw = indicator_values.get("customfield_10123")
    cf_10123_values = _as_text_values(cf_10123_raw)
    cf_10123_has_values = len(cf_10123_values) > 0
    cf_10123_all_plunet = cf_10123_has_values and all("plunet" in v.lower() for v in cf_10123_values)

    customer_is_plunet_only = (not has_10114) and cf_10123_all_plunet

    has_fix_versions = bool(fix_versions)

    # --- Primary unhealthy reasons ---
    unhealthy_reasons: list[str] = []
    if not has_affected_versions:
        unhealthy_reasons.append("unhealthy - affected_version missing")
    if not has_customer_indicator and not has_fix_versions:
        unhealthy_reasons.append("unhealthy - customer missing and fix_version missing")
    if customer_is_plunet_only:
        unhealthy_reasons.append("unhealthy - Customer set to Plunet only")

    if not unhealthy_reasons:
        return True, "post-production"

    # --- Override 1: parent type/summary rescue (ONLY when unhealthy) ---
    parent_type_allowed = {"techsupport", "new feature", "analysis", "epic", "improvement"}
    has_test_in_parent_summary = "test" in parent_summary.lower()
    parent_type_matches = parent_type.lower() in parent_type_allowed

    if has_test_in_parent_summary or parent_type_matches:
        label = parent_type if parent_type else "unknown"
        return True, f"pre-production - parent is {label}"

    # --- Override 2: fix_version higher than affects_version ---
    if _has_higher_fix_version(fix_versions, affects_versions):
        return True, "post-production due to higher fix_version"

    return False, " and ".join(unhealthy_reasons)


def _fetch_parent_bug_context(
    jira: Jira,
    parent_keys: list[str],
    indicator_field_ids: list[str],
) -> dict[str, dict]:
    if not parent_keys:
        return {}

    unique_keys = sorted(set(parent_keys))
    context: dict[str, dict] = {}
    fields = ["summary", "issuetype", "versions", "fixVersions"]
    fields.extend(indicator_field_ids)

    chunk_size = 100
    for i in range(0, len(unique_keys), chunk_size):
        chunk = unique_keys[i : i + chunk_size]
        jql = f'issuetype = "Bug" AND issuekey in ({",".join(chunk)})'
        result = jira.enhanced_jql(jql, fields=fields, limit=1000)
        for issue in result.get("issues", []):
            issue_fields = issue.get("fields", {})
            context[issue["key"]] = {
                "affects_versions": [
                    v["name"] for v in issue_fields.get("versions", []) if v.get("name")
                ],
                "fix_versions": [
                    v["name"] for v in issue_fields.get("fixVersions", []) if v.get("name")
                ],
                "indicator_fields": {fid: issue_fields.get(fid) for fid in indicator_field_ids},
            }
    return context


def _parse_bug(issue: dict, indicator_field_ids: list[str]) -> dict:
    """Extract the data we care about from a raw Jira issue dict."""
    fields = issue.get("fields", {})

    affects_versions = [
        v["name"] for v in fields.get("versions", []) if v.get("name")
    ]
    fix_versions = [
        v["name"] for v in fields.get("fixVersions", []) if v.get("name")
    ]
    components = [c["name"] for c in fields.get("components", []) if c.get("name")]

    indicator_values = {fid: fields.get(fid) for fid in indicator_field_ids}
    parent = fields.get("parent") or {}
    parent_fields = parent.get("fields") or {}

    parent_summary = parent_fields.get("summary") or ""
    parent_type = parent_fields.get("issuetype", {}).get("name") or ""
    is_healthy, healthmemo = _evaluate_health(
        affects_versions=affects_versions,
        fix_versions=fix_versions,
        indicator_values=indicator_values,
        parent_summary=parent_summary,
        parent_type=parent_type,
    )

    closed_at = fields.get("resolutiondate")
    priority = (fields.get("priority") or {}).get("name")

    return {
        "jira_key": issue["key"],
        "summary": fields.get("summary"),
        "issue_type": fields.get("issuetype", {}).get("name"),
        "status": fields.get("status", {}).get("name"),
        "priority": priority,
        "created_at": fields.get("created"),
        "updated_at": fields.get("updated"),
        "closed_at": closed_at,
        "components": components,
        "parent_key": parent.get("key"),
        "parent_summary": parent_summary or None,
        "parent_type": parent_type or None,
        "parent_affects_versions": [],
        "parent_fix_versions": [],
        "parent_customfield_10114": None,
        "parent_customfield_10123": None,
        "affects_versions": affects_versions,
        "fix_versions": fix_versions,
        "indicator_fields": indicator_values,
        "healthy": is_healthy,
        "healthmemo": healthmemo,
    }


# ── public API ────────────────────────────────────────────────────────────────

def fetch_production_bugs(
    jira_url: str,
    username: str,
    token: str,
    lookback_years: int = 3,
    indicator_cf_ids: list[int] | None = None,
    excluded_projects: list[str] | None = None,
) -> dict:
    """
    Connect to Jira and return all production bugs together with metadata.

    Args:
        lookback_years: Only fetch bugs created within this many years.
                        Configured via configuration.yml -> jira.lookback_years.

    Returns a dict with:
      - "indicator_cf_ids": numeric custom field IDs used as production-bug indicators
      - "lookback_from": ISO date string used as the lower bound
      - "total": total number of matching issues
      - "bugs": list of parsed bug dicts
    """
    jira = Jira(url=jira_url, username=username, password=token, cloud=True)

    indicator_cf_ids = indicator_cf_ids or [10114]
    indicator_field_ids = [_as_customfield_id(n) for n in indicator_cf_ids]
    print(f"Using production-bug indicators: {indicator_cf_ids}")

    lookback_from = date.today() - timedelta(days=lookback_years * 365)
    lookback_from_str = lookback_from.strftime("%Y-%m-%d")
    print(f"  -> Lookback window: {lookback_years} year(s), from {lookback_from_str}")
    excluded_projects = [p.strip() for p in (excluded_projects or []) if p and p.strip()]
    if excluded_projects:
        print(f"  -> Excluding projects: {excluded_projects}")

    jql_parts = [
        'issuetype in ("Bug", "Bug Subtask")',
        f"created >= {lookback_from_str!r}",
    ]
    if excluded_projects:
        quoted_projects = ",".join(f'"{p}"' for p in excluded_projects)
        jql_parts.append(f"project not in ({quoted_projects})")

    jql = " AND ".join(jql_parts) + " ORDER BY created DESC"
    print(f"\nRunning JQL: {jql}\n")

    fields = [
        "summary",
        "issuetype",
        "status",
        "priority",
        "created",
        "updated",
        "resolutiondate",
        "components",
        "parent",
        "versions",
        "fixVersions",
    ]
    fields.extend(indicator_field_ids)

    page_size = 100
    next_page_token: str | None = None
    all_bugs: list[dict] = []
    page = 1

    while True:
        print(f"  Fetching page {page} (up to {page_size} issues) ...")
        result = jira.enhanced_jql(
            jql,
            fields=fields,
            limit=page_size,
            nextPageToken=next_page_token,
        )

        issues = result.get("issues", [])
        all_bugs.extend(_parse_bug(issue, indicator_field_ids) for issue in issues)

        next_page_token = result.get("nextPageToken")
        if not next_page_token or not issues:
            break

        page += 1

    # Second-pass parent-based correction:
    # For currently unhealthy Bug/Bug Subtask with a Bug parent, fetch parent's
    # data and re-evaluate health using the same primary rules (no grandparent context).
    targets = [
        bug for bug in all_bugs
        if not bug.get("healthy")
        and (bug.get("issue_type") or "").lower() in {"bug", "bug subtask"}
        and (bug.get("parent_type") or "").lower() == "bug"
        and bug.get("parent_key")
    ]
    parent_context = _fetch_parent_bug_context(
        jira=jira,
        parent_keys=[bug["parent_key"] for bug in targets],
        indicator_field_ids=indicator_field_ids,
    )
    for bug in targets:
        parent_key = bug.get("parent_key")
        parent_data = parent_context.get(parent_key)
        if not parent_data:
            continue

        bug["parent_affects_versions"] = parent_data["affects_versions"]
        bug["parent_fix_versions"] = parent_data["fix_versions"]
        bug["parent_customfield_10114"] = parent_data["indicator_fields"].get("customfield_10114")
        bug["parent_customfield_10123"] = parent_data["indicator_fields"].get("customfield_10123")

        parent_healthy, parent_memo = _evaluate_health(
            affects_versions=parent_data["affects_versions"],
            fix_versions=parent_data["fix_versions"],
            indicator_values=parent_data["indicator_fields"],
            parent_summary="",
            parent_type="",
        )
        if parent_healthy:
            bug["healthy"] = True
            if parent_memo.startswith("pre-production"):
                bug["healthmemo"] = "pre-production due to parent"
            else:
                bug["healthmemo"] = "post-production due to parent"

    # Final-pass override:
    # If any version field states "next minor - please branch from master",
    # classify still-unhealthy issues as post-production.
    for bug in all_bugs:
        if bug.get("healthy"):
            continue

        version_fields = []
        version_fields.extend(bug.get("affects_versions") or [])
        version_fields.extend(bug.get("fix_versions") or [])
        version_fields.extend(bug.get("parent_affects_versions") or [])
        version_fields.extend(bug.get("parent_fix_versions") or [])

        if _has_next_minor_marker(version_fields):
            bug["healthy"] = True
            bug["healthmemo"] = "post-production - next minor stated"

    print(f"\nDone. {len(all_bugs)} production bugs fetched.")

    return {
        "indicator_cf_ids": indicator_cf_ids,
        "excluded_projects": excluded_projects,
        "lookback_from": lookback_from_str,
        "total": len(all_bugs),
        "bugs": all_bugs,
    }


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) // 2


def _percentile(values: list[int], p: int) -> int | None:
    if not values:
        return None
    s = sorted(values)
    idx = min(int(len(s) * p / 100), len(s) - 1)
    return s[idx]


def compute_mttr_alpha(
    bugs: list[dict],
    mr_jira_key_to_tag: dict[str, tuple[str, str]],
    tag_name_to_date: dict[str, str],
    critical_priorities: list[str] | None = None,
) -> dict:
    """
    Compute MTTR Alpha per eligible bug and aggregate statistics.

    MTTR Alpha = bug.created_at → first customer release tag that contains the fix.
    Measures DEV-owned response time from incident report to customer delivery.

    Eligibility: healthy=True AND priority in critical_priorities.

    Two resolution paths (tried in order):
      1. mr_jira_key  – find the MR whose jira_key matches the bug's jira_key;
                        use that MR's first_customer_tag_date.
      2. fix_version  – match bug.fix_versions to release tag names (with/without
                        leading 'v'); use the earliest matching tag's committed_date.

    Args:
        bugs:                  List of parsed bug dicts (from fetch_production_bugs).
        mr_jira_key_to_tag:    {jira_key: (tag_name, tag_committed_date_iso)}
                               Built from GitLab MR lead-time output:
                               only MRs with match_status="matched" and first_commit_at set.
        tag_name_to_date:      {tag_name: committed_date_iso}
                               All customer_release=true tags from GitLab.
        critical_priorities:   Priority names that qualify (default: Critical, Blocker).
    """
    priorities = {p.lower() for p in (critical_priorities or ["critical", "blocker"])}

    eligible = [
        b for b in bugs
        if b.get("healthy")
        and (b.get("priority") or "").lower() in priorities
    ]

    records: list[dict] = []
    for bug in eligible:
        jira_key = bug.get("jira_key")
        created_at_str = bug.get("created_at")
        created_dt = _parse_iso(created_at_str)

        first_fix_tag: str | None = None
        first_fix_date_str: str | None = None
        resolution_path: str | None = None

        # Path 1: MR with matching jira_key → first_customer_tag_date
        if jira_key in mr_jira_key_to_tag:
            tag_name, tag_date = mr_jira_key_to_tag[jira_key]
            first_fix_tag = tag_name
            first_fix_date_str = tag_date
            resolution_path = "mr_jira_key"
        else:
            # Path 2: fix_versions → release tag name match
            fix_versions: list[str] = bug.get("fix_versions") or []
            candidates: list[tuple[datetime, str, str]] = []
            for fv in fix_versions:
                for variant in [fv, f"v{fv}", fv.lstrip("v")]:
                    if variant in tag_name_to_date:
                        dt = _parse_iso(tag_name_to_date[variant])
                        if dt is not None:
                            candidates.append((dt, variant, tag_name_to_date[variant]))
                        break
            if candidates:
                candidates.sort(key=lambda x: x[0])
                _, first_fix_tag, first_fix_date_str = candidates[0]
                resolution_path = "fix_version"

        mttr_alpha_minutes: int | None = None
        mttr_alpha_hours: float | None = None
        if created_dt and first_fix_date_str:
            fix_dt = _parse_iso(first_fix_date_str)
            if fix_dt is not None and fix_dt >= created_dt:
                delta = int((fix_dt - created_dt).total_seconds() / 60)
                mttr_alpha_minutes = delta
                mttr_alpha_hours = round(delta / 60, 2)

        records.append({
            "jira_key": jira_key,
            "summary": bug.get("summary"),
            "priority": bug.get("priority"),
            "created_at": created_at_str,
            "fix_versions": bug.get("fix_versions"),
            "affects_versions": bug.get("affects_versions"),
            "first_fix_release_tag": first_fix_tag,
            "first_fix_release_date": first_fix_date_str,
            "resolution_path": resolution_path,
            "mttr_alpha_minutes": mttr_alpha_minutes,
            "mttr_alpha_hours": mttr_alpha_hours,
        })

    resolved = [r for r in records if r["mttr_alpha_minutes"] is not None]
    unresolved = [r for r in records if r["mttr_alpha_minutes"] is None]
    mr_path_count = sum(1 for r in resolved if r["resolution_path"] == "mr_jira_key")
    fv_path_count = sum(1 for r in resolved if r["resolution_path"] == "fix_version")

    minutes_list = [r["mttr_alpha_minutes"] for r in resolved]

    return {
        "critical_priorities": sorted(priorities),
        "total_eligible": len(eligible),
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "coverage_pct": round(len(resolved) / len(eligible) * 100, 1) if eligible else 0.0,
        "resolution_path_breakdown": {
            "mr_jira_key": mr_path_count,
            "fix_version": fv_path_count,
        },
        "aggregate": {
            "median_minutes": _median(minutes_list),
            "p75_minutes": _percentile(minutes_list, 75),
            "p90_minutes": _percentile(minutes_list, 90),
            "median_hours": round(_median(minutes_list) / 60, 2) if _median(minutes_list) is not None else None,
            "p75_hours": round(_percentile(minutes_list, 75) / 60, 2) if _percentile(minutes_list, 75) is not None else None,
            "p90_hours": round(_percentile(minutes_list, 90) / 60, 2) if _percentile(minutes_list, 90) is not None else None,
        },
        "records": records,
    }
