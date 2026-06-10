from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.people_data_user import PeopleDataUser
from app.schemas.people_data_user import (
    PeopleDataUserCreate,
    PeopleDataUserItem,
    PeopleDataUserListResponse,
    PeopleDataUserPatch,
)
from app.services.people_data_password_service import hash_password


def normalize_people_data_username(username: str) -> str:
    normalized = username.strip().casefold()
    if not normalized:
        raise ValueError("Username is required")
    return normalized


def list_people_data_users(db: Session) -> PeopleDataUserListResponse:
    rows = db.execute(
        select(PeopleDataUser).order_by(PeopleDataUser.username_normalized.asc())
    ).scalars()
    return PeopleDataUserListResponse(items=[_item(row) for row in rows])


def create_people_data_user(
    db: Session,
    body: PeopleDataUserCreate,
    *,
    created_by: str | None,
) -> PeopleDataUserItem:
    username = body.username.strip()
    normalized = normalize_people_data_username(username)
    if _username_exists(db, normalized):
        raise ValueError("Username already exists")
    row = PeopleDataUser(
        username=username,
        username_normalized=normalized,
        password_hash=hash_password(body.password),
        is_active=True,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _item(row)


def patch_people_data_user(
    db: Session,
    user_id: int,
    body: PeopleDataUserPatch,
) -> PeopleDataUserItem:
    row = db.get(PeopleDataUser, user_id)
    if row is None:
        raise LookupError("people_data_user_not_found")
    if body.username is not None:
        username = body.username.strip()
        normalized = normalize_people_data_username(username)
        if normalized != row.username_normalized and _username_exists(db, normalized):
            raise ValueError("Username already exists")
        row.username = username
        row.username_normalized = normalized
    if body.password is not None:
        row.password_hash = hash_password(body.password)
    if body.is_active is not None:
        row.is_active = body.is_active
    db.flush()
    db.refresh(row)
    return _item(row)


def delete_people_data_user(db: Session, user_id: int) -> None:
    row = db.get(PeopleDataUser, user_id)
    if row is None:
        raise LookupError("people_data_user_not_found")
    db.delete(row)
    db.flush()


def _username_exists(db: Session, normalized: str) -> bool:
    return (
        db.execute(
            select(PeopleDataUser.id).where(PeopleDataUser.username_normalized == normalized)
        ).scalar_one_or_none()
        is not None
    )


def _item(row: PeopleDataUser) -> PeopleDataUserItem:
    return PeopleDataUserItem(
        id=row.id,
        username=row.username,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
