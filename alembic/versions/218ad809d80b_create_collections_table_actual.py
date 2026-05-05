"""create collections table actual

Revision ID: 218ad809d80b
Revises: 8e46997be270
Create Date: 2026-04-16 19:10:42.663623

"""
from typing import Sequence, Union


revision: str = "218ad809d80b"
down_revision: Union[str, Sequence[str], None] = "8e46997be270"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The previous revision already creates collections. Keep this historical
    # revision as a no-op so a fresh Alembic replay does not create it twice.
    pass


def downgrade() -> None:
    pass
