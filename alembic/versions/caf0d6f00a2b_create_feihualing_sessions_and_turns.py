"""create_feihualing_sessions_and_turns

Revision ID: caf0d6f00a2b
Revises: 228297fedd25
Create Date: 2026-04-20 17:27:45.976698

"""
from typing import Sequence, Union

from alembic import op


revision: str = "caf0d6f00a2b"
down_revision: Union[str, Sequence[str], None] = "228297fedd25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feihualing_difficulty') THEN
            CREATE TYPE feihualing_difficulty AS ENUM ('easy', 'medium', 'hard');
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feihualing_status') THEN
            CREATE TYPE feihualing_status AS ENUM ('in_progress','user_won','agent_won','abandoned');
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feihualing_speaker') THEN
            CREATE TYPE feihualing_speaker AS ENUM ('user','agent');
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feihualing_sessions (
          id SERIAL PRIMARY KEY,
          target_char TEXT NOT NULL CHECK (char_length(target_char) = 1),
          difficulty feihualing_difficulty NOT NULL,
          status feihualing_status NOT NULL DEFAULT 'in_progress',
          winner_reason TEXT,
          started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          ended_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feihualing_turns (
          id SERIAL PRIMARY KEY,
          session_id INTEGER NOT NULL REFERENCES feihualing_sessions(id) ON DELETE CASCADE,
          turn_index INTEGER NOT NULL,
          speaker feihualing_speaker NOT NULL,
          line TEXT NOT NULL,
          poem_id INTEGER REFERENCES poems(id) ON DELETE SET NULL,
          is_valid BOOLEAN NOT NULL DEFAULT true,
          reject_reason TEXT,
          latency_ms INTEGER,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (session_id, turn_index)
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_feihualing_turns_session "
        "ON feihualing_turns (session_id, turn_index)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_feihualing_sessions_status "
        "ON feihualing_sessions (status, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_feihualing_sessions_status")
    op.execute("DROP INDEX IF EXISTS idx_feihualing_turns_session")
    op.execute("DROP TABLE IF EXISTS feihualing_turns")
    op.execute("DROP TABLE IF EXISTS feihualing_sessions")
    op.execute("DROP TYPE IF EXISTS feihualing_speaker")
    op.execute("DROP TYPE IF EXISTS feihualing_status")
    op.execute("DROP TYPE IF EXISTS feihualing_difficulty")
