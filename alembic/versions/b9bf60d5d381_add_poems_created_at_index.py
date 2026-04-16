"""add poems created_at index

Revision ID: b9bf60d5d381
Revises: f7b5f50e644e
Create Date: 2026-04-16 18:53:41.554837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9bf60d5d381"
down_revision: Union[str, Sequence[str], None] = "f7b5f50e644e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_poems_created_at",
        "poems",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_poems_created_at", table_name="poems")
