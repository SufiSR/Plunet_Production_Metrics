from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

REQUIRED_FIELD_IDS: tuple[str, ...] = (
    "parent",
    "customfield_10110",
    "customfield_10111",
    "resolution",
    "customfield_10114",
    "customfield_10104",
    "customfield_10108",
    "customfield_10109",
    "customfield_10180",
    "customfield_10181",
    "priority",
    "labels",
    "assignee",
    "status",
    "components",
    "creator",
    "reporter",
    "customfield_10167",
    "customfield_10169",
    "customfield_10159",
    "issuetype",
    "customfield_10030",
    "project",
    "customfield_10033",
    "resolutiondate",
    "created",
    "customfield_10260",
    "customfield_10259",
    "customfield_10251",
    "customfield_10252",
    "customfield_10185",
    "customfield_10020",
    "updated",
    "description",
    "customfield_10131",
    "customfield_10014",
    "customfield_10135",
    "customfield_10015",
    "customfield_10084",
    "customfield_10085",
    "customfield_10079",
    "customfield_10005",
    "customfield_10127",
    "customfield_10006",
    "customfield_10007",
    "customfield_10008",
    "customfield_10129",
    "customfield_10009",
    "summary",
    "customfield_10001",
    "customfield_10123",
    "versions",
    "fixVersions",
    "subtasks",
    "issuelinks",
    "worklog",
)


@dataclass(frozen=True)
class RelationPayload:
    target_key: str | None
    target_jira_issue_id: str | None
    relation_source: str
    jira_link_id: str | None = None
    link_type_id: str | None = None
    link_type_name: str = ""
    direction: str = "undirected"
    inward_description: str | None = None
    outward_description: str | None = None
    is_hierarchy_edge: bool = False
    is_feature_membership_edge: bool = False
    raw_json: dict[str, Any] | None = None


def parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text
    if len(normalized) >= 5 and normalized[-5] in {"+", "-"} and normalized[-3] != ":":
        normalized = f"{normalized[:-2]}:{normalized[-2:]}"
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        parsed = parse_dt(text)
        return parsed.date() if parsed else None


def text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("value", "name", "displayName", "key", "id"):
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return candidate
    return str(value).strip() or None


def option_values(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = text_value(item)
        if text:
            result.append(text)
    return result


def named_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("name") or "").strip()
        for item in value
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]


