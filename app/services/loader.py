"""Batch load parsed trial data into PostgreSQL."""

import logging

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.trial import Trial
from app.schemas.trial import TrialCreate

logger = logging.getLogger(__name__)

# Columns to update on conflict (everything except id, trial_id, created_at)
UPDATE_COLUMNS = [
    "title",
    "phase",
    "status",
    "sponsor_name",
    "intervention_type",
    "intervention_name",
    "primary_outcome_description",
    "primary_outcome_measure",
    "start_date",
    "completion_date",
    "location_country",
    "enrollment_number",
    "raw_data",
]


async def upsert_trials_batch(
    session: AsyncSession,
    trials: list[TrialCreate],
) -> int:
    """Insert or update a batch of trials. Returns count of rows affected."""
    if not trials:
        return 0

    values = [trial.model_dump() for trial in trials]
    dialect_name = session.bind.dialect.name if session.bind else "unknown"  # type: ignore[union-attr]

    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(Trial).values(values)
        update_dict = {col: getattr(stmt.excluded, col) for col in UPDATE_COLUMNS}
        update_dict["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(index_elements=["trial_id"], set_=update_dict)
        result = await session.execute(stmt)
        await session.commit()
        return int(result.rowcount)  # type: ignore[attr-defined]
    else:
        # SQLite fallback: delete existing + insert
        trial_ids = [v["trial_id"] for v in values]
        await session.execute(delete(Trial).where(Trial.trial_id.in_(trial_ids)))
        for v in values:
            trial = Trial(**v)
            session.add(trial)
        await session.commit()
        return len(values)


async def load_trials(
    session: AsyncSession,
    trials: list[TrialCreate],
    batch_size: int = 500,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> tuple[int, int]:
    """Load trials in batches. Returns (total_loaded, total_errors).

    If session_factory is provided, creates a fresh session per batch
    to avoid stale connections on hosted databases with connection limits.
    """
    total_loaded = 0
    total_errors = 0

    for i in range(0, len(trials), batch_size):
        batch = trials[i : i + batch_size]
        batch_num = i // batch_size + 1
        try:
            if session_factory is not None:
                async with session_factory() as batch_session:
                    count = await upsert_trials_batch(batch_session, batch)
            else:
                count = await upsert_trials_batch(session, batch)
            total_loaded += count
            logger.info("Batch %d: loaded %d trials", batch_num, count)
        except Exception:
            total_errors += len(batch)
            logger.exception("Batch %d failed", batch_num)

    return total_loaded, total_errors
