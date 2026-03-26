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
    intervention_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intervention_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_outcome_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_outcome_measure: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enrollment_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    )

    def __repr__(self) -> str:
        return f"<Trial(trial_id={self.trial_id!r}, title={self.title[:50]!r})>"
