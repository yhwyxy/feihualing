"""add_popularity_rank_and_expert_difficulty

Revision ID: 86a0db6678db
Revises: d5641bcb0f47
Create Date: 2026-04-21 22:19:07.833539

Changes:
  * poems.popularity_rank SMALLINT NOT NULL DEFAULT 3，CHECK 1..5
  * 索引 idx_poems_popularity_rank（配合飞花令 min_rank 过滤）
  * 扩展 feihualing_difficulty enum 增加 'expert'（炼狱难度，允许 Agent 引用库外）
"""
from typing import Sequence, Union

from alembic import op


revision: str = "86a0db6678db"
down_revision: Union[str, Sequence[str], None] = "d5641bcb0f47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE poems
        ADD COLUMN IF NOT EXISTS popularity_rank SMALLINT NOT NULL DEFAULT 3
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'poems_popularity_rank_range'
          ) THEN
            ALTER TABLE poems
            ADD CONSTRAINT poems_popularity_rank_range
            CHECK (popularity_rank BETWEEN 1 AND 5);
          END IF;
        END$$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_poems_popularity_rank "
        "ON poems(popularity_rank)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_enum
            WHERE enumlabel = 'expert'
              AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'feihualing_difficulty')
          ) THEN
            ALTER TYPE feihualing_difficulty ADD VALUE 'expert';
          END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_poems_popularity_rank")
    op.execute(
        "ALTER TABLE poems DROP CONSTRAINT IF EXISTS poems_popularity_rank_range"
    )
    op.execute("ALTER TABLE poems DROP COLUMN IF EXISTS popularity_rank")
    # PostgreSQL 不支持从 enum 删除 value，此处不做 expert 的回滚。
