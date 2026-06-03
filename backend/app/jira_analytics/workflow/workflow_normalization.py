from __future__ import annotations

import re

STATUS_MARKER_SUFFIX_RE = re.compile(r"\s*\(\s*[*!]\s*\)\s*$", re.IGNORECASE)
TRAILING_BANG_RE = re.compile(r"\s*!\s*$")
SUBTASK_ISSUE_TYPE_RE = re.compile(r"^(?P<base>.+?)\s+sub[- ]?tasks?$", re.IGNORECASE)

EXCLUDED_STATUS_NAMES = frozenset({"done"})


def canonical_status_name(raw: str | None) -> str | None:
    """Merge Jira status variants such as 'In Arbeit (!)' into 'In Arbeit'."""
    if not raw:
        return None
    name = raw.strip()
    if not name:
        return None
    name = STATUS_MARKER_SUFFIX_RE.sub("", name).strip()
    name = TRAILING_BANG_RE.sub("", name).strip()
    return name or None


def is_excluded_status(canonical: str) -> bool:
    return canonical.strip().lower() in EXCLUDED_STATUS_NAMES


def normalize_issue_type_family(name: str | None) -> str:
    """Treat 'Bug Sub-task' like 'Bug' for workflow grouping."""
    raw = (name or "").strip()
    if not raw:
        return "Unknown"
    match = SUBTASK_ISSUE_TYPE_RE.match(raw)
    if match:
        base = match.group("base").strip()
        return base or raw
    return raw


def issue_type_matches_filter(issue_type_name: str | None, filter_family: str | None) -> bool:
    if not filter_family:
        return True
    return normalize_issue_type_family(issue_type_name) == filter_family
