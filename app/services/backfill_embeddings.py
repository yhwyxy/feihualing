from __future__ import annotations

from app.db.connection import get_connection
from app.services.embeddings import (
    compose_author_text,
    compose_collection_text,
    compose_poem_text,
    embed_text,
)


def backfill_poems(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.title, COALESCE(a.name, ''), p.content
            FROM poems p
            LEFT JOIN authors a ON a.id = p.author_id
            WHERE p.embedding IS NULL
            ORDER BY p.id
            """
        )
        rows = cur.fetchall()

    total = len(rows)
    for idx, (poem_id, title, author_name, content) in enumerate(rows, start=1):
        text = compose_poem_text(title or "", author_name or "", content or "")
        if not text:
            continue
        vec = embed_text(text)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE poems SET embedding = %s WHERE id = %s",
                (vec, poem_id),
            )
        conn.commit()
        print(f"[poems] {idx}/{total} id={poem_id} {title[:30]}")
    return total


def backfill_authors(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, bio
            FROM authors
            WHERE embedding IS NULL
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    total = len(rows)
    for idx, (author_id, name, bio) in enumerate(rows, start=1):
        text = compose_author_text(name or "", bio)
        if not text:
            continue
        vec = embed_text(text)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE authors SET embedding = %s WHERE id = %s",
                (vec, author_id),
            )
        conn.commit()
        print(f"[authors] {idx}/{total} id={author_id} {name}")
    return total


def backfill_collections(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, description
            FROM collections
            WHERE embedding IS NULL
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    total = len(rows)
    for idx, (collection_id, name, description) in enumerate(rows, start=1):
        text = compose_collection_text(name or "", description)
        if not text:
            continue
        vec = embed_text(text)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE collections SET embedding = %s WHERE id = %s",
                (vec, collection_id),
            )
        conn.commit()
        print(f"[collections] {idx}/{total} id={collection_id} {name}")
    return total


def main() -> None:
    with get_connection() as conn:
        poems = backfill_poems(conn)
        authors = backfill_authors(conn)
        collections = backfill_collections(conn)
    print(f"\ndone: poems={poems}, authors={authors}, collections={collections}")


if __name__ == "__main__":
    main()
