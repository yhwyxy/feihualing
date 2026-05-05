from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.connection import get_connection
from app.schemas.collection import (
    CollectionCreate,
    CollectionListResponse,
    CollectionPatch,
    CollectionPoemCreate,
    CollectionPoemListResponse,
    CollectionPoemRead,
    CollectionPoemReplace,
    CollectionRead,
    CollectionUpdate,
)
from app.schemas.poem import MessageResponse, PoemRead
from app.services.embeddings import sync_collection_embedding

router = APIRouter()

COLLECTION_PATCH_FIELDS = {"name", "description"}


def serialize_collection(row) -> CollectionRead:
    return CollectionRead(
        id=row[0],
        name=row[1],
        description=row[2],
        created_at=row[3],
    )


def serialize_collection_poem(row) -> CollectionPoemRead:
    poem = PoemRead(
        id=row[2],
        title=row[3],
        author_id=row[4],
        author=row[5],
        content=row[6],
        created_at=row[7],
    )
    return CollectionPoemRead(
        collection_id=row[0],
        poem=poem,
        created_at=row[1],
    )


def validate_poem_ids(cur, poem_ids: list[int]):
    if not poem_ids:
        return

    cur.execute(
        "SELECT id FROM poems WHERE id = ANY(%s)",
        (poem_ids,),
    )
    existing_ids = {row[0] for row in cur.fetchall()}
    missing_ids = [poem_id for poem_id in poem_ids if poem_id not in existing_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Poems not found: {missing_ids}")


@router.get(
    "/collections",
    tags=["collections"],
    response_model=CollectionListResponse,
    summary="获取合集列表",
)
def list_collections(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    base_query = """
        FROM collections
    """
    params: list[object] = []
    conditions: list[str] = []

    if keyword:
        conditions.append("name ILIKE %s")
        params.append(f"%{keyword}%")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    list_query = (
        "SELECT id, name, description, created_at"
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

    return CollectionListResponse(
        items=[serialize_collection(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/collections/{collection_id}",
    tags=["collections"],
    response_model=CollectionRead,
    summary="获取合集详情",
)
def get_collection(collection_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, created_at
                FROM collections
                WHERE id = %s
                """,
                (collection_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    return serialize_collection(row)


@router.get(
    "/collections/{collection_id}/poems",
    tags=["collections"],
    response_model=CollectionPoemListResponse,
    summary="获取合集下诗词",
)
def list_collection_poems(
    collection_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM collections WHERE id = %s", (collection_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Collection not found")

            cur.execute(
                "SELECT COUNT(*) FROM collection_poems WHERE collection_id = %s",
                (collection_id,),
            )
            total = cur.fetchone()[0]

            cur.execute(
                """
                SELECT cp.collection_id, cp.created_at,
                       p.id, p.title, p.author_id, a.name, p.content, p.created_at
                FROM collection_poems cp
                JOIN poems p ON p.id = cp.poem_id
                JOIN authors a ON a.id = p.author_id
                WHERE cp.collection_id = %s
                ORDER BY cp.created_at ASC
                LIMIT %s OFFSET %s
                """,
                (collection_id, limit, offset),
            )
            rows = cur.fetchall()

    return CollectionPoemListResponse(
        items=[serialize_collection_poem(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/collections",
    tags=["collections"],
    response_model=CollectionRead,
    summary="新增合集",
)
def create_collection(collection: CollectionCreate, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collections (name, description)
                VALUES (%s, %s)
                RETURNING id, name, description, created_at
                """,
                (collection.name, collection.description),
            )
            row = cur.fetchone()
        conn.commit()

    background_tasks.add_task(sync_collection_embedding, row[0])

    return serialize_collection(row)


@router.post(
    "/collections/{collection_id}/poems",
    tags=["collections"],
    response_model=MessageResponse,
    summary="向合集添加诗词",
)
def add_poem_to_collection(collection_id: int, payload: CollectionPoemCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM collections WHERE id = %s", (collection_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Collection not found")

            cur.execute("SELECT id FROM poems WHERE id = %s", (payload.poem_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Poem not found")

            cur.execute(
                "SELECT 1 FROM collection_poems WHERE collection_id = %s AND poem_id = %s",
                (collection_id, payload.poem_id),
            )
            if cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="Poem already in collection")

            cur.execute(
                "INSERT INTO collection_poems (collection_id, poem_id) VALUES (%s, %s)",
                (collection_id, payload.poem_id),
            )
        conn.commit()

    return MessageResponse(message="Poem added to collection")


@router.put(
    "/collections/{collection_id}/poems",
    tags=["collections"],
    response_model=MessageResponse,
    summary="整包替换合集诗词",
)
def replace_collection_poems(collection_id: int, payload: CollectionPoemReplace):
    poem_ids = list(dict.fromkeys(payload.poem_ids))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM collections WHERE id = %s", (collection_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Collection not found")

            validate_poem_ids(cur, poem_ids)

            cur.execute(
                "DELETE FROM collection_poems WHERE collection_id = %s",
                (collection_id,),
            )

            for poem_id in poem_ids:
                cur.execute(
                    "INSERT INTO collection_poems (collection_id, poem_id) VALUES (%s, %s)",
                    (collection_id, poem_id),
                )
        conn.commit()

    return MessageResponse(message="Collection poems replaced")


@router.delete(
    "/collections/{collection_id}/poems/{poem_id}",
    tags=["collections"],
    response_model=MessageResponse,
    summary="从合集移除诗词",
)
def remove_poem_from_collection(collection_id: int, poem_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM collection_poems WHERE collection_id = %s AND poem_id = %s RETURNING poem_id",
                (collection_id, poem_id),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Collection poem relation not found")

    return MessageResponse(message="Poem removed from collection")


@router.put(
    "/collections/{collection_id}",
    tags=["collections"],
    response_model=CollectionRead,
    summary="更新合集",
)
def update_collection(collection_id: int, collection: CollectionUpdate, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE collections
                SET name = %s, description = %s
                WHERE id = %s
                RETURNING id, name, description, created_at
                """,
                (collection.name, collection.description, collection_id),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    background_tasks.add_task(sync_collection_embedding, row[0])

    return serialize_collection(row)


@router.patch(
    "/collections/{collection_id}",
    tags=["collections"],
    response_model=CollectionRead,
    summary="局部更新合集",
)
def patch_collection(collection_id: int, collection: CollectionPatch, background_tasks: BackgroundTasks):
    update_data = {k: v for k, v in collection.to_update_data().items() if k in COLLECTION_PATCH_FIELDS}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    assignments = ", ".join(f"{field} = %s" for field in update_data)
    params = list(update_data.values())
    params.append(collection_id)

    query = f"""
        UPDATE collections
        SET {assignments}
        WHERE id = %s
        RETURNING id, name, description, created_at
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    background_tasks.add_task(sync_collection_embedding, row[0])

    return serialize_collection(row)


@router.delete(
    "/collections/{collection_id}",
    tags=["collections"],
    response_model=MessageResponse,
    summary="删除合集",
)
def delete_collection(collection_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM collections WHERE id = %s RETURNING id",
                (collection_id,),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    return MessageResponse(message="Collection deleted")
