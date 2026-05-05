from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import PageResponse


ConceptType = Literal["char", "phrase", "place", "image", "theme", "dynasty"]
ConceptSource = Literal["parser", "manual", "import", "llm"]
ParseJobType = Literal["initial_parse", "reparse", "delete_cleanup", "batch_backfill"]
ParseJobStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]


class ConceptRead(BaseModel):
    id: int
    name: str
    normalized_name: str
    type: ConceptType
    description: str | None = None
    is_active: bool
    poem_count: int | None = None
    line_count: int | None = None
    created_at: datetime


class ConceptListResponse(PageResponse[ConceptRead]):
    pass


class ConceptAliasRead(BaseModel):
    id: int
    concept_id: int
    alias: str
    normalized_alias: str
    created_at: datetime


class ConceptAliasListResponse(BaseModel):
    concept_id: int
    aliases: list[ConceptAliasRead]


class ConceptAliasCreate(BaseModel):
    alias: str = Field(min_length=1)


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ConceptGraphLimits(BaseModel):
    limit_poems: int
    limit_lines: int


class ConceptGraphResponse(BaseModel):
    center: GraphNode
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    limits: ConceptGraphLimits
    truncated: bool = False


class LineConceptRead(BaseModel):
    line_index: int
    line_text: str
    matched_text: str
    start_offset: int
    source: ConceptSource


class PoemConceptRead(BaseModel):
    id: int
    name: str
    type: ConceptType
    confidence: Decimal
    source: ConceptSource
    matched_count: int
    matched_texts: list[str]
    lines: list[LineConceptRead] = Field(default_factory=list)


class PoemConceptsResponse(BaseModel):
    poem_id: int
    concepts: list[PoemConceptRead]


class ParseJobRead(BaseModel):
    id: int
    poem_id: int | None
    job_type: ParseJobType
    status: ParseJobStatus
    trigger_source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ParseLogRead(BaseModel):
    id: int
    job_id: int
    level: Literal["info", "warning", "error"]
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class ParseJobListResponse(PageResponse[ParseJobRead]):
    pass


class ParseJobDetailResponse(BaseModel):
    job: ParseJobRead
    logs: list[ParseLogRead]


class ParseJobScheduledResponse(BaseModel):
    message: str
    job_id: int
    poem_id: int
    status: ParseJobStatus


class ManualLineConceptCreate(BaseModel):
    concept_id: int = Field(gt=0)
    line_index: int = Field(ge=0)
    matched_text: str | None = None
    start_offset: int = Field(default=0, ge=0)


class FeihualingQueryConcept(BaseModel):
    id: int
    name: str
    type: ConceptType


class FeihualingQueryPoem(BaseModel):
    id: int
    title: str


class FeihualingQueryAuthor(BaseModel):
    id: int
    name: str


class FeihualingQueryItem(BaseModel):
    line: str
    line_index: int
    matched_text: str
    poem: FeihualingQueryPoem
    author: FeihualingQueryAuthor
    concepts: list[FeihualingQueryConcept] = Field(default_factory=list)


class FeihualingQueryResponse(BaseModel):
    keyword: str
    position: Literal["any", "start", "end"]
    items: list[FeihualingQueryItem]
    total: int
    limit: int
    offset: int
