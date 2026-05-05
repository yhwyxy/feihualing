from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.connection import get_connection
from app.schemas.concept import (
    ConceptAliasCreate,
    ConceptAliasListResponse,
    ConceptAliasRead,
    ConceptGraphLimits,
    ConceptGraphResponse,
    ConceptListResponse,
    ConceptRead,
    ConceptType,
    ParseJobScheduledResponse,
    ParseJobDetailResponse,
    ParseJobListResponse,
    ParseJobRead,
    ParseLogRead,
    PoemConceptRead,
    PoemConceptsResponse,
    ManualLineConceptCreate,
)
from app.schemas.common import MessageResponse
from app.services.concept_admin import (
    create_concept_alias,
    create_manual_line_concept,
    delete_concept_alias,
    delete_manual_line_concept,
    list_concept_aliases,
)
from app.services.concept_graph import get_concept_graph
from app.services.parse_jobs import get_parse_job_detail, list_parse_jobs, schedule_poem_parse


router = APIRouter()
ALLOWED_CONCEPT_TYPES = {"char", "phrase", "place", "image", "theme", "dynasty"}
ALLOWED_SOURCES = {"parser", "manual", "import", "llm"}


def serialize_concept(row) -> ConceptRead:
    return ConceptRead(
        id=row[0],
        name=row[1],
        normalized_name=row[2],
        type=row[3],
        description=row[4],
        is_active=row[5],
        poem_count=row[6],
        line_count=row[7],
        created_at=row[8],
    )


