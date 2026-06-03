from __future__ import annotations

from app.jira_analytics.workflow.workflow_normalization import (
    canonical_status_name,
    is_excluded_status,
    normalize_issue_type_family,
)


def test_canonical_status_name_strips_marker_suffixes() -> None:
    assert canonical_status_name("Description update (*)") == "Description update"
    assert canonical_status_name("In Arbeit (!)") == "In Arbeit"
    assert canonical_status_name("In Progress") == "In Progress"


def test_is_excluded_status_drops_done() -> None:
    assert is_excluded_status("Done")
    assert is_excluded_status("done")
    assert not is_excluded_status("In Progress")


def test_normalize_issue_type_family_collapses_subtasks() -> None:
    assert normalize_issue_type_family("Bug Sub-task") == "Bug"
    assert normalize_issue_type_family("Story Subtask") == "Story"
    assert normalize_issue_type_family("Bug") == "Bug"
