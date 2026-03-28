"""Ingestion trigger endpoint — runs ingestion from the deployed service."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.services.ingestion import (
    fetch_studies_page,
    load_trials,
    validate_and_parse_studies,
    log_ingestion_errors,
)

import httpx

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
async def trigger_ingestion(
    query: str | None = Query(default=None, description="Optional search term"),
    max_pages: int | None = Query(default=None, description="Limit pages (1000 records/page)"),
    year_start: int | None = Query(default=None, description="Filter by StudyFirstPostDate start year"),
    year_end: int | None = Query(default=None, description="Filter by StudyFirstPostDate end year"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Trigger ingestion from ClinicalTrials.gov.

    Supports year_start/year_end to shard by date range for parallel loading.
    """
    settings = get_settings()
    factory = get_session_factory()

    filter_advanced: str | None = None
    if year_start and year_end:
        filter_advanced = f"AREA[StudyFirstPostDate]RANGE[01/01/{year_start},12/31/{year_end}]"

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
