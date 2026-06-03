from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.issue_worklog import IssueWorklog
from app.models.production_bug import ProductionBug
from app.services.jira_worklog_settings import list_distinct_worklog_authors_page


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_list_distinct_worklog_authors_orders_with_distinct_outer_query() -> None:
    """Regression: Postgres rejects DISTINCT + ORDER BY on non-selected expressions."""
    with _session() as db:
        bug = ProductionBug(
            id=1,
            jira_key="DEVOPS-9001",
            healthy=True,
            healthmemo=None,
            jira_created_at_valid=True,
        )
        db.add(bug)
        db.flush()
        db.add_all(
            [
                IssueWorklog(
                    id=101,
                    bug_id=1,
                    jira_worklog_id="w1",
                    jira_account_id="acc-z",
                    author="Zebra",
                    time_spent_seconds=60,
                ),
                IssueWorklog(
                    id=102,
                    bug_id=1,
                    jira_worklog_id="w2",
                    jira_account_id="acc-a",
                    author="alpha",
                    time_spent_seconds=60,
                ),
            ]
        )
        db.commit()

        rows, total = list_distinct_worklog_authors_page(db, page=0, size=10)
        assert total == 2
        assert [(a, author) for a, author in rows] == [
            ("acc-a", "alpha"),
            ("acc-z", "Zebra"),
        ]