@router.get(
    "/concepts",
    tags=["concepts"],
    response_model=ConceptListResponse,
    summary="获取概念列表",
)
def list_concepts(
    keyword: str | None = Query(default=None),
    type: ConceptType | None = Query(default=None),
    include_counts: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    base_query = "FROM concepts c"
    params: list[object] = []
    conditions = ["c.is_active = true"]

    if keyword:
        base_query += " LEFT JOIN concept_aliases ca ON ca.concept_id = c.id"
        conditions.append("(c.name ILIKE %s OR ca.alias ILIKE %s)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if type:
        conditions.append("c.type = %s")
        params.append(type)

    where_clause = " WHERE " + " AND ".join(conditions)
    count_query = "SELECT COUNT(DISTINCT c.id) " + base_query + where_clause

    if include_counts:
        select_counts = """
            COALESCE(pc.poem_count, 0) AS poem_count,
            COALESCE(lc.line_count, 0) AS line_count,
        """
        joins = """
            LEFT JOIN (
                SELECT concept_id, COUNT(DISTINCT poem_id) AS poem_count
                FROM poem_concepts
                GROUP BY concept_id
            ) pc ON pc.concept_id = c.id
            LEFT JOIN (
                SELECT concept_id, COUNT(*) AS line_count
                FROM line_concepts
                GROUP BY concept_id
            ) lc ON lc.concept_id = c.id
        """
    else:
        select_counts = "NULL AS poem_count, NULL AS line_count,"
        joins = ""

    list_query = f"""
        SELECT DISTINCT
            c.id,
            c.name,
            c.normalized_name,
            c.type,
            c.description,
            c.is_active,
            {select_counts}
            c.created_at
        {base_query}
        {joins}
        {where_clause}
        ORDER BY c.id ASC
        LIMIT %s OFFSET %s
    """

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(count_query, params)
        total = cur.fetchone()[0]
        cur.execute(list_query, [*params, limit, offset])
        rows = cur.fetchall()

    return ConceptListResponse(
        items=[serialize_concept(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/concepts/{concept_id}/graph",
    tags=["concepts"],
    response_model=ConceptGraphResponse,
    summary="获取概念局部图谱",
)
def get_graph(
    concept_id: int,
    depth: int = Query(default=1, ge=1),
    limit_poems: int = Query(default=30, ge=1, le=100),
    limit_lines: int = Query(default=80, ge=1, le=200),
    author_id: int | None = Query(default=None, gt=0),
    dynasty: str | None = Query(default=None),
    node_types: str | None = Query(default="line,poem,author,dynasty"),
    source: str | None = Query(default=None),
    min_popularity: int | None = Query(default=None, ge=1, le=5),
    min_matched_count: int | None = Query(default=None, ge=1),
):
    if depth != 1:
        raise HTTPException(status_code=400, detail="MVP only supports depth=1")

    center, nodes, edges, truncated = get_concept_graph(
        concept_id,
        limit_poems=limit_poems,
        limit_lines=limit_lines,
        author_id=author_id,
        dynasty=dynasty,
        node_types=node_types,
        source=source,
        min_popularity=min_popularity,
        min_matched_count=min_matched_count,
    )
    if center is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    return ConceptGraphResponse(
        center=center,
        nodes=nodes,
        edges=edges,
        limits=ConceptGraphLimits(limit_poems=limit_poems, limit_lines=limit_lines),
        truncated=truncated,
    )


@router.get(
    "/concepts/{concept_id}/aliases",
    tags=["concepts"],
    response_model=ConceptAliasListResponse,
    summary="获取概念别名",
)
def get_concept_aliases(concept_id: int):
    aliases = list_concept_aliases(concept_id)
    return ConceptAliasListResponse(
        concept_id=concept_id,
        aliases=[ConceptAliasRead(**alias) for alias in aliases],
    )


@router.post(
    "/concepts/{concept_id}/aliases",
    tags=["concepts"],
    response_model=ConceptAliasRead,
    summary="新增概念别名",
)
def add_concept_alias(concept_id: int, payload: ConceptAliasCreate):
    return ConceptAliasRead(**create_concept_alias(concept_id, payload.alias))


@router.delete(
    "/concepts/{concept_id}/aliases/{alias_id}",
    tags=["concepts"],
    response_model=MessageResponse,
    summary="删除概念别名",
)
def remove_concept_alias(concept_id: int, alias_id: int):
    if not delete_concept_alias(concept_id, alias_id):
        raise HTTPException(status_code=404, detail="Alias not found")
    return MessageResponse(message="Alias deleted")


@router.get(
    "/poems/{poem_id}/concepts",
    tags=["concepts"],
    response_model=PoemConceptsResponse,
    summary="获取诗词关联概念",
)
def get_poem_concepts(
    poem_id: int,
    include_lines: bool = Query(default=True),
    source: str | None = Query(default=None),
):
    if source is not None and source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM poems WHERE id = %s", (poem_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Poem not found")

        params: list[object] = [poem_id]
        source_filter = ""
        if source is not None:
            source_filter = " AND pc.source = %s"
            params.append(source)

        cur.execute(
            f"""
            SELECT
                c.id,
                c.name,
                c.type,
                pc.confidence,
                pc.source,
                pc.matched_count,
                pc.matched_texts
            FROM poem_concepts pc
            JOIN concepts c ON c.id = pc.concept_id
            WHERE pc.poem_id = %s{source_filter}
            ORDER BY pc.matched_count DESC, c.id ASC
            """,
            params,
        )
        concept_rows = cur.fetchall()

        lines_by_concept: dict[int, list[dict]] = {}
        if include_lines and concept_rows:
            concept_ids = [row[0] for row in concept_rows]
            line_params: list[object] = [poem_id, concept_ids]
            line_source_filter = ""
            if source is not None:
                line_source_filter = " AND lc.source = %s"
                line_params.append(source)
            cur.execute(
                f"""
                SELECT concept_id, line_index, line_text, matched_text, start_offset, source
                FROM line_concepts lc
                WHERE poem_id = %s AND concept_id = ANY(%s){line_source_filter}
                ORDER BY concept_id ASC, line_index ASC, start_offset ASC
                """,
                line_params,
            )
            for row in cur.fetchall():
                lines_by_concept.setdefault(row[0], []).append(
                    {
                        "line_index": row[1],
                        "line_text": row[2],
                        "matched_text": row[3],
                        "start_offset": row[4],
                        "source": row[5],
                    }
                )

    return PoemConceptsResponse(
        poem_id=poem_id,
        concepts=[
            PoemConceptRead(
                id=row[0],
                name=row[1],
                type=row[2],
                confidence=row[3],
                source=row[4],
                matched_count=row[5],
                matched_texts=row[6],
                lines=lines_by_concept.get(row[0], []),
            )
            for row in concept_rows
        ],
    )


@router.post(
    "/poems/{poem_id}/concepts/manual",
    tags=["concepts"],
    response_model=MessageResponse,
    summary="手动新增诗句概念关系",
)
def add_manual_poem_concept(poem_id: int, payload: ManualLineConceptCreate):
    create_manual_line_concept(
        poem_id=poem_id,
        concept_id=payload.concept_id,
        line_index=payload.line_index,
        matched_text=payload.matched_text,
        start_offset=payload.start_offset,
    )
    return MessageResponse(message="Manual concept relation created")


@router.delete(
    "/poems/{poem_id}/concepts/manual",
    tags=["concepts"],
    response_model=MessageResponse,
    summary="手动删除诗句概念关系",
)
def remove_manual_poem_concept(
    poem_id: int,
    concept_id: int = Query(gt=0),
    line_index: int = Query(ge=0),
    matched_text: str = Query(min_length=1),
    start_offset: int = Query(ge=0),
):
    deleted = delete_manual_line_concept(
        poem_id=poem_id,
        concept_id=concept_id,
        line_index=line_index,
        matched_text=matched_text,
        start_offset=start_offset,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Manual concept relation not found")
    return MessageResponse(message="Manual concept relation deleted")


@router.post(
    "/poems/{poem_id}/reparse",
    tags=["concepts"],
    response_model=ParseJobScheduledResponse,
    summary="手动触发诗词概念重解析",
)
def reparse_poem(poem_id: int, background_tasks: BackgroundTasks):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM poems WHERE id = %s", (poem_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Poem not found")

    job = schedule_poem_parse(background_tasks, poem_id, job_type="reparse", trigger_source="api")
    if job is None:
        raise HTTPException(status_code=503, detail="Parse job table is not available")

    return ParseJobScheduledResponse(
        message="Parse job scheduled",
        job_id=job.id,
        poem_id=poem_id,
        status=job.status,
    )


@router.get(
    "/concepts/parse-jobs",
    tags=["concepts"],
    response_model=ParseJobListResponse,
    summary="查看解析任务列表",
)
def get_parse_jobs(
    status: str | None = Query(default=None),
    poem_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = list_parse_jobs(status=status, poem_id=poem_id, limit=limit, offset=offset)
    return ParseJobListResponse(
        items=[ParseJobRead(**row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/concepts/parse-jobs/{job_id}",
    tags=["concepts"],
    response_model=ParseJobDetailResponse,
    summary="查看解析任务详情",
)
def get_parse_job(job_id: int):
    job, logs = get_parse_job_detail(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Parse job not found")
    return ParseJobDetailResponse(
        job=ParseJobRead(**job),
        logs=[ParseLogRead(**log) for log in logs],
    )
