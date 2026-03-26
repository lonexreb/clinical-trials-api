"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trial_id", sa.String(length=50), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("phase", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("sponsor_name", sa.Text(), nullable=False),
        sa.Column("intervention_type", sa.String(length=100), nullable=True),
        sa.Column("intervention_name", sa.Text(), nullable=True),
        sa.Column("primary_outcome_description", sa.Text(), nullable=True),
        sa.Column("primary_outcome_measure", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("location_country", sa.String(length=100), nullable=True),
        sa.Column("enrollment_number", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trial_id"),
    )
    op.create_index("ix_trials_trial_id", "trials", ["trial_id"], unique=True)
    op.create_index("ix_trials_sponsor_name", "trials", ["sponsor_name"], unique=False)
    op.create_index("ix_trials_status", "trials", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trials_status", table_name="trials")
    op.drop_index("ix_trials_sponsor_name", table_name="trials")
    op.drop_index("ix_trials_trial_id", table_name="trials")
    op.drop_table("trials")
