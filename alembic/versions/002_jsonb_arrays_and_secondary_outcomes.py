"""Convert interventions/outcomes/locations to JSONB arrays, add secondary outcomes.

Revision ID: 002
Revises: 001
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new JSONB array columns
    op.add_column("trials", sa.Column("interventions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("trials", sa.Column("primary_outcomes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("trials", sa.Column("secondary_outcomes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("trials", sa.Column("locations", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Migrate existing scalar data into the new JSONB columns
    op.execute("""
        UPDATE trials SET
            interventions = CASE
                WHEN intervention_type IS NOT NULL OR intervention_name IS NOT NULL
                THEN jsonb_build_array(jsonb_build_object(
                    'type', intervention_type,
                    'name', intervention_name
                ))
                ELSE NULL
            END,
            primary_outcomes = CASE
                WHEN primary_outcome_measure IS NOT NULL OR primary_outcome_description IS NOT NULL
                THEN jsonb_build_array(jsonb_build_object(
                    'measure', primary_outcome_measure,
                    'description', primary_outcome_description
                ))
                ELSE NULL
            END,
            locations = CASE
                WHEN location_country IS NOT NULL
                THEN jsonb_build_array(jsonb_build_object('country', location_country))
                ELSE NULL
            END
    """)

    # Drop old scalar columns
    op.drop_column("trials", "intervention_type")
    op.drop_column("trials", "intervention_name")
    op.drop_column("trials", "primary_outcome_description")
    op.drop_column("trials", "primary_outcome_measure")
    op.drop_column("trials", "location_country")

    # Add phase index
    op.create_index("ix_trials_phase", "trials", ["phase"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trials_phase", table_name="trials")

    # Re-add old scalar columns
    op.add_column("trials", sa.Column("location_country", sa.String(length=100), nullable=True))
    op.add_column("trials", sa.Column("primary_outcome_measure", sa.Text(), nullable=True))
    op.add_column("trials", sa.Column("primary_outcome_description", sa.Text(), nullable=True))
    op.add_column("trials", sa.Column("intervention_name", sa.Text(), nullable=True))
    op.add_column("trials", sa.Column("intervention_type", sa.String(length=100), nullable=True))

    # Migrate JSONB data back to scalar columns (first element only)
    op.execute("""
        UPDATE trials SET
            intervention_type = interventions->0->>'type',
            intervention_name = interventions->0->>'name',
            primary_outcome_measure = primary_outcomes->0->>'measure',
            primary_outcome_description = primary_outcomes->0->>'description',
            location_country = locations->0->>'country'
    """)

    # Drop JSONB columns
    op.drop_column("trials", "locations")
    op.drop_column("trials", "secondary_outcomes")
    op.drop_column("trials", "primary_outcomes")
    op.drop_column("trials", "interventions")
