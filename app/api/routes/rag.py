from __future__ import annotations

import json
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI

from app.core.config import settings
from app.db.connection import get_connection
from app.schemas.rag import (
    RagAskRequest,
    RagAuthorHit,
    RagCollectionHit,
    RagDocumentChunkHit,
    RagPoemHit,
    RagSearchRequest,
    RagSearchResponse,
)
from app.services.embeddings import EmbeddingError, embed_text
from app.services.hybrid_search import (
    build_or_tsquery,
    hybrid_search_authors,
    hybrid_search_collections,
    hybrid_search_document_chunks,
    hybrid_search_poems,
)


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RagSearchResponse)
def rag_search(payload: RagSearchRequest) -> RagSearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="查询不能为空")

    try:
        vec = embed_text(query)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=f"Embedding 服务不可用: {exc}") from exc

    with get_connection() as conn, conn.cursor() as cur:
        or_tsq = build_or_tsquery(cur, query)

        rows = hybrid_search_poems(cur, vec, or_tsq, payload.top_k)
        poems = [
            RagPoemHit(
                id=row[0], title=row[1], content=row[2],
                author_id=row[3], author_name=row[4],
                sem_score=float(row[5]),
                kw_score=float(row[6]),
                score=float(row[7]),
            )
            for row in rows
        ]

        rows = hybrid_search_authors(cur, vec, or_tsq, payload.top_k)
        authors = [
            RagAuthorHit(
                id=row[0], name=row[1], bio=row[2],
                sem_score=float(row[3]),
                kw_score=float(row[4]),
                score=float(row[5]),
            )
            for row in rows
        ]

        rows = hybrid_search_collections(cur, vec, or_tsq, payload.top_k)
        collections = [
            RagCollectionHit(
                id=row[0], name=row[1], description=row[2],
                sem_score=float(row[3]),
                kw_score=float(row[4]),
                score=float(row[5]),
            )
            for row in rows
        ]

        rows = hybrid_search_document_chunks(cur, vec, or_tsq, payload.top_k)
        document_chunks = [
            RagDocumentChunkHit(
                chunk_id=row[0],
                document_id=row[1],
                document_title=row[2],
                chunk_index=row[3],
                content=row[4],
                sem_score=float(row[5]),
                kw_score=float(row[6]),
                score=float(row[7]),
            )
            for row in rows
        ]

    return RagSearchResponse(
        query=query,
        poems=poems,
        authors=authors,
        collections=collections,
        document_chunks=document_chunks,
    )


SYSTEM_PROMPT = (
    "你是一个古诗词问答助手。\n"
    "回答必须严格基于下方“参考诗词”和“参考文档”中出现的内容，不得编造参考中没有的信息。\n"
    "引用规则：\n"
    "  - 引用某首诗的内容或信息时，在该句末尾加标记 [poem:ID]，ID 对应参考诗词编号。\n"
    "  - 引用文档片段时，在该句末尾加标记 [doc:ID#IDX]，ID 是文档编号，IDX 是片段序号。\n"
    "如果参考中没有相关信息，请直接回答：暂无相关资料。\n"
    "用中文回答，简洁，不超过 200 字。"
)


def _build_user_prompt(
    query: str,
    poems: list[tuple],
    doc_chunks: list[tuple],
) -> str:
    sections: list[str] = []

    if poems:
        poem_blocks = []
        for pid, title, author, content in poems:
            poem_blocks.append(f"[poem:{pid}] 《{title}》({author or '佚名'})\n{content}")
        sections.append("参考诗词：\n" + "\n\n".join(poem_blocks))
    else:
        sections.append("参考诗词：\n（无）")

    if doc_chunks:
        doc_blocks = []
        for doc_id, chunk_idx, doc_title, content in doc_chunks:
            doc_blocks.append(
                f"[doc:{doc_id}#{chunk_idx}] 《{doc_title}》片段\n{content}"
            )
        sections.append("参考文档：\n" + "\n\n".join(doc_blocks))

    return "\n\n".join(sections) + f"\n\n问题：{query}"


def _sse(event: dict) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


def _stream_ask(
    query: str,
    poems: list[tuple],
    doc_chunks: list[tuple],
) -> Iterator[bytes]:
    sources = {
        "poems": [
            {"id": pid, "title": title, "author": author, "content": content}
            for pid, title, author, content in poems
        ],
        "document_chunks": [
            {
                "document_id": doc_id,
                "chunk_index": chunk_idx,
                "document_title": doc_title,
                "content": content,
            }
            for doc_id, chunk_idx, doc_title, content in doc_chunks
        ],
    }
    yield _sse({"type": "sources", "sources": sources})

    if not poems and not doc_chunks:
        yield _sse({"type": "delta", "text": "暂无相关资料。"})
        yield _sse({"type": "done"})
        return

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    try:
        stream = client.chat.completions.create(
            model=settings.dashscope_chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(query, poems, doc_chunks)},
            ],
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield _sse({"type": "delta", "text": delta})
    except Exception as exc:  # noqa: BLE001
        yield _sse({"type": "error", "message": f"LLM 调用失败: {exc}"})

    yield _sse({"type": "done"})


@router.post("/ask")
def rag_ask(payload: RagAskRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="查询不能为空")

    if not settings.dashscope_api_key:
        raise HTTPException(status_code=503, detail="未配置 DashScope API Key")

    try:
        vec = embed_text(query)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=f"Embedding 服务不可用: {exc}") from exc

    with get_connection() as conn, conn.cursor() as cur:
        or_tsq = build_or_tsquery(cur, query)

        poem_rows = hybrid_search_poems(cur, vec, or_tsq, payload.top_k)
        poems = [(row[0], row[1], row[4], row[2]) for row in poem_rows]
        # (id, title, author_name, content)

        doc_rows = hybrid_search_document_chunks(cur, vec, or_tsq, payload.top_k)
        doc_chunks = [(row[1], row[3], row[2], row[4]) for row in doc_rows]
        # (document_id, chunk_index, document_title, content)

    return StreamingResponse(
        _stream_ask(query, poems, doc_chunks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
