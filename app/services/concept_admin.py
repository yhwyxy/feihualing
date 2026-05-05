from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from psycopg.rows import dict_row

from app.db.connection import get_connection
from app.services.concept_parser import normalize_term
from app.services.feihualing_tools import split_poem_lines


def list_concept_aliases(concept_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM concepts WHERE id = %s", (concept_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Concept not found")

        cur.execute(
            """
            SELECT id, concept_id, alias, normalized_alias, created_at
            FROM concept_aliases
            WHERE concept_id = %s
            ORDER BY id ASC
            """,
            (concept_id,),
        )
        return cur.fetchall()


def create_concept_alias(concept_id: int, alias: str) -> dict:
    normalized_alias = normalize_term(alias)
    if not normalized_alias:
        raise HTTPException(status_code=400, detail="alias is required")

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM concepts WHERE id = %s", (concept_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Concept not found")

        cur.execute(
            """
            INSERT INTO concept_aliases (concept_id, alias, normalized_alias)
            VALUES (%s, %s, %s)
            ON CONFLICT (concept_id, normalized_alias)
            DO UPDATE SET alias = EXCLUDED.alias
            RETURNING id, concept_id, alias, normalized_alias, created_at
            """,
            (concept_id, alias.strip(), normalized_alias),
        )
        row = cur.fetchone()
        conn.commit()
    return row


def delete_concept_alias(concept_id: int, alias_id: int) -> bool:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM concept_aliases
            WHERE id = %s AND concept_id = %s
            RETURNING id
            """,
            (alias_id, concept_id),
        )
        row = cur.fetchone()
        conn.commit()
    return row is not None


def _load_poem_line(poem_id: int, line_index: int) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT content FROM poems WHERE id = %s", (poem_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Poem not found")

    lines = split_poem_lines(row[0])
    if line_index < 0 or line_index >= len(lines):
        raise HTTPException(status_code=400, detail="line_index is out of range")
    return lines[line_index]


def _ensure_concept_exists(concept_id: int) -> tuple[str, Decimal]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT name FROM concepts WHERE id = %s AND is_active = true", (concept_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Concept not found")
    return row[0], Decimal("1.0000")


def _sync_poem_concept_aggregate(poem_id: int, concept_id: int) -> None:
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT matched_text, confidence, source
            FROM line_concepts
            WHERE poem_id = %s AND concept_id = %s
            ORDER BY line_index ASC, start_offset ASC
            """,
            (poem_id, concept_id),
        )
        rows = cur.fetchall()

        if not rows:
            cur.execute(
                "DELETE FROM poem_concepts WHERE poem_id = %s AND concept_id = %s",
                (poem_id, concept_id),
            )
            conn.commit()
            return

        matched_texts = sorted({row["matched_text"] for row in rows})
        matched_count = len(rows)
        confidence = max(row["confidence"] for row in rows)
        source = "manual" if any(row["source"] == "manual" for row in rows) else rows[0]["source"]

        cur.execute(
            """
            INSERT INTO poem_concepts (
                poem_id,
                concept_id,
                confidence,
                source,
                matched_count,
                matched_texts
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (poem_id, concept_id)
            DO UPDATE SET
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                matched_count = EXCLUDED.matched_count,
                matched_texts = EXCLUDED.matched_texts,
                updated_at = now()
            """,
            (poem_id, concept_id, confidence, source, matched_count, matched_texts),
        )
        conn.commit()


def create_manual_line_concept(
    poem_id: int,
    concept_id: int,
    line_index: int,
    matched_text: str | None,
    start_offset: int,
) -> None:
    concept_name, confidence = _ensure_concept_exists(concept_id)
    line_text = _load_poem_line(poem_id, line_index)
    matched_value = (matched_text or concept_name).strip()
    if not matched_value:
        raise HTTPException(status_code=400, detail="matched_text is required")
    if start_offset < 0 or start_offset > len(line_text):
        raise HTTPException(status_code=400, detail="start_offset is out of range")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO line_concepts (
                poem_id,
                concept_id,
                line_index,
                line_text,
                matched_text,
                start_offset,
                confidence,
                source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'manual')
            ON CONFLICT (poem_id, line_index, concept_id, matched_text, start_offset, source)
            DO UPDATE SET
                line_text = EXCLUDED.line_text,
                confidence = EXCLUDED.confidence,
                updated_at = now()
            """,
            (
                poem_id,
                concept_id,
                line_index,
                line_text,
                matched_value,
                start_offset,
                confidence,
            ),
        )
        conn.commit()

    _sync_poem_concept_aggregate(poem_id, concept_id)


def delete_manual_line_concept(
    poem_id: int,
    concept_id: int,
    line_index: int,
    matched_text: str,
    start_offset: int,
) -> bool:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM line_concepts
            WHERE poem_id = %s
              AND concept_id = %s
              AND line_index = %s
              AND matched_text = %s
              AND start_offset = %s
              AND source = 'manual'
            RETURNING id
            """,
            (poem_id, concept_id, line_index, matched_text, start_offset),
        )
        row = cur.fetchone()
        conn.commit()

    if row is None:
        return False

    _sync_poem_concept_aggregate(poem_id, concept_id)
    return True
