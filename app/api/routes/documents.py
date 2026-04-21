from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.connection import get_connection
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentChunkRead,
    DocumentCreate,
    DocumentDetail,
    DocumentListResponse,
    DocumentRead,
)
from app.schemas.poem import MessageResponse
from app.services.documents import create_document, sync_document_embeddings


router = APIRouter(prefix="/documents", tags=["documents"])


def _load_document(cur, document_id: int) -> DocumentRead | None:
    cur.execute(
        """
        SELECT d.id, d.title, d.source_filename, d.created_at,
               COALESCE(c.total, 0), COALESCE(c.embedded, 0)
        FROM documents d
        LEFT JOIN (
            SELECT document_id,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embedded
            FROM document_chunks
            GROUP BY document_id
        ) c ON c.document_id = d.id
        WHERE d.id = %s
        """,
        (document_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return DocumentRead(
        id=row[0],
        title=row[1],
        source_filename=row[2],
        created_at=row[3],
        chunk_count=row[4],
        embedded_count=row[5],
    )


@router.get("", response_model=DocumentListResponse, summary="获取文档列表")
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT d.id, d.title, d.source_filename, d.created_at,
                   COALESCE(c.total, 0), COALESCE(c.embedded, 0)
            FROM documents d
            LEFT JOIN (
                SELECT document_id,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embedded
                FROM document_chunks
                GROUP BY document_id
            ) c ON c.document_id = d.id
            ORDER BY d.id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        items = [
            DocumentRead(
                id=row[0],
                title=row[1],
                source_filename=row[2],
                created_at=row[3],
                chunk_count=row[4],
                embedded_count=row[5],
            )
            for row in cur.fetchall()
        ]

    return DocumentListResponse(items=items, total=total)


@router.get("/{document_id}", response_model=DocumentDetail, summary="获取文档详情")
def get_document(document_id: int):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.title, d.source_filename, d.content, d.created_at,
                   COALESCE(c.total, 0), COALESCE(c.embedded, 0)
            FROM documents d
            LEFT JOIN (
                SELECT document_id,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embedded
                FROM document_chunks
                GROUP BY document_id
            ) c ON c.document_id = d.id
            WHERE d.id = %s
            """,
            (document_id,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetail(
        id=row[0],
        title=row[1],
        source_filename=row[2],
        content=row[3],
        created_at=row[4],
        chunk_count=row[5],
        embedded_count=row[6],
    )


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="获取文档切分片段",
)
def list_document_chunks(document_id: int):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE id = %s", (document_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Document not found")

        cur.execute(
            """
            SELECT id, chunk_index, content, embedding IS NOT NULL
            FROM document_chunks
            WHERE document_id = %s
            ORDER BY chunk_index
            """,
            (document_id,),
        )
        items = [
            DocumentChunkRead(
                id=row[0], chunk_index=row[1], content=row[2], has_embedding=row[3]
            )
            for row in cur.fetchall()
        ]

    return DocumentChunkListResponse(document_id=document_id, items=items)


@router.post("", response_model=DocumentRead, summary="上传文档")
def upload_document(payload: DocumentCreate, background_tasks: BackgroundTasks):
    try:
        document_id, _ = create_document(
            title=payload.title,
            content=payload.content,
            source_filename=payload.source_filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(sync_document_embeddings, document_id)

    with get_connection() as conn, conn.cursor() as cur:
        document = _load_document(cur, document_id)

    if document is None:
        raise HTTPException(status_code=500, detail="文档创建后未能读取")

    return document


@router.delete("/{document_id}", response_model=MessageResponse, summary="删除文档")
def delete_document(document_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM documents WHERE id = %s RETURNING id",
                (document_id,),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return MessageResponse(message="Document deleted")
