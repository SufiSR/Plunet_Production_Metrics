from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jira_analytics.models import JiraUser

PLUNET_EMAIL_DOMAIN = "plunet.com"
# HRWorks appends this suffix to person ids for departed employees in working-times payloads.
_HRWORKS_DEPARTED_SUFFIX = re.compile(r"ausgeschieden\d+$", re.IGNORECASE)


def normalize_hrworks_response_email_key(email: str) -> str:
    """Strip HRWorks departed-employee suffixes so keys align with roster person ids."""
    key = email.strip().lower()
    return _HRWORKS_DEPARTED_SUFFIX.sub("", key)


def hrworks_response_email_matches_person(response_email: str, person_id: str) -> bool:
    """True when a working-times payload key belongs to the requested person."""
    response_key = normalize_hrworks_response_email_key(response_email)
    expected_key = to_hrworks_person_email(person_id).strip().lower()
    return response_key == expected_key


def to_hrworks_person_email(email: str) -> str:
    """Map Jira email to the HRworks persons identifier (local-part @plunet.com)."""
    normalized = email.strip().lower()
    local, separator, domain = normalized.partition("@")
    if not separator or not local or not domain:
        return normalized
    if domain == PLUNET_EMAIL_DOMAIN:
        return normalized
    return f"{local}@{PLUNET_EMAIL_DOMAIN}"


def build_hrworks_person_lookup(users: list[tuple[int, str]]) -> dict[str, int]:
    """HRworks person email -> jira_user_id (lowest id wins on duplicate HRworks keys)."""
    lookup: dict[str, int] = {}
    for user_id, jira_email in sorted(users, key=lambda item: item[0]):
        hrworks_email = to_hrworks_person_email(jira_email)
        if hrworks_email not in lookup:
            lookup[hrworks_email] = user_id
    return lookup


def load_jira_users_with_email(db: Session) -> list[tuple[int, str]]:
    """Jira users with non-empty account_id and one row per distinct email (lowest id wins)."""
    rows = db.execute(
        select(JiraUser.id, JiraUser.email_address, JiraUser.account_id)
        .where(JiraUser.email_address.is_not(None))
        .where(JiraUser.account_id.is_not(None))
        .order_by(JiraUser.id)
    ).all()
    by_email: dict[str, tuple[int, str]] = {}
    for user_id, email, account_id in rows:
        if not isinstance(email, str) or not isinstance(account_id, str):
            continue
        normalized_email = email.strip().lower()
        normalized_account_id = account_id.strip()
        if not normalized_email or not normalized_account_id:
            continue
        if normalized_email not in by_email:
            by_email[normalized_email] = (int(user_id), normalized_email)
    return list(by_email.values())
