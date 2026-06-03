from __future__ import annotations

"""Condense legacy Standard Plunet workflow statuses into current display names."""

STANDARD_PLUNET_STATUS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Backlog",
        ("Backlog", "Ready to start", "Ready for development", "Ready for Development"),
    ),
    (
        "Assigned - Ready to start",
        ("Assigned - Ready to start", "Assigned - ready to start"),
    ),
    ("In Progress", ("In Progress", "In Arbeit", "Development")),
    ("Reopened", ("Reopened",)),
    ("Solved - Ready for approval", ("Solved - Ready for approval",)),
    ("Waiting for input", ("Waiting for input",)),
    (
        "Ready for code review",
        ("Ready for code review", "Ready for Code Review"),
    ),
    ("Code review", ("Code review", "Code Review")),
    ("Ready for QA", ("Ready for QA",)),
    ("Test", ("Test",)),
)


def _build_alias_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, aliases in STANDARD_PLUNET_STATUS_GROUPS:
        for alias in (canonical, *aliases):
            mapping[alias.strip().lower()] = canonical
    return mapping


_STANDARD_PLUNET_STATUS_ALIASES = _build_alias_map()


def condense_standard_plunet_status(status: str) -> str:
    """Map legacy status names to the current Standard Plunet display label."""
    condensed = _STANDARD_PLUNET_STATUS_ALIASES.get(status.strip().lower())
    return condensed if condensed is not None else status


def standard_plunet_status_display_order() -> list[str]:
    return [canonical for canonical, _aliases in STANDARD_PLUNET_STATUS_GROUPS]


def order_standard_plunet_statuses(statuses: set[str]) -> list[str]:
    order = standard_plunet_status_display_order()
    declared = [status for status in order if status in statuses]
    remaining = sorted(statuses - set(order), key=str.lower)
    return declared + remaining
