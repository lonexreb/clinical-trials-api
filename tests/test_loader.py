"""Tests for the trial loader (batch upsert)."""


import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trial import Trial
from app.schemas.trial import TrialCreate
from app.services.loader import load_trials, upsert_trials_batch


def _make_trial(trial_id: str = "NCT00000001", title: str = "Test Trial", **kwargs: object) -> TrialCreate:
    defaults: dict[str, object] = {
        "trial_id": trial_id,
        "title": title,
        "status": "RECRUITING",
        "sponsor_name": "Test Sponsor",
        "raw_data": {"test": True},
    }
    defaults.update(kwargs)
    return TrialCreate(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_insert_new_trials(db_session: AsyncSession) -> None:
    trials = [_make_trial("NCT00000001", "Trial 1"), _make_trial("NCT00000002", "Trial 2")]
    count = await upsert_trials_batch(db_session, trials)
    assert count == 2

    result = await db_session.scalars(select(Trial))
    rows = list(result.all())
    assert len(rows) == 2
    assert {r.trial_id for r in rows} == {"NCT00000001", "NCT00000002"}


@pytest.mark.asyncio
async def test_upsert_existing_trial(db_session: AsyncSession) -> None:
    # Insert initial
    await upsert_trials_batch(db_session, [_make_trial("NCT00000001", "Original Title")])

    # Upsert with updated title
    await upsert_trials_batch(db_session, [_make_trial("NCT00000001", "Updated Title")])

    result = await db_session.scalar(select(Trial).where(Trial.trial_id == "NCT00000001"))
    assert result is not None
    assert result.title == "Updated Title"


@pytest.mark.asyncio
async def test_batch_size_respected(db_session: AsyncSession) -> None:
    """Load more trials than batch size to verify batching works."""
    trials = [_make_trial(f"NCT{i:08d}", f"Trial {i}") for i in range(15)]
    total, errors = await load_trials(db_session, trials, batch_size=5)
    assert total == 15
    assert errors == 0

    result = await db_session.scalars(select(Trial))
    rows = list(result.all())
    assert len(rows) == 15


@pytest.mark.asyncio
async def test_empty_list(db_session: AsyncSession) -> None:
    count = await upsert_trials_batch(db_session, [])
    assert count == 0


@pytest.mark.asyncio
async def test_load_trials_returns_counts(db_session: AsyncSession) -> None:
    trials = [_make_trial(f"NCT{i:08d}") for i in range(3)]
    total, errors = await load_trials(db_session, trials, batch_size=500)
    assert total == 3
    assert errors == 0
