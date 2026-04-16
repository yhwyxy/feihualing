"""create authors table

Revision ID: 40d34e71299b
Revises: b9bf60d5d381
Create Date: 2026-04-16 18:54:45.123430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "40d34e71299b"
down_revision: Union[str, Sequence[str], None] = "b9bf60d5d381"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_authors_name", "authors", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_authors_name", table_name="authors")
    op.drop_table("authors")
