from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.connection import get_connection
from app.schemas.author import (
    AuthorCreate,
    AuthorDynastyRead,
    AuthorDynastyUpdate,
    AuthorListResponse,
    AuthorPatch,
    AuthorRead,
    AuthorUpdate,
)
from app.schemas.poem import MessageResponse, PoemListResponse, PoemRead
from app.services.embeddings import sync_author_embedding

router = APIRouter()


def serialize_author(row) -> AuthorRead:
    return AuthorRead(
        id=row[0],
        name=row[1],
        bio=row[2],
        created_at=row[3],
    )


def serialize_author_poem(row) -> PoemRead:
    return PoemRead(
        id=row[0],
        title=row[1],
        author_id=row[2],
        author=row[3],
        content=row[4],
        created_at=row[5],
    )


@router.get(
    "/authors",
    tags=["authors"],
    response_model=AuthorListResponse,
    summary="获取作者列表",
)
def list_authors(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    base_query = """
        FROM authors
    """
    params: list[object] = []
    conditions: list[str] = []

    if keyword:
        conditions.append("name ILIKE %s")
        params.append(f"%{keyword}%")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    list_query = (
        "SELECT id, name, bio, created_at"
        + base_query
        + " ORDER BY id ASC LIMIT %s OFFSET %s"
    )
    count_query = "SELECT COUNT(*)" + base_query

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_query, params)
            total = cur.fetchone()[0]

            cur.execute(list_query, [*params, limit, offset])
            rows = cur.fetchall()

    return AuthorListResponse(
        items=[serialize_author(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/authors/{author_id}/poems",
    tags=["authors"],
    response_model=PoemListResponse,
    summary="获取作者名下诗词",
)
def list_author_poems(
    author_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM authors WHERE id = %s", (author_id,))
            author_row = cur.fetchone()
            if author_row is None:
                raise HTTPException(status_code=404, detail="Author not found")

            cur.execute("SELECT COUNT(*) FROM poems WHERE author_id = %s", (author_id,))
            total = cur.fetchone()[0]

            cur.execute(
                """
                SELECT p.id, p.title, p.author_id, a.name, p.content, p.created_at
                FROM poems p
                JOIN authors a ON a.id = p.author_id
                WHERE p.author_id = %s
                ORDER BY p.id ASC
                LIMIT %s OFFSET %s
                """,
                (author_id, limit, offset),
            )
            rows = cur.fetchall()

    return PoemListResponse(
        items=[serialize_author_poem(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/authors/{author_id}",
    tags=["authors"],
    response_model=AuthorRead,
    summary="获取作者详情",
)
def get_author(author_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, bio, created_at
                FROM authors
                WHERE id = %s
                """,
                (author_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Author not found")

    return serialize_author(row)


@router.get(
    "/authors/{author_id}/dynasty",
    tags=["authors"],
    response_model=AuthorDynastyRead,
    summary="获取作者朝代关联",
)
def get_author_dynasty(author_id: int):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM authors WHERE id = %s", (author_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Author not found")

        cur.execute(
            """
            SELECT c.id, c.name
            FROM author_concepts ac
            JOIN concepts c ON c.id = ac.concept_id
            WHERE ac.author_id = %s AND c.type = 'dynasty'
            ORDER BY ac.updated_at DESC NULLS LAST, ac.created_at DESC
            LIMIT 1
            """,
            (author_id,),
        )
        row = cur.fetchone()

    return AuthorDynastyRead(
        author_id=author_id,
        concept_id=row[0] if row else None,
        name=row[1] if row else None,
    )


@router.put(
    "/authors/{author_id}/dynasty",
    tags=["authors"],
    response_model=AuthorDynastyRead,
    summary="设置作者朝代关联",
)
def set_author_dynasty(author_id: int, payload: AuthorDynastyUpdate):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM authors WHERE id = %s", (author_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Author not found")

        cur.execute(
            "SELECT id, name FROM concepts WHERE id = %s AND type = 'dynasty' AND is_active = true",
            (payload.concept_id,),
        )
        concept_row = cur.fetchone()
        if concept_row is None:
            raise HTTPException(status_code=404, detail="Dynasty concept not found")

        cur.execute(
            """
            DELETE FROM author_concepts
            USING concepts
            WHERE author_concepts.concept_id = concepts.id
              AND author_concepts.author_id = %s
              AND concepts.type = 'dynasty'
            """,
            (author_id,),
        )
        cur.execute(
            """
            INSERT INTO author_concepts (author_id, concept_id, source)
            VALUES (%s, %s, 'manual')
            ON CONFLICT (author_id, concept_id)
            DO UPDATE SET source = 'manual', updated_at = now()
            """,
            (author_id, payload.concept_id),
        )
        conn.commit()

    return AuthorDynastyRead(author_id=author_id, concept_id=concept_row[0], name=concept_row[1])


@router.delete(
    "/authors/{author_id}/dynasty",
    tags=["authors"],
    response_model=MessageResponse,
    summary="删除作者朝代关联",
)
def delete_author_dynasty(author_id: int):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM authors WHERE id = %s", (author_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Author not found")

        cur.execute(
            """
            DELETE FROM author_concepts
            USING concepts
            WHERE author_concepts.concept_id = concepts.id
              AND author_concepts.author_id = %s
              AND concepts.type = 'dynasty'
            """,
            (author_id,),
        )
        conn.commit()

    return MessageResponse(message="Author dynasty deleted")


@router.post(
    "/authors",
    tags=["authors"],
    response_model=AuthorRead,
    summary="新增作者",
)
def create_author(author: AuthorCreate, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO authors (name, bio)
                VALUES (%s, %s)
                RETURNING id, name, bio, created_at
                """,
                (author.name, author.bio),
            )
            row = cur.fetchone()
        conn.commit()

    background_tasks.add_task(sync_author_embedding, row[0])

    return serialize_author(row)


@router.put(
    "/authors/{author_id}",
    tags=["authors"],
    response_model=AuthorRead,
    summary="更新作者",
)
def update_author(author_id: int, author: AuthorUpdate, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE authors
                SET name = %s, bio = %s
                WHERE id = %s
                RETURNING id, name, bio, created_at
                """,
                (author.name, author.bio, author_id),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Author not found")

    background_tasks.add_task(sync_author_embedding, row[0])

    return serialize_author(row)


@router.patch(
    "/authors/{author_id}",
    tags=["authors"],
    response_model=AuthorRead,
    summary="局部更新作者",
)
def patch_author(author_id: int, author: AuthorPatch, background_tasks: BackgroundTasks):
    update_data = author.model_dump(exclude_none=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    assignments = ", ".join(f"{field} = %s" for field in update_data)
    params = list(update_data.values())
    params.append(author_id)

    query = f"""
        UPDATE authors
        SET {assignments}
        WHERE id = %s
        RETURNING id, name, bio, created_at
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Author not found")

    background_tasks.add_task(sync_author_embedding, row[0])

    return serialize_author(row)


@router.delete(
    "/authors/{author_id}",
    tags=["authors"],
    response_model=MessageResponse,
    summary="删除作者",
)
def delete_author(author_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM poems WHERE author_id = %s", (author_id,))
            poem_count = cur.fetchone()[0]
            if poem_count > 0:
                raise HTTPException(status_code=409, detail="Author still has poems")

            cur.execute(
                "DELETE FROM authors WHERE id = %s RETURNING id",
                (author_id,),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Author not found")

    return MessageResponse(message="Author deleted")
