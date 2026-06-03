from __future__ import annotations

from app.jira_analytics.workflow.standard_plunet_status_condensation import (
    condense_standard_plunet_status,
    order_standard_plunet_statuses,
    standard_plunet_status_display_order,
)


def test_standard_plunet_status_display_order() -> None:
    order = standard_plunet_status_display_order()
    assert order[0] == "Backlog"
    assert order[1] == "Assigned - Ready to start"
    assert order[2] == "In Progress"
    assert order[-1] == "Test"


def test_condense_legacy_status_aliases() -> None:
    assert condense_standard_plunet_status("Ready to start") == "Backlog"
    assert condense_standard_plunet_status("Ready for development") == "Backlog"
    assert condense_standard_plunet_status("Assigned - ready to start") == "Assigned - Ready to start"
    assert condense_standard_plunet_status("In Arbeit") == "In Progress"
    assert condense_standard_plunet_status("Development") == "In Progress"
    assert condense_standard_plunet_status("Ready for Code Review") == "Ready for code review"


def test_condense_unknown_status_passthrough() -> None:
    assert condense_standard_plunet_status("On Hold") == "On Hold"


def test_order_standard_plunet_statuses_known_then_unknown() -> None:
    ordered = order_standard_plunet_statuses({"Test", "On Hold", "Backlog"})
    assert ordered == ["Backlog", "Test", "On Hold"]
