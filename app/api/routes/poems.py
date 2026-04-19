from fastapi import APIRouter, HTTPException, Query

from app.db.connection import get_connection
from app.schemas.poem import (
    MessageResponse,
    PoemCreate,
    PoemListResponse,
    PoemPatch,
    PoemRead,
    PoemUpdate,
)

router = APIRouter()


def serialize_poem(row) -> PoemRead:
    return PoemRead(
        id=row[0],
        title=row[1],
        author_id=row[2],
        author=row[3],
        content=row[4],
        created_at=row[5],
    )


@router.get(
    "/poems",
    tags=["poems"],
    response_model=PoemListResponse,
    summary="获取诗词列表",
)
def list_poems(
    author_id: int | None = Query(default=None, gt=0),
    author_name: str | None = Query(default=None),
    collection_id: int | None = Query(default=None, gt=0),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    base_query = """
        FROM poems p
        JOIN authors a ON a.id = p.author_id
    """
    params: list[object] = []
    conditions: list[str] = []

    if author_id:
        conditions.append("p.author_id = %s")
        params.append(author_id)

    if author_name:
        conditions.append("a.name ILIKE %s")
        params.append(f"%{author_name}%")

    if collection_id:
        base_query += " JOIN collection_poems cp ON cp.poem_id = p.id"
        conditions.append("cp.collection_id = %s")
        params.append(collection_id)

    if keyword:
        conditions.append("p.title ILIKE %s")
        params.append(f"%{keyword}%")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    list_query = (
        "SELECT p.id, p.title, p.author_id, a.name, p.content, p.created_at"
        + base_query
        + " ORDER BY p.id ASC LIMIT %s OFFSET %s"
    )
    count_query = "SELECT COUNT(*)" + base_query

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_query, params)
            total = cur.fetchone()[0]

            cur.execute(list_query, [*params, limit, offset])
            rows = cur.fetchall()

    return PoemListResponse(
        items=[serialize_poem(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/poems/{poem_id}",
    tags=["poems"],
    response_model=PoemRead,
    summary="获取单首诗词详情",
)
def get_poem(poem_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.title, p.author_id, a.name, p.content, p.created_at
                FROM poems p
                JOIN authors a ON a.id = p.author_id
                WHERE p.id = %s
                """,
                (poem_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Poem not found")

    return serialize_poem(row)


@router.post(
    "/poems",
    tags=["poems"],
    response_model=PoemRead,
    summary="新增诗词",
)
def create_poem(poem: PoemCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM authors WHERE id = %s", (poem.author_id,))
            author_row = cur.fetchone()
            if author_row is None:
                raise HTTPException(status_code=404, detail="Author not found")

            cur.execute(
                """
                INSERT INTO poems (title, author_id, content)
                VALUES (%s, %s, %s)
                RETURNING id, title, author_id, content, created_at
                """,
                (poem.title, poem.author_id, poem.content),
            )
            row = cur.fetchone()
        conn.commit()

    return PoemRead(
        id=row[0],
        title=row[1],
        author_id=row[2],
        author=author_row[1],
        content=row[3],
        created_at=row[4],
    )


@router.put(
    "/poems/{poem_id}",
    tags=["poems"],
    response_model=PoemRead,
    summary="更新诗词",
)
def update_poem(poem_id: int, poem: PoemUpdate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM authors WHERE id = %s", (poem.author_id,))
            author_row = cur.fetchone()
            if author_row is None:
                raise HTTPException(status_code=404, detail="Author not found")

            cur.execute(
                """
                UPDATE poems
                SET title = %s, author_id = %s, content = %s
                WHERE id = %s
                RETURNING id, title, author_id, content, created_at
                """,
                (poem.title, poem.author_id, poem.content, poem_id),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Poem not found")

    return PoemRead(
        id=row[0],
        title=row[1],
        author_id=row[2],
        author=author_row[1],
        content=row[3],
        created_at=row[4],
    )


@router.patch(
    "/poems/{poem_id}",
    tags=["poems"],
    response_model=PoemRead,
    summary="局部更新诗词",
)
def patch_poem(poem_id: int, poem: PoemPatch):
    update_data = poem.to_update_data()

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        with conn.cursor() as cur:
            if "author_id" in update_data:
                cur.execute("SELECT id FROM authors WHERE id = %s", (update_data["author_id"],))
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail="Author not found")

            assignments = ", ".join(f"{field} = %s" for field in update_data)
            params = list(update_data.values())
            params.append(poem_id)

            query = f"""
                UPDATE poems
                SET {assignments}
                WHERE id = %s
                RETURNING id, title, author_id, content, created_at
            """
            cur.execute(query, params)
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Poem not found")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM authors WHERE id = %s", (row[2],))
            author_name = cur.fetchone()[0]

    return PoemRead(
        id=row[0],
        title=row[1],
        author_id=row[2],
        author=author_name,
        content=row[3],
        created_at=row[4],
    )


@router.delete(
    "/poems/{poem_id}",
    tags=["poems"],
    response_model=MessageResponse,
    summary="删除诗词",
)
def delete_poem(poem_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM poems WHERE id = %s RETURNING id",
                (poem_id,),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Poem not found")

    return MessageResponse(message="Poem deleted")
