from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.document import DocumentRead

MAX_IMPORT_AUTHORS = 1000
MAX_IMPORT_POEMS = 5000
MAX_IMPORT_COLLECTIONS = 1000
MAX_IMPORT_RELATIONS = 10000


def clean_required_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


class ImportAuthorInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bio: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class ImportPoemRefInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("author")
    @classmethod
    def validate_author(cls, value: str) -> str:
        return clean_required_text(value)


class ImportPoemInput(ImportPoemRefInput):
    content: str = Field(min_length=1)
    collections: list[str] = Field(default_factory=list, max_length=MAX_IMPORT_RELATIONS)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("collections")
    @classmethod
    def validate_collections(cls, value: list[str]) -> list[str]:
        return [clean_required_text(item) for item in value if item.strip()]


class ImportCollectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    poems: list[ImportPoemRefInput] = Field(default_factory=list, max_length=MAX_IMPORT_RELATIONS)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class BatchImportRequest(BaseModel):
    authors: list[ImportAuthorInput] = Field(default_factory=list, max_length=MAX_IMPORT_AUTHORS)
    poems: list[ImportPoemInput] = Field(default_factory=list, max_length=MAX_IMPORT_POEMS)
    collections: list[ImportCollectionInput] = Field(default_factory=list, max_length=MAX_IMPORT_COLLECTIONS)


class BatchImportCount(BaseModel):
    created: int = 0
    matched: int = 0
    skipped: int = 0


class BatchImportSummary(BaseModel):
    authors: BatchImportCount = Field(default_factory=BatchImportCount)
    poems: BatchImportCount = Field(default_factory=BatchImportCount)
    collections: BatchImportCount = Field(default_factory=BatchImportCount)
    collection_poems: BatchImportCount = Field(default_factory=BatchImportCount)


class BatchImportWarning(BaseModel):
    code: str
    path: str
    message: str


class BatchImportResponse(BaseModel):
    summary: BatchImportSummary
    warnings: list[BatchImportWarning] = Field(default_factory=list)


class UnifiedImportRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source_filename: str | None = Field(default=None, max_length=200)
    batch_payload: BatchImportRequest | None = None
    extract_poems: bool = True
    max_extracted_poems: int = Field(default=80, ge=1, le=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("source_filename")
    @classmethod
    def validate_source_filename(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class UnifiedImportExtractionResult(BaseModel):
    attempted: bool
    source: Literal["batch_payload", "llm", "skipped", "unavailable", "failed"]
    extracted_poem_count: int = 0
    imported: BatchImportResponse | None = None
    warnings: list[BatchImportWarning] = Field(default_factory=list)


class UnifiedImportResponse(BaseModel):
    document: DocumentRead
    extraction: UnifiedImportExtractionResult
