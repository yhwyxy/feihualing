from __future__ import annotations

import argparse

from app.db.connection import get_connection
from app.services.parse_jobs import run_poem_parse_sync


def load_poem_ids(limit: int | None, offset: int, poem_ids: list[int] | None) -> list[int]:
    if poem_ids:
        return poem_ids

    query = "SELECT id FROM poems ORDER BY id ASC"
    params: list[object] = []
    if limit is not None:
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return [row[0] for row in cur.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill concept relations for poems.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of poems to process.")
    parser.add_argument("--offset", type=int, default=0, help="Offset for poem selection.")
    parser.add_argument("--poem-id", type=int, action="append", dest="poem_ids", help="Specific poem IDs to process.")
    args = parser.parse_args()

    poem_ids = load_poem_ids(limit=args.limit, offset=args.offset, poem_ids=args.poem_ids)
    for poem_id in poem_ids:
        job = run_poem_parse_sync(poem_id, job_type="batch_backfill", trigger_source="script")
        if job is None:
            raise RuntimeError("parse_jobs table is not available")
        print(f"poem_id={poem_id} job_id={job.id}")


if __name__ == "__main__":
    main()
