from fastapi import APIRouter
from app.db.connection import get_connection

router = APIRouter()

@router.get("/health", summary="服务健康检查")
def health_check():
    return {"status": "ok"}

@router.get("/health/db", summary="数据库健康检查")
def db_health_check():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            res = cur.fetchone()

    return {"status": "ok", "database": res[0]}