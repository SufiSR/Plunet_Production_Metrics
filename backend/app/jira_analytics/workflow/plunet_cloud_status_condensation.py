from __future__ import annotations

"""Condense legacy Plunet Cloud workflow statuses into current display names."""

PLUNET_CLOUD_STATUS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("In preparation", ("In preparation",)),
    ("Backlog", ("Backlog", "Auf Entwicklungsplan")),
    ("Description Update", ("Description Update", "Description update", "Check - Issue Description")),
    ("Refinement", ("Refinement", "Feature Request Meeting Review")),
    (
        "Ready for Development",
        ("Ready for Development", "Assigned - Ready to start", "Ready to start"),
    ),
    ("Development", ("Development", "In Arbeit", "In Progress")),
    ("Waiting for input", ("Waiting for input",)),
    (
        "Ready for Code Review",
        ("Ready for Code Review", "Solved - Ready for approval"),
    ),
    ("Code review", ("Code review", "Code Review")),
    ("Ready for QA", ("Ready for QA",)),
    ("Test", ("Test",)),
    ("Testing blocked", ("Testing blocked",)),
    ("Ready to merge", ("Ready to merge",)),
    ("Merging", ("Merging",)),
    ("Reopened", ("Reopened",)),
)


def _build_alias_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, aliases in PLUNET_CLOUD_STATUS_GROUPS:
        for alias in (canonical, *aliases):
            mapping[alias.strip().lower()] = canonical
    return mapping


_PLUNET_CLOUD_STATUS_ALIASES = _build_alias_map()


def condense_plunet_cloud_status(status: str) -> str:
    """Map legacy status names to the current Plunet Cloud display label."""
    condensed = _PLUNET_CLOUD_STATUS_ALIASES.get(status.strip().lower())
    return condensed if condensed is not None else status


def plunet_cloud_status_display_order() -> list[str]:
    return [canonical for canonical, _aliases in PLUNET_CLOUD_STATUS_GROUPS]


def order_plunet_cloud_statuses(statuses: set[str]) -> list[str]:
    order = plunet_cloud_status_display_order()
    declared = [status for status in order if status in statuses]
    remaining = sorted(statuses - set(order), key=str.lower)
    return declared + remaining
