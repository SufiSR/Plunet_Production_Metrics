from __future__ import annotations

from app.jira_analytics.workflow.status_waiting_catalog import (
    MAIN_WORKFLOW_SPECS,
    issue_type_matches_catalog_option,
    normalize_priority_name,
    status_waiting_priority_columns,
    workflow_matches_other_spec,
)


def test_plunet_cloud_matches_bug_subtask() -> None:
    assert issue_type_matches_catalog_option("Bug Sub-task", "Bug")
    assert issue_type_matches_catalog_option("Improvement Sub-task", "Improvement")


def test_development_subtask_option_only_matches_subtasks() -> None:
    assert issue_type_matches_catalog_option("Development Sub-task", "Development Subtask")
    assert not issue_type_matches_catalog_option("Development", "Development Subtask")


def test_main_workflow_specs_cloud_before_standard() -> None:
    assert [spec.catalog_key for spec in MAIN_WORKFLOW_SPECS] == [
        "plunet_cloud",
        "standard_plunet",
    ]


def test_status_waiting_priority_column_order() -> None:
    assert status_waiting_priority_columns() == [
        "Blocker",
        "Critical",
        "Major",
        "Normal",
        "Minor",
    ]


def test_normalize_priority_aliases() -> None:
    assert normalize_priority_name("Highest") == "Critical"
    assert normalize_priority_name("High") == "Major"
    assert normalize_priority_name("Normal") == "Normal"


def test_product_discovery_workflow_name() -> None:
    from app.jira_analytics.workflow.status_waiting_catalog import OTHER_WORKFLOW_SPECS

    spec = next(item for item in OTHER_WORKFLOW_SPECS if item.catalog_key == "product_discovery")
    assert workflow_matches_other_spec("10001: 10002 workflow for product_discovery", spec)
