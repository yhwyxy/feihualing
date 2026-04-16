"""add query indexes for search and collection poems

Revision ID: d4f2a1c0e9ab
Revises: b0c622dfce73
Create Date: 2026-04-16 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d4f2a1c0e9ab"
down_revision: Union[str, Sequence[str], None] = "b0c622dfce73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_poems_title_trgm ON poems USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_authors_name_trgm ON authors USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collections_name_trgm ON collections USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collection_poems_collection_id_created_at ON collection_poems (collection_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_collection_poems_collection_id_created_at")
    op.execute("DROP INDEX IF EXISTS ix_collections_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_authors_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_poems_title_trgm")
