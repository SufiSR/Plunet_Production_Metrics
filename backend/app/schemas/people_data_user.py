from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PeopleDataUserItem(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PeopleDataUserListResponse(BaseModel):
    items: list[PeopleDataUserItem]


class PeopleDataUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


class PeopleDataUserPatch(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None
