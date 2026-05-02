from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from app.core.config import settings


logger = logging.getLogger(__name__)


_pool: ConnectionPool | None = None


def _configure_connection(conn: psycopg.Connection) -> None:
    """连接首次进入池时执行：注册 pgvector adapter。"""
    register_vector(conn)


def open_pool(min_size: int = 2, max_size: int = 20, timeout: float = 10.0) -> None:
    """FastAPI startup 时调用。幂等。"""
    global _pool
    if _pool is not None:
        return
    _pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=min_size,
        max_size=max_size,
        configure=_configure_connection,
        timeout=timeout,
        open=True,
    )
    logger.info("psycopg pool opened (min=%d, max=%d)", min_size, max_size)


def close_pool() -> None:
    """FastAPI shutdown 时调用。"""
    global _pool
    if _pool is None:
        return
    _pool.close()
    _pool = None
    logger.info("psycopg pool closed")


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """借出一个连接，退出时自动 commit / rollback 并归还池。

    若池未开启（脚本、alembic env 等外部进程），回退到直连模式，保持向后兼容。
    """
    if _pool is None:
        with psycopg.connect(settings.database_url) as conn:
            register_vector(conn)
            yield conn
        return

    with _pool.connection() as conn:
        yield conn
