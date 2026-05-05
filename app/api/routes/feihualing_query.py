from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.concept import FeihualingQueryResponse
from app.services.feihualing_query import query_feihualing_lines


router = APIRouter()
ALLOWED_POSITIONS = {"any", "start", "end"}


@router.get(
    "/feihualing",
    tags=["feihualing"],
    response_model=FeihualingQueryResponse,
    summary="查询飞花令诗句",
)
def query_feihualing(
    keyword: str = Query(min_length=1),
    position: str = Query(default="any"),
    author: str | None = Query(default=None),
    author_id: int | None = Query(default=None, gt=0),
    dynasty: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    keyword = keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    if position not in ALLOWED_POSITIONS:
        raise HTTPException(status_code=400, detail="Invalid position")

    items, total = query_feihualing_lines(
        keyword,
        position=position,
        author=author,
        author_id=author_id,
        dynasty=dynasty,
        limit=limit,
        offset=offset,
    )

    return FeihualingQueryResponse(
        keyword=keyword,
        position=position,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
