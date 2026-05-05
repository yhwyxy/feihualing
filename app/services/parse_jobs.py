from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

from app.db.connection import get_connection
from app.services.concept_parser import ParseResult, parse_poem_concepts


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParseJob:
    id: int
    poem_id: int
    status: str


def create_parse_job(
    poem_id: int,
    job_type: str = "reparse",
    trigger_source: str = "api",
) -> ParseJob | None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parse_jobs (poem_id, job_type, status, trigger_source)
                VALUES (%s, %s, 'pending', %s)
                RETURNING id, poem_id, status
                """,
                (poem_id, job_type, trigger_source),
            )
            row = cur.fetchone()
            conn.commit()
    except psycopg.errors.UndefinedTable:
        logger.warning("parse_jobs table is missing; skip concept parse job for poem_id=%s", poem_id)
        return None

    return ParseJob(id=row[0], poem_id=row[1], status=row[2])


def _mark_job_running(job_id: int) -> int | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE parse_jobs
            SET status = 'running', started_at = now(), updated_at = now()
            WHERE id = %s
            RETURNING poem_id
            """,
            (job_id,),
        )
        row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def _mark_job_succeeded(job_id: int, result: ParseResult) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE parse_jobs
            SET status = 'succeeded', finished_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (job_id,),
        )
        cur.execute(
            """
            INSERT INTO parse_logs (job_id, level, message, payload)
            VALUES (%s, 'info', %s, %s)
            """,
            (
                job_id,
                "Concept parse succeeded",
                Jsonb({
                    "poem_id": result.poem_id,
                    "line_match_count": result.line_match_count,
                    "concept_count": result.concept_count,
                    "conflict_count": len(result.conflicts),
                }),
            ),
        )
        for conflict in result.conflicts:
            cur.execute(
                """
                INSERT INTO parse_logs (job_id, level, message, payload)
                VALUES (%s, 'warning', %s, %s)
                """,
                (job_id, "Concept parse conflict detected", Jsonb(conflict)),
            )
        conn.commit()


def _mark_job_failed(job_id: int, exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE parse_jobs
            SET status = 'failed',
                finished_at = now(),
                error_message = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (message, job_id),
        )
        cur.execute(
            """
            INSERT INTO parse_logs (job_id, level, message, payload)
            VALUES (%s, 'error', %s, %s)
            """,
            (job_id, message, Jsonb({"error_type": exc.__class__.__name__})),
        )
        conn.commit()


def run_parse_job(job_id: int) -> None:
    try:
        poem_id = _mark_job_running(job_id)
        if poem_id is None:
            logger.warning("parse job not found: %s", job_id)
            return

        result = parse_poem_concepts(poem_id)
        _mark_job_succeeded(job_id, result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("parse job failed: %s", job_id)
        try:
            _mark_job_failed(job_id, exc)
        except Exception:  # noqa: BLE001
            logger.exception("failed to mark parse job as failed: %s", job_id)


def schedule_poem_parse(
    background_tasks: Any,
    poem_id: int,
    job_type: str = "reparse",
    trigger_source: str = "api",
) -> ParseJob | None:
    job = create_parse_job(poem_id=poem_id, job_type=job_type, trigger_source=trigger_source)
    if job is not None:
        background_tasks.add_task(run_parse_job, job.id)
    return job


def run_poem_parse_sync(
    poem_id: int,
    *,
    job_type: str = "batch_backfill",
    trigger_source: str = "script",
) -> ParseJob | None:
    job = create_parse_job(poem_id=poem_id, job_type=job_type, trigger_source=trigger_source)
    if job is None:
        return None
    run_parse_job(job.id)
    return job


def list_parse_jobs(
    *,
    status: str | None = None,
    poem_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    base_query = "FROM parse_jobs"
    params: list[object] = []
    conditions: list[str] = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if poem_id is not None:
        conditions.append("poem_id = %s")
        params.append(poem_id)
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT COUNT(*) " + base_query, params)
        total = cur.fetchone()["count"]
        cur.execute(
            """
            SELECT id, poem_id, job_type, status, trigger_source, started_at, finished_at,
                   error_message, created_at, updated_at
            """
            + base_query
            + " ORDER BY created_at DESC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        rows = cur.fetchall()
    return rows, total


def get_parse_job_detail(job_id: int) -> tuple[dict | None, list[dict]]:
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, poem_id, job_type, status, trigger_source, started_at, finished_at,
                   error_message, created_at, updated_at
            FROM parse_jobs
            WHERE id = %s
            """,
            (job_id,),
        )
        job = cur.fetchone()
        if job is None:
            return None, []
        cur.execute(
            """
            SELECT id, job_id, level, message, payload, created_at
            FROM parse_logs
            WHERE job_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (job_id,),
        )
        logs = cur.fetchall()
    return job, logs
