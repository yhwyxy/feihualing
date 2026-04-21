"""add_llm_source_fields_to_turns

Revision ID: d5641bcb0f47
Revises: caf0d6f00a2b
Create Date: 2026-04-20 20:22:21.778776

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d5641bcb0f47"
down_revision: Union[str, Sequence[str], None] = "caf0d6f00a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE feihualing_turns "
        "ADD COLUMN IF NOT EXISTS llm_source_title TEXT, "
        "ADD COLUMN IF NOT EXISTS llm_source_author TEXT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE feihualing_turns "
        "DROP COLUMN IF EXISTS llm_source_author, "
        "DROP COLUMN IF EXISTS llm_source_title"
    )
