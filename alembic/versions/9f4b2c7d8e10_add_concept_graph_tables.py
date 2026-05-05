"""add concept graph tables

Revision ID: 9f4b2c7d8e10
Revises: 86a0db6678db
Create Date: 2026-05-02 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "9f4b2c7d8e10"
down_revision: Union[str, Sequence[str], None] = "86a0db6678db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS concepts (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('char', 'phrase', 'place', 'image', 'theme', 'dynasty')),
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (type, normalized_name)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_concepts_type_active ON concepts (type, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_concepts_normalized_name ON concepts (normalized_name)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS concept_aliases (
            id BIGSERIAL PRIMARY KEY,
            concept_id BIGINT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (concept_id, normalized_alias)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_concept_aliases_concept_id ON concept_aliases (concept_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_concept_aliases_normalized_alias ON concept_aliases (normalized_alias)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS poem_concepts (
            poem_id BIGINT NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
            concept_id BIGINT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
            source TEXT NOT NULL DEFAULT 'parser' CHECK (source IN ('parser', 'manual', 'import', 'llm')),
            matched_count INTEGER NOT NULL DEFAULT 1 CHECK (matched_count > 0),
            matched_texts TEXT[] NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (poem_id, concept_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_poem_concepts_concept_id ON poem_concepts (concept_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_poem_concepts_source ON poem_concepts (source)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS line_concepts (
            id BIGSERIAL PRIMARY KEY,
            poem_id BIGINT NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
            concept_id BIGINT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            line_index INTEGER NOT NULL CHECK (line_index >= 0),
            line_text TEXT NOT NULL,
            matched_text TEXT NOT NULL,
            start_offset INTEGER NOT NULL DEFAULT 0 CHECK (start_offset >= 0),
            confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
            source TEXT NOT NULL DEFAULT 'parser' CHECK (source IN ('parser', 'manual', 'import', 'llm')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (poem_id, line_index, concept_id, matched_text, start_offset, source)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_concepts_poem_id ON line_concepts (poem_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_concepts_concept_id ON line_concepts (concept_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_concepts_concept_poem ON line_concepts (concept_id, poem_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS author_concepts (
            author_id BIGINT NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
            concept_id BIGINT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
            source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('parser', 'manual', 'import', 'llm')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (author_id, concept_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_author_concepts_concept_id ON author_concepts (concept_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS parse_jobs (
            id BIGSERIAL PRIMARY KEY,
            poem_id BIGINT REFERENCES poems(id) ON DELETE CASCADE,
            job_type TEXT NOT NULL CHECK (job_type IN ('initial_parse', 'reparse', 'delete_cleanup', 'batch_backfill')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')),
            trigger_source TEXT NOT NULL DEFAULT 'api',
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_parse_jobs_poem_id_created ON parse_jobs (poem_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_parse_jobs_status_created ON parse_jobs (status, created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS parse_logs (
            id BIGSERIAL PRIMARY KEY,
            job_id BIGINT NOT NULL REFERENCES parse_jobs(id) ON DELETE CASCADE,
            level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error')),
            message TEXT NOT NULL,
            payload JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_parse_logs_job_id ON parse_logs (job_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_parse_logs_job_id")
    op.execute("DROP TABLE IF EXISTS parse_logs")
    op.execute("DROP INDEX IF EXISTS idx_parse_jobs_status_created")
    op.execute("DROP INDEX IF EXISTS idx_parse_jobs_poem_id_created")
    op.execute("DROP TABLE IF EXISTS parse_jobs")
    op.execute("DROP INDEX IF EXISTS idx_author_concepts_concept_id")
    op.execute("DROP TABLE IF EXISTS author_concepts")
    op.execute("DROP INDEX IF EXISTS idx_line_concepts_concept_poem")
    op.execute("DROP INDEX IF EXISTS idx_line_concepts_concept_id")
    op.execute("DROP INDEX IF EXISTS idx_line_concepts_poem_id")
    op.execute("DROP TABLE IF EXISTS line_concepts")
    op.execute("DROP INDEX IF EXISTS idx_poem_concepts_source")
    op.execute("DROP INDEX IF EXISTS idx_poem_concepts_concept_id")
    op.execute("DROP TABLE IF EXISTS poem_concepts")
    op.execute("DROP INDEX IF EXISTS idx_concept_aliases_normalized_alias")
    op.execute("DROP INDEX IF EXISTS idx_concept_aliases_concept_id")
    op.execute("DROP TABLE IF EXISTS concept_aliases")
    op.execute("DROP INDEX IF EXISTS idx_concepts_normalized_name")
    op.execute("DROP INDEX IF EXISTS idx_concepts_type_active")
    op.execute("DROP TABLE IF EXISTS concepts")
