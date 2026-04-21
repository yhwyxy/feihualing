from __future__ import annotations

import re

import numpy as np


RRF_K = 60


def _extract_lexemes(cur, query: str) -> list[str]:
    cur.execute("SELECT to_tsvector('zhcfg', %s)::text", (query,))
    row = cur.fetchone()
    tsv_str = row[0] if row and row[0] else ""
    return re.findall(r"'([^']+)':", tsv_str)


def build_or_tsquery(cur, query: str) -> str:
    lexemes = _extract_lexemes(cur, query)
    if not lexemes:
        return "__nomatch_token__"
    return " | ".join(lexemes)


def hybrid_search_poems(cur, vec: np.ndarray, or_tsq: str, top_k: int,
                         candidate_k: int = 20) -> list[tuple]:
    cur.execute(
        """
        WITH semantic AS (
            SELECT id,
                   RANK() OVER (ORDER BY embedding <=> %s) AS rk
            FROM poems
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
        ),
        keyword AS (
            SELECT id,
                   RANK() OVER (ORDER BY ts_rank_cd(search_tsv, q) DESC) AS rk
            FROM poems, to_tsquery('zhcfg', %s) q
            WHERE search_tsv @@ q
            LIMIT %s
        ),
        fused AS (
            SELECT COALESCE(s.id, k.id) AS id,
                   COALESCE(1.0 / (%s + s.rk), 0)::float AS sem_score,
                   COALESCE(1.0 / (%s + k.rk), 0)::float AS kw_score
            FROM semantic s
            FULL OUTER JOIN keyword k ON s.id = k.id
        )
        SELECT p.id, p.title, p.content, p.author_id, a.name,
               f.sem_score, f.kw_score,
               (f.sem_score + f.kw_score) AS score
        FROM fused f
        JOIN poems p ON p.id = f.id
        LEFT JOIN authors a ON a.id = p.author_id
        ORDER BY score DESC
        LIMIT %s
        """,
        (vec, vec, candidate_k, or_tsq, candidate_k, RRF_K, RRF_K, top_k),
    )
    return cur.fetchall()


def hybrid_search_authors(cur, vec: np.ndarray, or_tsq: str, top_k: int,
                           candidate_k: int = 20) -> list[tuple]:
    cur.execute(
        """
        WITH semantic AS (
            SELECT id,
                   RANK() OVER (ORDER BY embedding <=> %s) AS rk
            FROM authors
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
        ),
        keyword AS (
            SELECT id,
                   RANK() OVER (ORDER BY ts_rank_cd(search_tsv, q) DESC) AS rk
            FROM authors, to_tsquery('zhcfg', %s) q
            WHERE search_tsv @@ q
            LIMIT %s
        ),
        fused AS (
            SELECT COALESCE(s.id, k.id) AS id,
                   COALESCE(1.0 / (%s + s.rk), 0)::float AS sem_score,
                   COALESCE(1.0 / (%s + k.rk), 0)::float AS kw_score
            FROM semantic s
            FULL OUTER JOIN keyword k ON s.id = k.id
        )
        SELECT a.id, a.name, a.bio,
               f.sem_score, f.kw_score,
               (f.sem_score + f.kw_score) AS score
        FROM fused f
        JOIN authors a ON a.id = f.id
        ORDER BY score DESC
        LIMIT %s
        """,
        (vec, vec, candidate_k, or_tsq, candidate_k, RRF_K, RRF_K, top_k),
    )
    return cur.fetchall()


def hybrid_search_collections(cur, vec: np.ndarray, or_tsq: str, top_k: int,
                               candidate_k: int = 20) -> list[tuple]:
    cur.execute(
        """
        WITH semantic AS (
            SELECT id,
                   RANK() OVER (ORDER BY embedding <=> %s) AS rk
            FROM collections
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
        ),
        keyword AS (
            SELECT id,
                   RANK() OVER (ORDER BY ts_rank_cd(search_tsv, q) DESC) AS rk
            FROM collections, to_tsquery('zhcfg', %s) q
            WHERE search_tsv @@ q
            LIMIT %s
        ),
        fused AS (
            SELECT COALESCE(s.id, k.id) AS id,
                   COALESCE(1.0 / (%s + s.rk), 0)::float AS sem_score,
                   COALESCE(1.0 / (%s + k.rk), 0)::float AS kw_score
            FROM semantic s
            FULL OUTER JOIN keyword k ON s.id = k.id
        )
        SELECT c.id, c.name, c.description,
               f.sem_score, f.kw_score,
               (f.sem_score + f.kw_score) AS score
        FROM fused f
        JOIN collections c ON c.id = f.id
        ORDER BY score DESC
        LIMIT %s
        """,
        (vec, vec, candidate_k, or_tsq, candidate_k, RRF_K, RRF_K, top_k),
    )
    return cur.fetchall()


def hybrid_search_document_chunks(cur, vec: np.ndarray, or_tsq: str, top_k: int,
                                    candidate_k: int = 20) -> list[tuple]:
    cur.execute(
        """
        WITH semantic AS (
            SELECT id,
                   RANK() OVER (ORDER BY embedding <=> %s) AS rk
            FROM document_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
        ),
        keyword AS (
            SELECT id,
                   RANK() OVER (ORDER BY ts_rank_cd(search_tsv, q) DESC) AS rk
            FROM document_chunks, to_tsquery('zhcfg', %s) q
            WHERE search_tsv @@ q
            LIMIT %s
        ),
        fused AS (
            SELECT COALESCE(s.id, k.id) AS id,
                   COALESCE(1.0 / (%s + s.rk), 0)::float AS sem_score,
                   COALESCE(1.0 / (%s + k.rk), 0)::float AS kw_score
            FROM semantic s
            FULL OUTER JOIN keyword k ON s.id = k.id
        )
        SELECT dc.id, dc.document_id, d.title, dc.chunk_index, dc.content,
               f.sem_score, f.kw_score,
               (f.sem_score + f.kw_score) AS score
        FROM fused f
        JOIN document_chunks dc ON dc.id = f.id
        JOIN documents d ON d.id = dc.document_id
        ORDER BY score DESC
        LIMIT %s
        """,
        (vec, vec, candidate_k, or_tsq, candidate_k, RRF_K, RRF_K, top_k),
    )
    return cur.fetchall()
