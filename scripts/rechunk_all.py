"""一次性脚本：用新的 Markdown-aware chunker 重切所有已有文档，并重算 embedding。

运行：uv run python scripts/rechunk_all.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.connection import get_connection
from app.services.documents import rechunk_document, sync_document_embeddings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rechunk_all")


def main() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title FROM documents ORDER BY id")
        docs = cur.fetchall()

    logger.info("found %d documents", len(docs))
    for doc_id, title in docs:
        try:
            new_count = rechunk_document(doc_id)
            logger.info("rechunk doc=%s title=%r -> %d chunks", doc_id, title, new_count)
            sync_document_embeddings(doc_id)
            logger.info("embed doc=%s done", doc_id)
        except Exception as exc:
            logger.error("doc=%s failed: %s", doc_id, exc)


if __name__ == "__main__":
    main()
