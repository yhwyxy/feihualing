"""create collection poems table

Revision ID: b0c622dfce73
Revises: 218ad809d80b
Create Date: 2026-04-16 19:17:36.954250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0c622dfce73"
down_revision: Union[str, Sequence[str], None] = "218ad809d80b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collection_poems",
        sa.Column("collection_id", sa.BigInteger(), nullable=False),
        sa.Column("poem_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["poem_id"], ["poems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "poem_id"),
    )
    op.create_index("ix_collection_poems_poem_id", "collection_poems", ["poem_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_collection_poems_poem_id", table_name="collection_poems")
    op.drop_table("collection_poems")
