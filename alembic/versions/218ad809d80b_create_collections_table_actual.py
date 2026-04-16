"""create collections table actual

Revision ID: 218ad809d80b
Revises: 8e46997be270
Create Date: 2026-04-16 19:10:42.663623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "218ad809d80b"
down_revision: Union[str, Sequence[str], None] = "8e46997be270"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_collections_name", "collections", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_collections_name", table_name="collections")
    op.drop_table("collections")
