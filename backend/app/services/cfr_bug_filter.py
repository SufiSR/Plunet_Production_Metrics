from __future__ import annotations

from sqlalchemy import ColumnElement, and_

from app.models.production_bug import ProductionBug


def cfr_eligible_production_bug_predicate() -> ColumnElement[bool]:
    """Bugs that count toward CFR: healthy and classified as post-production (not internal QA).

    Pre-production issues can still be marked healthy with a memo starting with
    "pre-production" (see jira-production-bug-filter-decision.md); they must not affect CFR.
    """
    memo = ProductionBug.healthmemo
    return and_(
        ProductionBug.healthy.is_(True),
        memo.is_not(None),
        memo.ilike("post-production%"),
    )
