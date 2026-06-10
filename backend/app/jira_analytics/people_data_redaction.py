from __future__ import annotations

from typing import Any

from app.schemas.jira_analytics_reports import (
    AnalyticsReportResponse,
    DataQualityUserDrilldownResponse,
)

_RESTRICTED = "Restricted"


def _restricted_report(report: AnalyticsReportResponse) -> AnalyticsReportResponse:
    payload = report.model_copy(deep=True)
    payload.summary = {**payload.summary, "people_data_restricted": True}
    payload.filters = {**payload.filters, "people_data_restricted": True}
    return payload


def redact_heatmap(report: AnalyticsReportResponse, *, allowed: bool) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    for team in payload.series:
        for topic in _list_value(team.get("topics")):
            topic.pop("people", None)
    payload.table = []
    return payload


def redact_availability_vs_booked(
    report: AnalyticsReportResponse, *, allowed: bool
) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    for month in payload.series:
        for team in _list_value(month.get("teams")):
            team.pop("people", None)
    payload.table = [row for row in payload.table if "person" not in row]
    return payload


def redact_capacity_forecast(
    report: AnalyticsReportResponse, *, allowed: bool
) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    payload.table = [
        row for row in payload.table if "person" not in row and "person_key" not in row
    ]
    return payload


def redact_bus_factor(report: AnalyticsReportResponse, *, allowed: bool) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    for row in payload.table:
        if "top_contributor" in row:
            row["top_contributor"] = _RESTRICTED
    return payload


def redact_customer_effort(
    report: AnalyticsReportResponse,
    *,
    allowed: bool,
) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    for row in payload.table:
        row.pop("people", None)
    drilldowns = payload.filters.get("issue_drilldowns")
    if isinstance(drilldowns, dict):
        payload.filters["issue_drilldowns"] = {
            customer: [_without_people(row) for row in _list_value(rows)]
            for customer, rows in drilldowns.items()
        }
    return payload


def redact_people_worklogs(
    report: AnalyticsReportResponse, *, allowed: bool
) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    payload.table = []
    return payload


def redact_allocation_explain(
    report: AnalyticsReportResponse, *, allowed: bool
) -> AnalyticsReportResponse:
    if allowed:
        return report
    payload = _restricted_report(report)
    for row in payload.table:
        row.pop("person", None)
    return payload


def redact_data_quality_user_drilldown(
    response: DataQualityUserDrilldownResponse, *, allowed: bool
) -> DataQualityUserDrilldownResponse:
    if allowed:
        return response
    payload = response.model_copy(deep=True)
    payload.people_data_restricted = True
    for user in payload.users:
        user.display_name = _mask_person(user.display_name, user.account_id)
        user.email_address = _mask_email(user.email_address)
    return payload


def _list_value(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _mask_person(display_name: str | None, account_id: str) -> str:
    if display_name:
        return _RESTRICTED
    if account_id:
        return f"{_RESTRICTED} user"
    return _RESTRICTED


def _mask_email(email: str | None) -> str | None:
    if not email:
        return None
    return "restricted@example.invalid"


def _without_people(row: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(row)
    sanitized.pop("people", None)
    return sanitized
