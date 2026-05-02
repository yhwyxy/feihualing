from __future__ import annotations

import io
import json

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from pypdf import PdfReader

from app.core.config import settings
from app.schemas.imports import (
    BatchImportRequest,
    BatchImportResponse,
    BatchImportSummary,
    BatchImportWarning,
    UnifiedImportExtractionResult,
    UnifiedImportRequest,
    UnifiedImportResponse,
)
from app.services.documents import create_document, load_document, sync_document_embeddings
from app.services.embeddings import (
    sync_author_embedding,
    sync_collection_embedding,
    sync_poem_embedding,
)
from app.services.imports import BatchImportOutcome, import_batch_payload
from app.services.poem_extraction import extract_poems_from_text

router = APIRouter()

MAX_UNIFIED_FILE_SIZE = 50 * 1024 * 1024
TEXT_EXTENSIONS = {"txt", "md", "markdown"}
STRUCTURED_EXTENSIONS = {"json"}
PDF_EXTENSIONS = {"pdf"}


def schedule_import_embeddings(outcome: BatchImportOutcome, background_tasks: BackgroundTasks) -> None:
    for aid in outcome.created_author_ids:
        background_tasks.add_task(sync_author_embedding, aid)
    for cid in outcome.created_collection_ids:
        background_tasks.add_task(sync_collection_embedding, cid)
    for pid in outcome.created_poem_ids:
        background_tasks.add_task(sync_poem_embedding, pid)


@router.post(
    "/imports/batch",
    tags=["imports"],
    response_model=BatchImportResponse,
    summary="批量导入作者、诗词和合集",
)
def import_batch(payload: BatchImportRequest, background_tasks: BackgroundTasks):
    outcome = import_batch_payload(payload)
    schedule_import_embeddings(outcome, background_tasks)
    return outcome.response


def _import_structured_payload(payload: BatchImportRequest, background_tasks: BackgroundTasks) -> UnifiedImportExtractionResult:
    outcome = import_batch_payload(payload)
    schedule_import_embeddings(outcome, background_tasks)
    return UnifiedImportExtractionResult(
        attempted=True,
        source="batch_payload",
        extracted_poem_count=len(payload.poems),
        imported=outcome.response,
        warnings=outcome.response.warnings,
    )


def _extract_and_import(payload: UnifiedImportRequest, background_tasks: BackgroundTasks) -> UnifiedImportExtractionResult:
    if payload.batch_payload is not None:
        return _import_structured_payload(payload.batch_payload, background_tasks)

    if not payload.extract_poems:
        return UnifiedImportExtractionResult(attempted=False, source="skipped")

    if not settings.dashscope_api_key:
        return UnifiedImportExtractionResult(
            attempted=True,
            source="unavailable",
            warnings=[BatchImportWarning(
                code="llm_unavailable",
                path="dashscope_api_key",
                message="未配置 DashScope API Key，已仅导入 RAG 文档。",
            )],
        )

    extracted_payload, extraction_warnings = extract_poems_from_text(
        title=payload.title,
        content=payload.content,
        source_filename=payload.source_filename,
        max_poems=payload.max_extracted_poems,
    )
    if not extracted_payload.poems:
        return UnifiedImportExtractionResult(
            attempted=True,
            source="llm",
            extracted_poem_count=0,
            imported=BatchImportResponse(summary=BatchImportSummary()),
            warnings=extraction_warnings,
        )

    outcome = import_batch_payload(extracted_payload)
    schedule_import_embeddings(outcome, background_tasks)
    return UnifiedImportExtractionResult(
        attempted=True,
        source="llm",
        extracted_poem_count=len(extracted_payload.poems),
        imported=outcome.response,
        warnings=[*extraction_warnings, *outcome.response.warnings],
    )


def _run_unified_import(payload: UnifiedImportRequest, background_tasks: BackgroundTasks) -> UnifiedImportResponse:
    try:
        document_id, _ = create_document(
            title=payload.title,
            content=payload.content,
            source_filename=payload.source_filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(sync_document_embeddings, document_id)
    document = load_document(document_id)
    if document is None:
        raise HTTPException(status_code=500, detail="文档创建后未能读取")

    try:
        extraction = _extract_and_import(payload, background_tasks)
    except Exception as exc:  # noqa: BLE001
        extraction = UnifiedImportExtractionResult(
            attempted=True,
            source="failed",
            warnings=[BatchImportWarning(
                code="structured_import_failed",
                path="extraction",
                message=f"诗词抽取或入库失败，RAG 文档已保留：{exc}",
            )],
        )

    return UnifiedImportResponse(document=document, extraction=extraction)


@router.post(
    "/imports/unified",
    tags=["imports"],
    response_model=UnifiedImportResponse,
    summary="统一导入文档并尝试抽取诗词",
)
def import_unified(payload: UnifiedImportRequest, background_tasks: BackgroundTasks):
    return _run_unified_import(payload, background_tasks)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="无法识别文本编码，请使用 UTF-8 或 GB18030")


def _extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"# 第 {index} 页\n\n{text.strip()}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"PDF 解析失败：{exc}") from exc
    content = "\n\n".join(pages).strip()
    if not content:
        raise HTTPException(status_code=400, detail="PDF 未提取到文本，可能是扫描版图片 PDF")
    return content


def _parse_json_batch(raw_text: str) -> BatchImportRequest:
    try:
        return BatchImportRequest.model_validate(json.loads(raw_text))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="JSON 文件格式错误") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"JSON 导入结构不符合要求：{exc}") from exc


@router.post(
    "/imports/unified/file",
    tags=["imports"],
    response_model=UnifiedImportResponse,
    summary="上传文件并统一导入",
)
async def import_unified_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    extract_poems: bool = Form(default=True),
    max_extracted_poems: int = Form(default=80),
):
    data = await file.read()
    if len(data) > MAX_UNIFIED_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件不能超过 50MB")

    filename = file.filename or "uploaded"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    display_title = (title or filename.rsplit(".", 1)[0]).strip() or "未命名文档"
    batch_payload = None

    if ext in TEXT_EXTENSIONS:
        content = _decode_text(data)
    elif ext in STRUCTURED_EXTENSIONS:
        content = _decode_text(data)
        batch_payload = _parse_json_batch(content)
    elif ext in PDF_EXTENSIONS:
        content = _extract_pdf_text(data)
    else:
        raise HTTPException(status_code=400, detail="仅支持 txt / md / markdown / json / pdf 文件")

    payload = UnifiedImportRequest(
        title=display_title,
        content=content,
        source_filename=filename,
        batch_payload=batch_payload,
        extract_poems=extract_poems,
        max_extracted_poems=max_extracted_poems,
    )
    return _run_unified_import(payload, background_tasks)
