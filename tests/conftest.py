"""Shared test fixtures for the clinical trials API."""

import datetime
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import get_db
from app.main import app
from app.models.trial import Base, Trial

TEST_DATABASE_URL = "sqlite+aiosqlite:///"


@pytest.fixture()
async def db_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with test database session injected."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
async def seed_trials(db_session: AsyncSession) -> list[Trial]:
    """Create sample trial records for testing."""
    trials = [
        Trial(
            trial_id="NCT00000001",
            title="Test Trial Alpha",
            phase="PHASE3",
            status="RECRUITING",
            sponsor_name="Pfizer",
            intervention_type="DRUG",
            intervention_name="TestDrug-A",
            primary_outcome_measure="Overall Survival",
            primary_outcome_description="Time from randomization to death",
            start_date=datetime.date(2023, 1, 15),
            completion_date=datetime.date(2025, 6, 30),
            location_country="United States",
            enrollment_number=500,
            raw_data={"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}},
        ),
        Trial(
            trial_id="NCT00000002",
            title="Test Trial Beta",
            phase="PHASE2",
            status="COMPLETED",
            sponsor_name="Novartis",
            intervention_type="BIOLOGICAL",
            intervention_name="BioAgent-B",
            primary_outcome_measure="Progression Free Survival",
            primary_outcome_description="Time to disease progression",
            start_date=datetime.date(2020, 3, 1),
            completion_date=datetime.date(2023, 12, 31),
            location_country="Germany",
            enrollment_number=200,
            raw_data={"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}}},
        ),
        Trial(
            trial_id="NCT00000003",
            title="Test Trial Gamma",
            phase="PHASE1",
            status="RECRUITING",
            sponsor_name="Pfizer",
            intervention_type="DRUG",
            intervention_name="TestDrug-C",
            primary_outcome_measure="Dose Limiting Toxicity",
            primary_outcome_description=None,
            start_date=datetime.date(2024, 6, 1),
            completion_date=None,
            location_country="United Kingdom",
            enrollment_number=50,
            raw_data={"protocolSection": {"identificationModule": {"nctId": "NCT00000003"}}},
        ),
        Trial(
            trial_id="NCT00000004",
            title="Test Trial Delta",
            phase=None,
            status="TERMINATED",
            sponsor_name="Roche",
            intervention_type=None,
            intervention_name=None,
            primary_outcome_measure=None,
            primary_outcome_description=None,
            start_date=None,
            completion_date=None,
            location_country=None,
            enrollment_number=None,
            raw_data={"protocolSection": {"identificationModule": {"nctId": "NCT00000004"}}},
        ),
        Trial(
            trial_id="NCT00000005",
            title="Test Trial Epsilon",
            phase="PHASE4",
            status="ACTIVE_NOT_RECRUITING",
            sponsor_name="Novartis",
            intervention_type="DEVICE",
            intervention_name="MedDevice-E",
            primary_outcome_measure="Adverse Events",
            primary_outcome_description="Incidence of adverse events",
            start_date=datetime.date(2022, 9, 15),
            completion_date=datetime.date(2026, 3, 1),
            location_country="Japan",
            enrollment_number=1000,
            raw_data={"protocolSection": {"identificationModule": {"nctId": "NCT00000005"}}},
        ),
    ]
    db_session.add_all(trials)
    await db_session.commit()
    for trial in trials:
        await db_session.refresh(trial)
    return trials
