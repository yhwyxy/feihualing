from __future__ import annotations

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=20)


class RagPoemHit(BaseModel):
    id: int
    title: str
    content: str
    author_id: int | None
    author_name: str | None
    score: float
    sem_score: float = 0.0
    kw_score: float = 0.0


class RagAuthorHit(BaseModel):
    id: int
    name: str
    bio: str | None
    score: float
    sem_score: float = 0.0
    kw_score: float = 0.0


class RagCollectionHit(BaseModel):
    id: int
    name: str
    description: str | None
    score: float
    sem_score: float = 0.0
    kw_score: float = 0.0


class RagDocumentChunkHit(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    score: float
    sem_score: float = 0.0
    kw_score: float = 0.0


class RagSearchResponse(BaseModel):
    query: str
    poems: list[RagPoemHit]
    authors: list[RagAuthorHit]
    collections: list[RagCollectionHit]
    document_chunks: list[RagDocumentChunkHit]


class RagAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=10)
