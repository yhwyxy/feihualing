from __future__ import annotations

from app.db.connection import get_connection
from app.services.concept_parser import normalize_term
from app.services.feihualing_tools import split_poem_lines


def _position_sql(position: str) -> str:
    if position == "start":
        return " AND lc.line_text LIKE %s"
    if position == "end":
        return " AND lc.line_text LIKE %s"
    return ""


def _position_param(keyword: str, position: str) -> str | None:
    if position == "start":
        return f"{keyword}%"
    if position == "end":
        return f"%{keyword}"
    return None


def find_concept_ids(keyword: str) -> list[int]:
    normalized = normalize_term(keyword)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM concepts
            WHERE is_active = true AND normalized_name = %s
            UNION
            SELECT c.id
            FROM concept_aliases a
            JOIN concepts c ON c.id = a.concept_id
            WHERE c.is_active = true AND a.normalized_alias = %s
            """,
            (normalized, normalized),
        )
        return [row[0] for row in cur.fetchall()]


def query_feihualing_lines(
    keyword: str,
    *,
    position: str,
    author: str | None,
    author_id: int | None,
    dynasty: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    concept_ids = find_concept_ids(keyword)
    if concept_ids:
        return _query_by_concepts(
            concept_ids,
            keyword=keyword,
            position=position,
            author=author,
            author_id=author_id,
            dynasty=dynasty,
            limit=limit,
            offset=offset,
        )
    return _query_by_like(
        keyword,
        position=position,
        author=author,
        author_id=author_id,
        dynasty=dynasty,
        limit=limit,
        offset=offset,
    )


def _query_by_concepts(
    concept_ids: list[int],
    *,
    keyword: str,
    position: str,
    author: str | None,
    author_id: int | None,
    dynasty: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    base_query = """
        FROM line_concepts lc
        JOIN concepts c ON c.id = lc.concept_id
        JOIN poems p ON p.id = lc.poem_id
        LEFT JOIN authors a ON a.id = p.author_id
    """
    conditions = ["lc.concept_id = ANY(%s)"]
    params: list[object] = [concept_ids]

    position_filter = _position_sql(position)
    if position_filter:
        conditions.append(position_filter.removeprefix(" AND "))
        params.append(_position_param(keyword, position))
    if author:
        conditions.append("a.name ILIKE %s")
        params.append(f"%{author}%")
    if author_id is not None:
        conditions.append("p.author_id = %s")
        params.append(author_id)
    if dynasty:
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM author_concepts ac
                JOIN concepts dc ON dc.id = ac.concept_id
                WHERE ac.author_id = p.author_id
                  AND dc.type = 'dynasty'
                  AND dc.name = %s
            )
            """
        )
        params.append(dynasty)

    where_clause = " WHERE " + " AND ".join(conditions)
    count_query = "SELECT COUNT(*) " + base_query + where_clause
    list_query = (
        """
        SELECT
            lc.line_text,
            lc.line_index,
            lc.matched_text,
            p.id,
            p.title,
            a.id,
            COALESCE(a.name, '佚名'),
            c.id,
            c.name,
            c.type
        """
        + base_query
        + where_clause
        + " ORDER BY p.popularity_rank DESC, p.id ASC, lc.line_index ASC LIMIT %s OFFSET %s"
    )

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(count_query, params)
        total = cur.fetchone()[0]
        cur.execute(list_query, [*params, limit, offset])
        rows = cur.fetchall()

    return [
        {
            "line": row[0],
            "line_index": row[1],
            "matched_text": row[2],
            "poem": {"id": row[3], "title": row[4]},
            "author": {"id": row[5], "name": row[6]},
            "concepts": [{"id": row[7], "name": row[8], "type": row[9]}],
        }
        for row in rows
    ], total


def _query_by_like(
    keyword: str,
    *,
    position: str,
    author: str | None,
    author_id: int | None,
    dynasty: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    query = """
        SELECT p.id, p.title, p.author_id, COALESCE(a.name, '佚名'), p.content
        FROM poems p
        LEFT JOIN authors a ON a.id = p.author_id
        WHERE p.content LIKE %s
    """
    params: list[object] = [f"%{keyword}%"]
    if author:
        query += " AND a.name ILIKE %s"
        params.append(f"%{author}%")
    if author_id is not None:
        query += " AND p.author_id = %s"
        params.append(author_id)
    if dynasty:
        query += """
            AND EXISTS (
                SELECT 1
                FROM author_concepts ac
                JOIN concepts dc ON dc.id = ac.concept_id
                WHERE ac.author_id = p.author_id
                  AND dc.type = 'dynasty'
                  AND dc.name = %s
            )
        """
        params.append(dynasty)
    query += " ORDER BY p.popularity_rank DESC, p.id ASC LIMIT 200"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    matches: list[dict] = []
    for poem_id, title, row_author_id, author_name, content in rows:
        for line_index, line in enumerate(split_poem_lines(content)):
            if keyword not in line:
                continue
            if position == "start" and not line.startswith(keyword):
                continue
            if position == "end" and not line.endswith(keyword):
                continue
            matches.append(
                {
                    "line": line,
                    "line_index": line_index,
                    "matched_text": keyword,
                    "poem": {"id": poem_id, "title": title},
                    "author": {"id": row_author_id, "name": author_name},
                    "concepts": [],
                }
            )

    total = len(matches)
    return matches[offset : offset + limit], total
