"""Ingestion trigger endpoint — supports synchronous and background modes."""

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.models.trial import Trial
from app.services.ingestion import (
    fetch_studies_page,
    load_trials,
    validate_and_parse_studies,
    log_ingestion_errors,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])

# Year ranges covering all CT.gov data — used by /ingest/all
YEAR_SHARDS = [
    (1999, 2005),
    (2006, 2009),
    (2010, 2012),
    (2013, 2015),
    (2016, 2017),
    (2018, 2019),
    (2020, 2020),
    (2021, 2021),
    (2022, 2022),
    (2023, 2023),
    (2024, 2024),
    (2025, 2026),
]

# In-memory job tracker (lost on restart — acceptable for this use case)
_jobs: dict[str, dict] = {}

# Limit concurrent background ingestion jobs
_semaphore = asyncio.Semaphore(3)


async def _run_ingestion_job(
    job_id: str,
    query_term: str | None,
    filter_advanced: str | None,
    max_pages: int | None,
) -> None:
    """Background task: fetch from CT.gov and load into DB."""
    async with _semaphore:
        settings = get_settings()
        factory = get_session_factory()

        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

        page_token: str | None = None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                while True:
                    studies, next_token = await fetch_studies_page(
                        client,
                        settings.ct_gov_base_url,
                        page_token=page_token,
                        query_term=query_term,
                        filter_advanced=filter_advanced,
                    )
                    _jobs[job_id]["pages_fetched"] += 1

                    valid_trials, parse_errors = validate_and_parse_studies(studies)
                    _jobs[job_id]["parse_errors"] += len(parse_errors)
                    log_ingestion_errors(parse_errors)

                    if valid_trials:
                        async with factory() as session:
                            loaded, load_errors = await load_trials(
                                session, valid_trials,
                                batch_size=settings.batch_size,
                                session_factory=factory,
                            )
                            _jobs[job_id]["loaded"] += loaded
                            _jobs[job_id]["load_errors"] += load_errors

                    if not next_token or (max_pages and _jobs[job_id]["pages_fetched"] >= max_pages):
                        break
                    page_token = next_token

            _jobs[job_id]["status"] = "complete"
        except Exception as e:
            logger.exception("Background ingestion job %s failed: %s", job_id, e)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
        finally:
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


def _create_job(
    year_start: int | None,
    year_end: int | None,
    query: str | None,
    max_pages: int | None,
    filter_advanced: str | None,
) -> str:
    """Create a job entry and return the job_id."""
    label = f"{year_start}-{year_end}" if year_start and year_end else (query or "all")
    job_id = f"ingest-{label}-{int(time.time())}"
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "filter": filter_advanced or query or "none",
        "max_pages": max_pages,
        "pages_fetched": 0,
        "loaded": 0,
        "parse_errors": 0,
        "load_errors": 0,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    return job_id


@router.post("/ingest")
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    query: str | None = Query(default=None, description="Optional search term"),
    max_pages: int | None = Query(default=None, description="Limit pages (1000 records/page)"),
    year_start: int | None = Query(default=None, description="Filter by StudyFirstPostDate start year"),
    year_end: int | None = Query(default=None, description="Filter by StudyFirstPostDate end year"),
    background: bool = Query(default=False, description="Run in background (returns immediately)"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Trigger ingestion from ClinicalTrials.gov.

    With background=false (default): runs inline and returns results (for small loads / demo).
    With background=true: returns immediately with a job_id. Check GET /ingest/status for progress.
    """
    filter_advanced: str | None = None
    if year_start and year_end:
        filter_advanced = f"AREA[StudyFirstPostDate]RANGE[01/01/{year_start},12/31/{year_end}]"

    # --- Background mode: return immediately ---
    if background:
        job_id = _create_job(year_start, year_end, query, max_pages, filter_advanced)
        background_tasks.add_task(_run_ingestion_job, job_id, query, filter_advanced, max_pages)
        return {
            "job_id": job_id,
            "status": "accepted",
            "message": "Ingestion started in background. Check GET /ingest/status for progress.",
        }

    # --- Synchronous mode (default): run inline ---
    settings = get_settings()
    factory = get_session_factory()

    total_loaded = 0
    total_parse_errors = 0
    total_load_errors = 0
    page_token: str | None = None
    page_count = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            studies, next_token = await fetch_studies_page(
                client,
                settings.ct_gov_base_url,
                page_token=page_token,
                query_term=query,
                filter_advanced=filter_advanced,
            )
            page_count += 1

            valid_trials, parse_errors = validate_and_parse_studies(studies)
            total_parse_errors += len(parse_errors)
            log_ingestion_errors(parse_errors)

            if valid_trials:
                loaded, load_errors = await load_trials(
                    session, valid_trials,
                    batch_size=settings.batch_size,
                    session_factory=factory,
                )
                total_loaded += loaded
                total_load_errors += load_errors

            if not next_token or (max_pages and page_count >= max_pages):
                break
            page_token = next_token

    return {
        "status": "complete",
        "loaded": total_loaded,
        "parse_errors": total_parse_errors,
        "load_errors": total_load_errors,
        "pages_fetched": page_count,
    }


async def _run_all_shards(job_ids: list[str], filters: list[str], max_pages: int | None) -> None:
    """Run all shards concurrently (semaphore limits to 3 at a time)."""
    await asyncio.gather(*(
        _run_ingestion_job(job_id, None, filt, max_pages)
        for job_id, filt in zip(job_ids, filters)
    ))


@router.post("/ingest/all")
async def trigger_all_shards(
    background_tasks: BackgroundTasks,
    max_pages: int | None = Query(default=None, description="Limit pages per shard (for testing)"),
) -> dict[str, object]:
    """Queue all 12 year-range shards as background ingestion jobs.

    Concurrency is limited by a semaphore (max 3 simultaneous).
    Safe to call even if data already exists — upserts prevent duplicates.
    """
    job_ids = []
    filters = []
    for start_year, end_year in YEAR_SHARDS:
        filter_advanced = f"AREA[StudyFirstPostDate]RANGE[01/01/{start_year},12/31/{end_year}]"
        job_id = _create_job(start_year, end_year, None, max_pages, filter_advanced)
        job_ids.append(job_id)
        filters.append(filter_advanced)

    background_tasks.add_task(_run_all_shards, job_ids, filters, max_pages)

    return {
        "status": "accepted",
        "shards_queued": len(job_ids),
        "job_ids": job_ids,
        "message": "All shards queued (3 concurrent). Check GET /ingest/status for progress.",
    }


@router.get("/ingest/status")
async def ingestion_status() -> dict[str, object]:
    """Return status of all ingestion jobs and current DB count."""
    # Use a short-lived session from the factory to avoid competing
    # with background tasks for the Depends(get_db) connection pool.
    factory = get_session_factory()
    try:
        async with factory() as session:
            total_trials = await session.scalar(select(func.count()).select_from(Trial)) or 0
    except Exception:
        total_trials = "unavailable"

    return {
        "db_total": total_trials,
        "jobs": list(_jobs.values()),
    }
