from datetime import datetime

from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.schemas.common import PageResponse
from app.schemas.poem import PoemRead


class CollectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None)


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(CollectionBase):
    pass


class CollectionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None)

    def to_update_data(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class CollectionRead(CollectionBase):
    id: int
    created_at: datetime


class CollectionListResponse(PageResponse[CollectionRead]):
    pass


class CollectionPoemCreate(BaseModel):
    poem_id: int = Field(gt=0)


class CollectionPoemReplace(BaseModel):
    poem_ids: list[Annotated[int, Field(gt=0)]]


class CollectionPoemRead(BaseModel):
    collection_id: int
    poem: PoemRead
    created_at: datetime


class CollectionPoemListResponse(PageResponse[CollectionPoemRead]):
    pass
