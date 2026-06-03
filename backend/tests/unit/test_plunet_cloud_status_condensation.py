from __future__ import annotations

from app.jira_analytics.workflow.plunet_cloud_status_condensation import (
    condense_plunet_cloud_status,
    order_plunet_cloud_statuses,
    plunet_cloud_status_display_order,
)


def test_plunet_cloud_status_display_order() -> None:
    order = plunet_cloud_status_display_order()
    assert order[0] == "In preparation"
    assert order[1] == "Backlog"
    assert "Ready for Code Review" in order
    assert order[-1] == "Reopened"


def test_condense_legacy_status_aliases() -> None:
    assert condense_plunet_cloud_status("Auf Entwicklungsplan") == "Backlog"
    assert condense_plunet_cloud_status("Check - Issue Description") == "Description Update"
    assert condense_plunet_cloud_status("Feature Request Meeting Review") == "Refinement"
    assert condense_plunet_cloud_status("Ready to start") == "Ready for Development"
    assert condense_plunet_cloud_status("In Arbeit") == "Development"
    assert condense_plunet_cloud_status("In Progress") == "Development"
    assert condense_plunet_cloud_status("Solved - Ready for approval") == "Ready for Code Review"


def test_condense_unknown_status_passthrough() -> None:
    assert condense_plunet_cloud_status("On Hold") == "On Hold"


def test_order_plunet_cloud_statuses_known_then_unknown() -> None:
    ordered = order_plunet_cloud_statuses({"Development", "On Hold", "Backlog"})
    assert ordered == ["Backlog", "Development", "On Hold"]
