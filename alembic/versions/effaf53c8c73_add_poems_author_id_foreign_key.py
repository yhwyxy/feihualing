"""add poems author_id foreign key

Revision ID: effaf53c8c73
Revises: 40d34e71299b
Create Date: 2026-04-16 19:02:01.237709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "effaf53c8c73"
down_revision: Union[str, Sequence[str], None] = "40d34e71299b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("poems", sa.Column("author_id", sa.BigInteger(), nullable=True))

    op.execute(
        """
        INSERT INTO authors (name, bio)
        SELECT DISTINCT p.author, NULL
        FROM poems p
        WHERE p.author IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM authors a
              WHERE a.name = p.author
          )
        """
    )

    op.execute(
        """
        UPDATE poems p
        SET author_id = matched.id
        FROM (
            SELECT name, MIN(id) AS id
            FROM authors
            GROUP BY name
        ) AS matched
        WHERE p.author = matched.name
        """
    )

    op.alter_column("poems", "author_id", nullable=False)
    op.create_index("ix_poems_author_id", "poems", ["author_id"], unique=False)
    op.create_foreign_key(
        "fk_poems_author_id_authors",
        "poems",
        "authors",
        ["author_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("poems", "author")



def downgrade() -> None:
    op.add_column("poems", sa.Column("author", sa.String(length=100), nullable=True))

    op.execute(
        """
        UPDATE poems p
        SET author = a.name
        FROM authors a
        WHERE p.author_id = a.id
        """
    )

    op.alter_column("poems", "author", nullable=False)
    op.drop_constraint("fk_poems_author_id_authors", "poems", type_="foreignkey")
    op.drop_index("ix_poems_author_id", table_name="poems")
    op.drop_column("poems", "author_id")
