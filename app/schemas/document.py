from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    source_filename: str | None = Field(default=None, max_length=200)


class DocumentRead(BaseModel):
    id: int
    title: str
    source_filename: str | None
    chunk_count: int
    embedded_count: int
    created_at: datetime


class DocumentDetail(DocumentRead):
    content: str


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int


class DocumentChunkRead(BaseModel):
    id: int
    chunk_index: int
    content: str
    has_embedding: bool


class DocumentChunkListResponse(BaseModel):
    document_id: int
    items: list[DocumentChunkRead]
