from __future__ import annotations

WORKLOG_ROLE_TO_ALLOCATION: dict[str, str] = {
    "dev": "Developer",
    "qa": "QA",
    "pm": "Product Manager",
    "sup": "Support Agent",
}

DIRECT_PRODUCTION_ROLES = frozenset(
    {"Developer", "QA", "UX Research", "UX Design", "Support Agent", "Solutions Engineer"}
)

HEATMAP_ROLES = frozenset({"Developer", "QA"})


def allocation_role_for_worklog_role(worklog_role: str) -> str:
    key = (worklog_role or "").strip().lower()
    return WORKLOG_ROLE_TO_ALLOCATION.get(key, worklog_role or "Unknown")


ALLOCATION_ROLE_TO_WORKLOG: dict[str, str] = {
    "Developer": "dev",
    "QA": "qa",
    "UX Research": "dev",
    "UX Design": "dev",
    "Product Manager": "pm",
    "Product Owner": "pm",
    "System Architect": "pm",
    "Head of Dev": "pm",
    "Support Agent": "sup",
    "Tech Support": "sup",
    "Solutions Engineer": "sup",
}


def worklog_role_for_allocation_role(allocation_role: str) -> str | None:
    return ALLOCATION_ROLE_TO_WORKLOG.get((allocation_role or "").strip())
