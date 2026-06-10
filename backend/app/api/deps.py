from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.database import SessionLocal
from app.models.people_data_user import PeopleDataUser
from app.services.config_service import load_runtime_config


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
SessionDep = DbSession


def require_admin_session(request: Request) -> None:
    if not request.session.get("admin"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid admin session is required",
        )


def has_people_data_access(request: Request, db: Session | None = None) -> bool:
    if request.session.get("admin"):
        return True
    user_id = request.session.get("people_data_user_id")
    if not user_id:
        return False
    if db is None:
        return True
    user = db.execute(
        select(PeopleDataUser).where(PeopleDataUser.id == int(user_id))
    ).scalar_one_or_none()
    return bool(user and user.is_active)


def require_people_data_access(request: Request, db: DbSession) -> None:
    if not has_people_data_access(request, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid people-data session is required",
        )

def get_runtime_settings(db: DbSession) -> ConfigurationSchema:
    return load_runtime_config(db=db).settings


RuntimeSettingsDep = Annotated[ConfigurationSchema, Depends(get_runtime_settings)]
