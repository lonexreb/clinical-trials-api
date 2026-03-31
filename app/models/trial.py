import datetime

from sqlalchemy import Date, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Trial(Base):
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trial_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    sponsor_name: Mapped[str] = mapped_column(Text, nullable=False)
    study_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interventions: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    primary_outcomes: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    secondary_outcomes: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    conditions: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    eligibility_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    mesh_terms: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    references: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    investigators: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    locations: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    enrollment_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="clinicaltrials.gov"
    )
    raw_data: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_trials_trial_id", "trial_id", unique=True),
        Index("ix_trials_sponsor_name", "sponsor_name"),
        Index("ix_trials_status", "status"),
        Index("ix_trials_phase", "phase"),
        Index("ix_trials_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Trial(trial_id={self.trial_id!r}, title={self.title[:50]!r})>"
