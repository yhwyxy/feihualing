from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PageResponse


class AuthorBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bio: str | None = Field(default=None)


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(AuthorBase):
    pass


class AuthorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None)


class AuthorRead(AuthorBase):
    id: int
    created_at: datetime


class AuthorListResponse(PageResponse[AuthorRead]):
    pass
