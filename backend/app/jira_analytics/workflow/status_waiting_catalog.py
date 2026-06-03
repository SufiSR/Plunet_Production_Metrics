from __future__ import annotations

from dataclasses import dataclass

from app.jira_analytics.workflow.workflow_normalization import (
    SUBTASK_ISSUE_TYPE_RE,
    normalize_issue_type_family,
)


@dataclass(frozen=True, slots=True)
class MainWorkflowSpec:
    catalog_key: str
    label: str
    workflow_names: frozenset[str]
    """Issue types allowed for this main workflow (eligibility for dynamic pills)."""
    allowed_issue_type_options: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OtherWorkflowSpec:
    catalog_key: str
    label: str
    workflow_names: frozenset[str]
    name_substrings: tuple[str, ...] = ()


MAIN_WORKFLOW_SPECS: tuple[MainWorkflowSpec, ...] = (
    MainWorkflowSpec(
        catalog_key="plunet_cloud",
        label="Plunet Cloud Workflow",
        workflow_names=frozenset({"Plunet Cloud Workflow"}),
        allowed_issue_type_options=("Bug", "Improvement"),
    ),
    MainWorkflowSpec(
        catalog_key="standard_plunet",
        label="Standard Plunet Workflow",
        workflow_names=frozenset({"Standard Plunet Workflow"}),
        allowed_issue_type_options=("Analysis", "Epic", "TechSupport", "Development Subtask"),
    ),
)

OTHER_WORKFLOW_SPECS: tuple[OtherWorkflowSpec, ...] = (
    OtherWorkflowSpec(
        catalog_key="product_discovery",
        label="Workflow for product_discovery",
        workflow_names=frozenset(),
        name_substrings=("product_discovery",),
    ),
    OtherWorkflowSpec(
        catalog_key="design",
        label="Design Workflow",
        workflow_names=frozenset({"Design Workflow"}),
    ),
    OtherWorkflowSpec(
        catalog_key="autotest",
        label="Autotest Workflow",
        workflow_names=frozenset({"QA: AutoTest Workflow", "Autotest Workflow"}),
    ),
    OtherWorkflowSpec(
        catalog_key="regular_test",
        label="Regular Test Workflow",
        workflow_names=frozenset({"QA: Regular Test Workflow", "Regular Test Workflow"}),
    ),
    OtherWorkflowSpec(
        catalog_key="test_result",
        label="Test Result Workflow",
        workflow_names=frozenset({"QA: Test Result Workflow", "Test Result Workflow"}),
    ),
)

STATUS_WAITING_PRIORITY_COLUMNS: tuple[str, ...] = (
    "Blocker",
    "Critical",
    "Major",
    "Normal",
    "Minor",
)

PRIORITY_ORDER: tuple[str, ...] = STATUS_WAITING_PRIORITY_COLUMNS + ("Unknown",)

_PRIORITY_ALIASES: dict[str, str] = {
    "highest": "Critical",
    "high": "Major",
    "medium": "Normal",
    "low": "Minor",
    "lowest": "Minor",
    "trivial": "Minor",
}


def _development_subtask_only(issue_type_name: str) -> bool:
    raw = issue_type_name.strip()
    if not raw:
        return False
    if raw.lower() in {"development subtask", "development sub-task"}:
        return True
    match = SUBTASK_ISSUE_TYPE_RE.match(raw)
    return match is not None and match.group("base").strip().lower() == "development"


def issue_type_matches_catalog_option(issue_type_name: str | None, option: str) -> bool:
    if not issue_type_name:
        return False
    raw = issue_type_name.strip()
    family = normalize_issue_type_family(issue_type_name)
    option_norm = option.strip()
    if not option_norm:
        return False
    if option_norm == "Development Subtask":
        return _development_subtask_only(raw)
    if option_norm in {raw, family}:
        return True
    return family == option_norm


def issue_type_eligible_for_main_spec(issue_type_name: str | None, spec: MainWorkflowSpec) -> bool:
    return any(
        issue_type_matches_catalog_option(issue_type_name, option)
        for option in spec.allowed_issue_type_options
    )


def issue_type_matches_any_name(
    issue_type_name: str | None,
    selected_names: set[str],
) -> bool:
    if not selected_names:
        return False
    if not issue_type_name:
        return False
    raw = issue_type_name.strip()
    family = normalize_issue_type_family(issue_type_name)
    return raw in selected_names or family in selected_names


def workflow_matches_main_spec(workflow_name: str, spec: MainWorkflowSpec) -> bool:
    return workflow_name.strip() in spec.workflow_names


def workflow_matches_other_spec(workflow_name: str, spec: OtherWorkflowSpec) -> bool:
    name = workflow_name.strip()
    if name in spec.workflow_names:
        return True
    lowered = name.lower()
    return any(fragment in lowered for fragment in spec.name_substrings)


def normalize_priority_name(priority_name: str | None) -> str:
    value = (priority_name or "").strip()
    if not value:
        return "Unknown"
    alias = _PRIORITY_ALIASES.get(value.lower())
    if alias is not None:
        return alias
    if value in STATUS_WAITING_PRIORITY_COLUMNS:
        return value
    return value


def status_waiting_priority_columns() -> list[str]:
    return list(STATUS_WAITING_PRIORITY_COLUMNS)


def sort_priorities(priorities: set[str]) -> list[str]:
    order_index = {name: index for index, name in enumerate(PRIORITY_ORDER)}

    def sort_key(name: str) -> tuple[int, str]:
        return (order_index.get(name, len(PRIORITY_ORDER)), name.lower())

    return sorted(priorities, key=sort_key)
