from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import SessionDep, require_admin_session
from app.schemas.people_data_user import (
    PeopleDataUserCreate,
    PeopleDataUserItem,
    PeopleDataUserListResponse,
    PeopleDataUserPatch,
)
from app.services.admin_people_data_users_service import (
    create_people_data_user,
    delete_people_data_user,
    list_people_data_users,
    patch_people_data_user,
)

router = APIRouter()
AdminSessionDep = Annotated[None, Depends(require_admin_session)]


@router.get("/people-data-users", response_model=PeopleDataUserListResponse)
def get_people_data_users(
    _auth: AdminSessionDep,
    db: SessionDep,
) -> PeopleDataUserListResponse:
    return list_people_data_users(db)


@router.post(
    "/people-data-users",
    response_model=PeopleDataUserItem,
    status_code=status.HTTP_201_CREATED,
)
def post_people_data_user(
    body: PeopleDataUserCreate,
    request: Request,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> PeopleDataUserItem:
    try:
        item = create_people_data_user(
            db,
            body,
            created_by=str(request.session.get("username") or ""),
        )
        db.commit()
        return item
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/people-data-users/{user_id}", response_model=PeopleDataUserItem)
def patch_people_data_user_endpoint(
    user_id: int,
    body: PeopleDataUserPatch,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> PeopleDataUserItem:
    try:
        item = patch_people_data_user(db, user_id, body)
        db.commit()
        return item
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/people-data-users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_people_data_user_endpoint(
    user_id: int,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> Response:
    try:
        delete_people_data_user(db, user_id)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from None
