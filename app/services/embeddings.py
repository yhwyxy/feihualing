from __future__ import annotations

import logging

import httpx
import numpy as np

from app.core.config import settings
from app.db.connection import get_connection


logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    pass


MAX_EMBED_CHARS = 500


def embed_text(text: str) -> np.ndarray:
    clean = text.strip()
    if len(clean) > MAX_EMBED_CHARS:
        logger.warning(
            "embed_text input truncated: %d -> %d chars",
            len(clean),
            MAX_EMBED_CHARS,
        )
        clean = clean[:MAX_EMBED_CHARS]

    url = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
    payload = {"model": settings.ollama_embed_model, "prompt": clean}
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"Ollama 调用失败: {exc}") from exc

    vec = data.get("embedding")
    if not vec:
        raise EmbeddingError(f"Ollama 返回缺少 embedding 字段: {data}")
    if len(vec) != settings.embedding_dim:
        raise EmbeddingError(
            f"向量维度不匹配: 期望 {settings.embedding_dim}, 实际 {len(vec)}"
        )
    return np.asarray(vec, dtype=np.float32)


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    return [embed_text(text) for text in texts]


def compose_poem_text(title: str, author: str, content: str) -> str:
    parts = [title.strip(), author.strip(), content.strip()]
    return "\n".join(part for part in parts if part)


def compose_author_text(name: str, bio: str | None) -> str:
    parts = [name.strip()]
    if bio and bio.strip():
        parts.append(bio.strip())
    return "\n".join(parts)


def compose_collection_text(name: str, description: str | None) -> str:
    parts = [name.strip()]
    if description and description.strip():
        parts.append(description.strip())
    return "\n".join(parts)


def sync_poem_embedding(poem_id: int) -> None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.title, COALESCE(a.name, ''), p.content
                FROM poems p LEFT JOIN authors a ON a.id = p.author_id
                WHERE p.id = %s
                """,
                (poem_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            text = compose_poem_text(row[0] or "", row[1] or "", row[2] or "")
            if not text:
                return
            vec = embed_text(text)
            cur.execute(
                "UPDATE poems SET embedding = %s WHERE id = %s",
                (vec, poem_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("sync_poem_embedding failed for id=%s: %s", poem_id, exc)


def sync_author_embedding(author_id: int) -> None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, bio FROM authors WHERE id = %s",
                (author_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            text = compose_author_text(row[0] or "", row[1])
            if not text:
                return
            vec = embed_text(text)
            cur.execute(
                "UPDATE authors SET embedding = %s WHERE id = %s",
                (vec, author_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("sync_author_embedding failed for id=%s: %s", author_id, exc)


def sync_collection_embedding(collection_id: int) -> None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, description FROM collections WHERE id = %s",
                (collection_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            text = compose_collection_text(row[0] or "", row[1])
            if not text:
                return
            vec = embed_text(text)
            cur.execute(
                "UPDATE collections SET embedding = %s WHERE id = %s",
                (vec, collection_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning(
            "sync_collection_embedding failed for id=%s: %s", collection_id, exc
        )

