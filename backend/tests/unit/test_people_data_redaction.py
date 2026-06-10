from __future__ import annotations

from app.jira_analytics.people_data_redaction import (
    redact_availability_vs_booked,
    redact_customer_effort,
    redact_heatmap,
    redact_people_worklogs,
)
from app.schemas.jira_analytics_reports import AnalyticsReportResponse


def test_heatmap_redaction_keeps_topic_totals_but_removes_people() -> None:
    report = AnalyticsReportResponse(
        series=[
            {
                "team": "Team Tantrum",
                "topics": [{"topic": "Roadmap", "people": [{"person": "Dev", "hours": 2.0}]}],
            }
        ],
        table=[{"team": "Team Tantrum", "topic": "Roadmap", "person": "Dev", "hours": 2.0}],
    )

    redacted = redact_heatmap(report, allowed=False)

    assert redacted.summary["people_data_restricted"] is True
    assert "people" not in redacted.series[0]["topics"][0]
    assert redacted.table == []


def test_availability_redaction_removes_nested_people_and_person_rows() -> None:
    report = AnalyticsReportResponse(
        series=[{"teams": [{"team": "Team Tantrum", "people": [{"person": "Dev"}]}]}],
        table=[{"team": "Team Tantrum", "person": "Dev", "logged_hours": 1.0}],
    )

    redacted = redact_availability_vs_booked(report, allowed=False)

    assert "people" not in redacted.series[0]["teams"][0]
    assert redacted.table == []


def test_people_worklog_redaction_drops_table() -> None:
    report = AnalyticsReportResponse(table=[{"person": "Dev", "direct_hours": 1.0}])

    redacted = redact_people_worklogs(report, allowed=False)

    assert redacted.table == []
    assert redacted.filters["people_data_restricted"] is True


def test_customer_effort_redaction_removes_people_from_rows_and_drilldowns() -> None:
    report = AnalyticsReportResponse(
        table=[{"customer": "A", "people": [{"person": "Dev", "hours": 1.0}]}],
        filters={
            "issue_drilldowns": {
                "A": [{"issue_key": "BM-1", "people": [{"person": "Dev", "hours": 1.0}]}]
            }
        },
    )

    redacted = redact_customer_effort(report, allowed=False)

    assert "people" not in redacted.table[0]
    assert "people" not in redacted.filters["issue_drilldowns"]["A"][0]
