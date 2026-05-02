from __future__ import annotations

import logging

from app.db.connection import get_connection
from app.schemas.document import DocumentRead
from app.services.chunker import DEFAULT_CHUNK_SIZE, split_markdown
from app.services.embeddings import embed_text


logger = logging.getLogger(__name__)


def split_text(text: str, max_chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    return split_markdown(text, max_chunk_size=max_chunk_size)


def load_document(document_id: int) -> DocumentRead | None:
    with get_connection() as conn, conn.cursor() as cur:
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


def create_document(title: str, content: str, source_filename: str | None) -> tuple[int, int]:
    title = title.strip() or "未命名文档"
    content = content.strip()
    if not content:
        raise ValueError("文档内容为空")

    chunks = split_text(content)
    if not chunks:
        raise ValueError("切分后没有可用片段")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (title, source_filename, content)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (title, source_filename, content),
            )
            document_id = cur.fetchone()[0]

            for index, chunk in enumerate(chunks):
                cur.execute(
                    """
                    INSERT INTO document_chunks (document_id, chunk_index, content)
                    VALUES (%s, %s, %s)
                    """,
                    (document_id, index, chunk),
                )
        conn.commit()

    return document_id, len(chunks)


def sync_document_embeddings(document_id: int) -> None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content
                FROM document_chunks
                WHERE document_id = %s AND embedding IS NULL
                ORDER BY chunk_index
                """,
                (document_id,),
            )
            rows = cur.fetchall()
            for chunk_id, content in rows:
                vec = embed_text(content)
                cur.execute(
                    "UPDATE document_chunks SET embedding = %s WHERE id = %s",
                    (vec, chunk_id),
                )
                conn.commit()
    except Exception as exc:
        logger.warning("sync_document_embeddings failed for doc=%s: %s", document_id, exc)


def rechunk_document(document_id: int) -> int:
    """Re-split an existing document into chunks using current split_text rules,
    deleting old chunks and embeddings. Returns new chunk count.
    Caller should trigger sync_document_embeddings afterwards.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT content FROM documents WHERE id = %s", (document_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Document {document_id} not found")
        content = row[0]

        chunks = split_text(content)
        if not chunks:
            raise ValueError("切分后没有可用片段")

        cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))

        for index, chunk in enumerate(chunks):
            cur.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, content)
                VALUES (%s, %s, %s)
                """,
                (document_id, index, chunk),
            )
        conn.commit()

    return len(chunks)
