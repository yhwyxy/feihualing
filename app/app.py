from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "飞花令后端 API。当前提供 poems、authors、collections 三类资源接口，"
            "本地联调前可先执行 make seed 初始化演示数据。"
        ),
        version="0.1.0",
    )
    app.include_router(api_router)
    return app
