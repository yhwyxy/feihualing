from datetime import datetime

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ErrorResponse, MessageResponse, PageResponse


class PoemBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class PoemCreate(PoemBase):
    author_id: int = Field(gt=0)


class PoemUpdate(PoemBase):
    author_id: int = Field(gt=0)


class PoemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    author_id: int | None = Field(default=None, gt=0)

    def to_update_data(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class PoemRead(PoemBase):
    id: int
    author_id: int
    author: str
    created_at: datetime


class PoemListResponse(PageResponse[PoemRead]):
    pass
