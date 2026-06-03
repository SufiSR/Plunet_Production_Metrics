from __future__ import annotations

from decimal import Decimal

from app.jira_analytics.models import AllocationRoleRule, JiraUserRoleAssignment


def effective_allocation_params(
    rule: AllocationRoleRule,
    assignment: JiraUserRoleAssignment,
) -> tuple[Decimal, str, Decimal]:
    if assignment.allocatable_percentage is not None:
        allocatable_pct = Decimal(assignment.allocatable_percentage)
        overhead_pct = Decimal(100) - allocatable_pct
    else:
        overhead_pct = Decimal(rule.overhead_percentage)
        allocatable_pct = Decimal(100) - overhead_pct
    scope = (assignment.allocation_scope or rule.allocation_scope or "global").strip()
    return overhead_pct, scope, allocatable_pct
