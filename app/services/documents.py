from __future__ import annotations

import logging

from app.db.connection import get_connection
from app.services.embeddings import embed_text


logger = logging.getLogger(__name__)


DEFAULT_CHUNK_SIZE = 400


def split_text(text: str, max_chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer.strip():
            chunks.append(buffer.strip())
        buffer = ""

    for para in paragraphs:
        if len(para) > max_chunk_size:
            flush()
            for start in range(0, len(para), max_chunk_size):
                chunks.append(para[start:start + max_chunk_size])
            continue

        if not buffer:
            buffer = para
        elif len(buffer) + len(para) + 2 <= max_chunk_size:
            buffer = f"{buffer}\n\n{para}"
        else:
            flush()
            buffer = para

    flush()
    return chunks


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
