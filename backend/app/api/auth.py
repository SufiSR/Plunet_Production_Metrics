from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import SessionDep, require_admin_session
from app.models.people_data_user import PeopleDataUser
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    PeopleDataChangePasswordRequest,
    PeopleDataLoginRequest,
    PeopleDataSessionResponse,
    UserRole,
)
from app.services.people_data_password_service import hash_password, verify_password

router = APIRouter()
AdminSessionDep = Annotated[None, Depends(require_admin_session)]


def _normalize_people_data_username(username: str) -> str:
    return username.strip().casefold()


def _admin_login_ok(username: str, password: str) -> bool:
    expected_user = (os.getenv("DORA_ADMIN_USERNAME") or "admin").strip()
    expected_password = (os.getenv("DORA_ADMIN_PASSWORD") or "").strip()
    if not expected_password:
        return False
    try:
        user_ok = secrets.compare_digest(
            username.encode("utf-8"), expected_user.encode("utf-8")
        )
        pass_ok = secrets.compare_digest(
            password.encode("utf-8"), expected_password.encode("utf-8")
        )
    except (AttributeError, TypeError):
        return False
    return bool(user_ok and pass_ok)


@router.post("/login", response_model=LoginResponse)
def login(request: Request, body: LoginRequest) -> LoginResponse:
    if not _admin_login_ok(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    request.session.clear()
    request.session["admin"] = True
    request.session["username"] = body.username
    return LoginResponse(role=UserRole.ADMIN, expires_at=None)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, _auth: AdminSessionDep) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/people-data/login", response_model=PeopleDataSessionResponse)
def people_data_login(
    request: Request,
    body: PeopleDataLoginRequest,
    db: SessionDep,
) -> PeopleDataSessionResponse:
    user = db.execute(
        select(PeopleDataUser).where(
            PeopleDataUser.username_normalized == _normalize_people_data_username(body.username)
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    request.session["people_data_user_id"] = user.id
    request.session["people_data_username"] = user.username
    return PeopleDataSessionResponse(authenticated=True, username=user.username)


@router.post("/people-data/logout", status_code=status.HTTP_204_NO_CONTENT)
def people_data_logout(request: Request) -> Response:
    request.session.pop("people_data_user_id", None)
    request.session.pop("people_data_username", None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/people-data/me", response_model=PeopleDataSessionResponse)
def people_data_me(request: Request, db: SessionDep) -> PeopleDataSessionResponse:
    if request.session.get("admin"):
        username = request.session.get("username")
        return PeopleDataSessionResponse(
            authenticated=True,
            username=str(username) if username is not None else "admin",
        )
    user_id = request.session.get("people_data_user_id")
    if not user_id:
        return PeopleDataSessionResponse(authenticated=False, username=None)
    user = db.get(PeopleDataUser, int(user_id))
    if user is None or not user.is_active:
        request.session.pop("people_data_user_id", None)
        request.session.pop("people_data_username", None)
        return PeopleDataSessionResponse(authenticated=False, username=None)
    return PeopleDataSessionResponse(authenticated=True, username=user.username)


@router.post("/people-data/change-password", response_model=PeopleDataSessionResponse)
def people_data_change_password(
    request: Request,
    body: PeopleDataChangePasswordRequest,
    db: SessionDep,
) -> PeopleDataSessionResponse:
    user_id = request.session.get("people_data_user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid people-data session is required",
        )
    user = db.get(PeopleDataUser, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid people-data session is required",
        )
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    try:
        user.password_hash = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return PeopleDataSessionResponse(authenticated=True, username=user.username)


@router.get("/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    if request.session.get("admin"):
        username = request.session.get("username")
        return MeResponse(
            role=UserRole.ADMIN,
            username=str(username) if username is not None else None,
        )
    return MeResponse(role=None, username=None)
