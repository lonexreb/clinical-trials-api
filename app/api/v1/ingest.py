"""Ingestion trigger endpoint — runs ingestion from the deployed service."""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.services.ingestion import run_full_ingestion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
async def trigger_ingestion(
    query: str | None = Query(default=None, description="Optional search term"),
    max_pages: int | None = Query(default=None, description="Limit pages (1000 records/page)"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Trigger ingestion from ClinicalTrials.gov. Runs synchronously and returns results."""
    settings = get_settings()
    factory = get_session_factory()

    loaded, parse_errors, load_errors = await run_full_ingestion(
        settings,
        session,
        query_term=query,
        max_pages=max_pages,
        session_factory=factory,
    )

    return {
        "status": "complete",
        "loaded": loaded,
        "parse_errors": parse_errors,
        "load_errors": load_errors,
    }
