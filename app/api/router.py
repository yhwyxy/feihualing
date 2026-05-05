from fastapi import APIRouter

from app.api.routes.authors import router as authors_router
from app.api.routes.base import router as base_router
from app.api.routes.collections import router as collections_router
from app.api.routes.concepts import router as concepts_router
from app.api.routes.documents import router as documents_router
from app.api.routes.feihualing import router as feihualing_router
from app.api.routes.feihualing_query import router as feihualing_query_router
from app.api.routes.imports import router as imports_router
from app.api.routes.health import router as health_router
from app.api.routes.poems import router as poems_router
from app.api.routes.rag import router as rag_router


api_router = APIRouter()
api_router.include_router(base_router)
api_router.include_router(health_router)
api_router.include_router(poems_router)
api_router.include_router(authors_router)
api_router.include_router(collections_router)
api_router.include_router(concepts_router)
api_router.include_router(imports_router)
api_router.include_router(documents_router)
api_router.include_router(rag_router)
api_router.include_router(feihualing_query_router)
api_router.include_router(feihualing_router)
