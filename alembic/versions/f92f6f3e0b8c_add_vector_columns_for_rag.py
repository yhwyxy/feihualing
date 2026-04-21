"""add_vector_columns_for_rag

Revision ID: f92f6f3e0b8c
Revises: d4f2a1c0e9ab
Create Date: 2026-04-20 09:00:55.441901

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f92f6f3e0b8c"
down_revision: Union[str, Sequence[str], None] = "d4f2a1c0e9ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE poems ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})")
    op.execute(f"ALTER TABLE authors ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})")
    op.execute(f"ALTER TABLE collections ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})")


def downgrade() -> None:
    op.execute("ALTER TABLE collections DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE authors DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE poems DROP COLUMN IF EXISTS embedding")
