from fastapi import APIRouter

from app.api.routes.authors import router as authors_router
from app.api.routes.base import router as base_router
from app.api.routes.collections import router as collections_router
from app.api.routes.imports import router as imports_router
from app.api.routes.health import router as health_router
from app.api.routes.poems import router as poems_router


api_router = APIRouter()
api_router.include_router(base_router)
api_router.include_router(health_router)
api_router.include_router(poems_router)
api_router.include_router(authors_router)
api_router.include_router(collections_router)
api_router.include_router(imports_router)
