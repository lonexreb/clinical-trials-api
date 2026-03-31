"""Add study_type, eligibility_criteria, mesh_terms, references, investigators, source columns.

Revision ID: 004
Revises: 003
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trials", sa.Column("study_type", sa.String(100), nullable=True))
    op.add_column("trials", sa.Column("eligibility_criteria", sa.Text(), nullable=True))
    op.add_column(
        "trials",
        sa.Column("mesh_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "trials",
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "trials",
        sa.Column("investigators", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "trials",
        sa.Column("source", sa.String(100), nullable=False, server_default="clinicaltrials.gov"),
    )


def downgrade() -> None:
    op.drop_column("trials", "source")
    op.drop_column("trials", "investigators")
    op.drop_column("trials", "references")
    op.drop_column("trials", "mesh_terms")
    op.drop_column("trials", "eligibility_criteria")
    op.drop_column("trials", "study_type")