def user_identity(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    account_id = str(value.get("accountId") or "").strip()
    if not account_id:
        return None
    return {
        "account_id": account_id,
        "display_name": str(value.get("displayName") or "").strip() or None,
        "email_address": str(value.get("emailAddress") or "").strip() or None,
        "active": value.get("active") if isinstance(value.get("active"), bool) else None,
        "time_zone": str(value.get("timeZone") or "").strip() or None,
        "account_type": str(value.get("accountType") or "").strip() or None,
        "raw_json": value,
    }


def adf_to_text(value: Any) -> str | None:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            parts.append(node)
            return
        if not isinstance(node, dict):
            if isinstance(node, list):
                for child in node:
                    walk(child)
            return
        node_type = str(node.get("type") or "")
        if node_type == "text":
            parts.append(str(node.get("text") or ""))
        elif node_type in {"hardBreak", "paragraph", "heading", "listItem", "taskItem", "tableRow"}:
            if parts and not parts[-1].endswith("\n"):
                parts.append("\n")
        content = node.get("content")
        if isinstance(content, list):
            for child in content:
                walk(child)
        if node_type in {"paragraph", "heading", "listItem", "taskItem", "tableRow"}:
            if parts and not parts[-1].endswith("\n"):
                parts.append("\n")

    walk(value)
    text = "".join(parts)
    lines = [line.strip() for line in text.splitlines()]
    compact = "\n".join(line for line in lines if line)
    return compact.strip() or None


def extract_project(fields: dict[str, Any]) -> dict[str, Any] | None:
    raw = fields.get("project")
    if not isinstance(raw, dict):
        return None
    project_id = str(raw.get("id") or "").strip()
    key = str(raw.get("key") or "").strip()
    if not project_id or not key:
        return None
    category = raw.get("projectCategory")
    return {
        "jira_project_id": project_id,
        "key": key,
        "name": str(raw.get("name") or "").strip() or None,
        "category_name": (
            str(category.get("name") or "").strip()
            if isinstance(category, dict) and str(category.get("name") or "").strip()
            else None
        ),
        "raw_json": raw,
    }


def extract_issue_core(raw_issue: dict[str, Any]) -> dict[str, Any] | None:
    fields = raw_issue.get("fields")
    if not isinstance(fields, dict):
        return None
    issue_id = str(raw_issue.get("id") or "").strip()
    key = str(raw_issue.get("key") or "").strip()
    if not issue_id or not key:
        return None
    issue_type = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
    status = fields.get("status") if isinstance(fields.get("status"), dict) else {}
    status_category = status.get("statusCategory") if isinstance(status, dict) else {}
    resolution = fields.get("resolution") if isinstance(fields.get("resolution"), dict) else {}
    priority = fields.get("priority") if isinstance(fields.get("priority"), dict) else {}
    parent = fields.get("parent") if isinstance(fields.get("parent"), dict) else {}
    description = fields.get("description")
    return {
        "jira_issue_id": issue_id,
        "key": key,
        "self_url": str(raw_issue.get("self") or "").strip() or None,
        "issue_type_id": str(issue_type.get("id") or "").strip() or None,
        "issue_type_name": str(issue_type.get("name") or "").strip() or None,
        "issue_type_hierarchy_level": issue_type.get("hierarchyLevel")
        if isinstance(issue_type.get("hierarchyLevel"), int)
        else None,
        "summary": str(fields.get("summary") or "").strip() or None,
        "description_text": adf_to_text(description),
        "description_adf": description if isinstance(description, dict) else None,
        "status_id": str(status.get("id") or "").strip() or None,
        "status_name": str(status.get("name") or "").strip() or None,
        "status_category_key": str(status_category.get("key") or "").strip() or None
        if isinstance(status_category, dict)
        else None,
        "status_category_name": str(status_category.get("name") or "").strip() or None
        if isinstance(status_category, dict)
        else None,
        "resolution_id": str(resolution.get("id") or "").strip() or None,
        "resolution_name": str(resolution.get("name") or "").strip() or None,
        "priority_id": str(priority.get("id") or "").strip() or None,
        "priority_name": str(priority.get("name") or "").strip() or None,
        "parent_jira_issue_id": str(parent.get("id") or "").strip() or None,
        "parent_key": str(parent.get("key") or "").strip() or None,
        "created_at_jira": parse_dt(fields.get("created")),
        "updated_at_jira": parse_dt(fields.get("updated")),
        "resolved_at_jira": parse_dt(fields.get("resolutiondate")),
        "raw_fields_json": fields,
        "raw_issue_json": raw_issue,
    }


def _parse_timeline_interval(value: Any) -> tuple[date | None, date | None]:
    """Product Discovery stores Start/End date as JSON."""
    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text.startswith("{"):
            return None, None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None, None
    if not isinstance(payload, dict):
        return None, None
    return parse_date(payload.get("start")), parse_date(payload.get("end"))


def _extract_start_date(fields: dict[str, Any]) -> date | None:
    classic = parse_date(fields.get("customfield_10015"))
    if classic is not None:
        return classic
    interval_start, _ = _parse_timeline_interval(fields.get("customfield_10084"))
    return interval_start


def _extract_promised_delivery_date(fields: dict[str, Any]) -> date | None:
    classic = parse_date(fields.get("customfield_10110"))
    if classic is not None:
        return classic
    _, interval_end = _parse_timeline_interval(fields.get("customfield_10085"))
    return interval_end


def _extract_team_name(fields: dict[str, Any]) -> tuple[str | None, str | None]:
    team = (
        fields.get("customfield_10001") if isinstance(fields.get("customfield_10001"), dict) else {}
    )
    team_id = str(team.get("id") or "").strip() or None
    team_name = str(team.get("name") or "").strip() or None
    if team_name:
        return team_id, team_name
    discovery_teams = option_values(fields.get("customfield_10079"))
    if discovery_teams:
        return None, ", ".join(discovery_teams)
    return team_id, None


def extract_issue_detail(fields: dict[str, Any]) -> dict[str, Any]:
    team_id, team_name = _extract_team_name(fields)
    required = {key: fields.get(key) for key in REQUIRED_FIELD_IDS if key in fields}
    return {
        "promised_delivery_date": _extract_promised_delivery_date(fields),
        "customer_transparency": text_value(fields.get("customfield_10111")),
        "external_issue_url": text_value(fields.get("customfield_10114")),
        "solution": text_value(fields.get("customfield_10108")),
        "promised_sold_on": parse_date(fields.get("customfield_10109")),
        "target_branches": option_values(fields.get("customfield_10180")) or None,
        "documentation": option_values(fields.get("customfield_10181")) or None,
        "version_value": text_value(fields.get("customfield_10167")),
        "epic_thema": text_value(fields.get("customfield_10169")),
        "design": text_value(fields.get("customfield_10030")),
        "goals": text_value(fields.get("customfield_10033")),
        "delivery_status": text_value(fields.get("customfield_10260")),
        "pmgt_product": fields.get("customfield_10185"),
        "external_issue_id": text_value(fields.get("customfield_10131")),
        "epic_link_key": text_value(fields.get("customfield_10014")),
        "ux_required": text_value(fields.get("customfield_10135")),
        "start_date": _extract_start_date(fields),
        "change_type": text_value(fields.get("customfield_10005")),
        "change_risk": text_value(fields.get("customfield_10006")),
        "change_reason": text_value(fields.get("customfield_10007")),
        "actual_start": parse_dt(fields.get("customfield_10008")),
        "customer_priority": text_value(fields.get("customfield_10129")),
        "actual_end": parse_dt(fields.get("customfield_10009")),
        "team_id": team_id,
        "team_name": team_name,
        "customers": option_values(fields.get("customfield_10123")) or None,
        "labels": option_values(fields.get("labels")) or None,
        "components": named_values(fields.get("components")) or None,
        "affects_versions": named_values(fields.get("versions")) or None,
        "fix_versions": named_values(fields.get("fixVersions")) or None,
        "raw_required_fields_json": required,
    }


def extract_sprints(fields: dict[str, Any]) -> list[dict[str, Any]]:
    raw = fields.get("customfield_10020")
    if not isinstance(raw, list):
        return []
    sprints: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        sprints.append(
            {
                "jira_sprint_id": int(item["id"]),
                "name": str(item.get("name") or "").strip() or None,
                "state": str(item.get("state") or "").strip() or None,
                "board_id": item.get("boardId") if isinstance(item.get("boardId"), int) else None,
                "goal": str(item.get("goal") or "").strip() or None,
                "start_date": parse_dt(item.get("startDate")),
                "end_date": parse_dt(item.get("endDate")),
                "complete_date": parse_dt(item.get("completeDate")),
                "raw_json": item,
            }
        )
    return sprints


def extract_worklog(raw: dict[str, Any]) -> dict[str, Any] | None:
    worklog_id = str(raw.get("id") or "").strip()
    seconds = raw.get("timeSpentSeconds")
    if not worklog_id or not isinstance(seconds, int):
        return None
    author = user_identity(raw.get("author"))
    comment = raw.get("comment")
    return {
        "jira_worklog_id": worklog_id,
        "author": author,
        "author_account_id": author["account_id"] if author else None,
        "author_display_name": author["display_name"] if author else None,
        "author_email_address": author["email_address"] if author else None,
        "comment_text": adf_to_text(comment),
        "comment_adf": comment if isinstance(comment, dict) else None,
        "created_at_jira": parse_dt(raw.get("created")),
        "updated_at_jira": parse_dt(raw.get("updated")),
        "started_at": parse_dt(raw.get("started")),
        "time_spent_seconds": seconds,
        "raw_json": raw,
    }


def extract_status_transitions(histories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for history in histories:
        changed_at = parse_dt(history.get("created"))
        history_id = str(history.get("id") or "").strip()
        if changed_at is None or not history_id:
            continue
        author = user_identity(history.get("author"))
        items = history.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict) or str(item.get("field") or "").lower() != "status":
                continue
            rows.append(
                {
                    "jira_history_id": history_id,
                    "history_item_index": index,
                    "changed_at": changed_at,
                    "author": author,
                    "changed_by_display_name": author["display_name"] if author else None,
                    "from_status_id": str(item.get("from") or "").strip() or None,
                    "from_status_name": str(item.get("fromString") or "").strip() or None,
                    "to_status_id": str(item.get("to") or "").strip() or None,
                    "to_status_name": str(item.get("toString") or "").strip() or None,
                    "raw_item_json": item,
                }
            )
    return rows


def _is_pmgt_issue_key(key: str | None) -> bool:
    return bool(key and key.upper().startswith("PMGT-"))


def extract_relations(raw_issue: dict[str, Any]) -> list[RelationPayload]:
    fields = raw_issue.get("fields")
    if not isinstance(fields, dict):
        return []
    source_key = str(raw_issue.get("key") or "").strip() or None
    relations: list[RelationPayload] = []
    parent = fields.get("parent")
    if isinstance(parent, dict):
        relations.append(
            RelationPayload(
                target_key=str(parent.get("key") or "").strip() or None,
                target_jira_issue_id=str(parent.get("id") or "").strip() or None,
                relation_source="parent",
                direction="outward",
                link_type_name="Parent",
                is_hierarchy_edge=True,
                is_feature_membership_edge=True,
                raw_json=parent,
            )
        )
    for subtask in fields.get("subtasks") if isinstance(fields.get("subtasks"), list) else []:
        if isinstance(subtask, dict):
            relations.append(
                RelationPayload(
                    target_key=str(subtask.get("key") or "").strip() or None,
                    target_jira_issue_id=str(subtask.get("id") or "").strip() or None,
                    relation_source="subtask",
                    direction="outward",
                    link_type_name="Subtask",
                    is_hierarchy_edge=True,
                    is_feature_membership_edge=True,
                    raw_json=subtask,
                )
            )
    epic_key = text_value(fields.get("customfield_10014"))
    if epic_key:
        relations.append(
            RelationPayload(
                target_key=epic_key,
                target_jira_issue_id=None,
                relation_source="epic_link",
                direction="outward",
                link_type_name="Epic Link",
                is_hierarchy_edge=True,
                is_feature_membership_edge=True,
            )
        )
    for link in fields.get("issuelinks") if isinstance(fields.get("issuelinks"), list) else []:
        if not isinstance(link, dict):
            continue
        link_type = link.get("type") if isinstance(link.get("type"), dict) else {}
        for direction, issue_key in (("outward", "outwardIssue"), ("inward", "inwardIssue")):
            target = link.get(issue_key)
            if not isinstance(target, dict):
                continue
            link_name = str(link_type.get("name") or "").strip()
            target_key = str(target.get("key") or "").strip() or None
            pmgt_edge = _is_pmgt_issue_key(source_key) or _is_pmgt_issue_key(target_key)
            relations.append(
                RelationPayload(
                    target_key=target_key,
                    target_jira_issue_id=str(target.get("id") or "").strip() or None,
                    relation_source="connected_pmgt_issue" if pmgt_edge else "issue_link",
                    jira_link_id=str(link.get("id") or "").strip() or None,
                    link_type_id=str(link_type.get("id") or "").strip() or None,
                    link_type_name=link_name,
                    direction=direction,
                    inward_description=str(link_type.get("inward") or "").strip() or None,
                    outward_description=str(link_type.get("outward") or "").strip() or None,
                    is_hierarchy_edge=pmgt_edge,
                    is_feature_membership_edge=link_name.lower() not in {"duplicates", "relates"},
                    raw_json=link,
                )
            )
    return [
        relation for relation in relations if relation.target_key or relation.target_jira_issue_id
    ]


def extract_field_values(
    fields: dict[str, Any],
    names: dict[str, Any] | None,
    schema: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    max_indexed_text_len = 1000
    for field_id, value in fields.items():
        schema_payload = schema.get(field_id) if isinstance(schema, dict) else {}
        field_name = str(names.get(field_id) or "").strip() if isinstance(names, dict) else None
        row: dict[str, Any] = {
            "field_id": field_id,
            "field_name": field_name or None,
            "schema_type": str(schema_payload.get("type") or "").strip()
            if isinstance(schema_payload, dict)
            else None,
            "schema_custom": str(schema_payload.get("custom") or "").strip()
            if isinstance(schema_payload, dict)
            else None,
            "value_text": None,
            "value_number": None,
            "value_date": None,
            "value_datetime": None,
            "value_json": value if isinstance(value, dict | list) else None,
        }
        if isinstance(value, str):
            row["value_text"] = value[:max_indexed_text_len]
            row["value_date"] = parse_date(value)
            row["value_datetime"] = parse_dt(value)
        elif isinstance(value, int | float):
            try:
                row["value_number"] = Decimal(str(value))
            except InvalidOperation:
                row["value_number"] = None
        elif isinstance(value, bool):
            row["value_text"] = str(value).lower()
        elif isinstance(value, dict | list):
            # Keep bulky Jira payloads queryable via JSON without blowing up the btree text index.
            preview = text_value(value)
            row["value_text"] = (
                preview[:max_indexed_text_len]
                if preview and len(preview) <= max_indexed_text_len
                else None
            )
        else:
            row["value_text"] = text_value(value)
        rows.append(row)
    return rows
