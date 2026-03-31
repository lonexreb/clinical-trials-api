"""Add conditions JSONB column and updated_at index.

Revision ID: 003
Revises: 002
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trials", sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index("ix_trials_updated_at", "trials", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_trials_updated_at", table_name="trials")
    op.drop_column("trials", "conditions")
