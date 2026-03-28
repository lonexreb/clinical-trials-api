"""Fetch studies from ClinicalTrials.gov API v2 and orchestrate ingestion."""

import json
import logging
from pathlib import Path

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.schemas.trial import TrialCreate
from app.services.loader import load_trials
from app.services.parser import parse_study

logger = logging.getLogger(__name__)


async def fetch_studies_page(
    client: httpx.AsyncClient,
    base_url: str,
    page_size: int = 1000,
    page_token: str | None = None,
    query_term: str | None = None,
) -> tuple[list[dict[str, object]], str | None]:
    """Fetch a single page of studies from CT.gov API v2.

    Returns (studies_list, next_page_token).
    next_page_token is None when there are no more pages.
    """
    params: dict[str, str | int] = {"pageSize": page_size, "format": "json"}
    if page_token:
        params["pageToken"] = page_token
    if query_term:
        params["query.term"] = query_term

    response = await client.get(base_url, params=params)
    response.raise_for_status()
    data = response.json()

    studies: list[dict[str, object]] = data.get("studies", [])
    next_token: str | None = data.get("nextPageToken")

    return studies, next_token


async def fetch_all_studies(
    settings: Settings,
    query_term: str | None = None,
    max_pages: int | None = None,
) -> list[dict[str, object]]:
    """Fetch all studies by following pagination tokens.

    Args:
        settings: App settings with ct_gov_base_url.
        query_term: Optional search term to filter studies.
        max_pages: Optional limit on number of pages to fetch (for dev/testing).

    Returns:
        List of raw study dicts from the CT.gov API.
    """
    all_studies: list[dict[str, object]] = []
    page_token: str | None = None
    page_count = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            studies, next_token = await fetch_studies_page(
                client,
                settings.ct_gov_base_url,
                page_token=page_token,
                query_term=query_term,
            )
            all_studies.extend(studies)
            page_count += 1
            logger.info("Fetched page %d: %d studies (total: %d)", page_count, len(studies), len(all_studies))

            if not next_token or (max_pages is not None and page_count >= max_pages):
                break
            page_token = next_token

    return all_studies


def validate_and_parse_studies(
    studies: list[dict[str, object]],
) -> tuple[list[TrialCreate], list[dict[str, object]]]:
    """Parse and validate studies. Returns (valid_trials, error_records)."""
    valid: list[TrialCreate] = []
    errors: list[dict[str, object]] = []

    for study in studies:
        try:
            parsed = parse_study(study)
            trial = TrialCreate(**parsed)
            valid.append(trial)
        except (ValidationError, KeyError, TypeError) as e:
            nct_id = "UNKNOWN"
            protocol = study.get("protocolSection")
            if isinstance(protocol, dict):
                id_mod = protocol.get("identificationModule")
                if isinstance(id_mod, dict):
                    nct_id = str(id_mod.get("nctId", "UNKNOWN"))
            errors.append(
                {
                    "trial_id": nct_id,
                    "error": str(e),
                    "raw_data": study,
                }
            )
            logger.warning("Failed to parse study %s: %s", nct_id, e)

    return valid, errors


def log_ingestion_errors(errors: list[dict[str, object]], output_path: str = "ingestion_errors.jsonl") -> None:
    """Write failed records to a JSONL file for review."""
    if not errors:
        return

    path = Path(output_path)
    with path.open("a", encoding="utf-8") as f:
        for error in errors:
            f.write(json.dumps(error, default=str) + "\n")

    logger.info("Logged %d ingestion errors to %s", len(errors), output_path)


async def run_full_ingestion(
    settings: Settings,
    session: AsyncSession,
    query_term: str | None = None,
    max_pages: int | None = None,
) -> tuple[int, int, int]:
    """Full ingestion pipeline: fetch -> parse -> validate -> load -> log errors.

    Returns (total_loaded, total_parse_errors, total_load_errors).
    """
    logger.info("Starting ingestion (query=%s, max_pages=%s)", query_term, max_pages)

    # Fetch
    studies = await fetch_all_studies(settings, query_term=query_term, max_pages=max_pages)
    logger.info("Fetched %d studies from CT.gov", len(studies))

    # Parse and validate
    valid_trials, parse_errors = validate_and_parse_studies(studies)
    logger.info("Parsed %d valid trials, %d errors", len(valid_trials), len(parse_errors))

    # Log parse errors
    log_ingestion_errors(parse_errors)

    # Load into database
    from app.db.session import session_factory as sf

    total_loaded, load_errors = await load_trials(
        session, valid_trials, batch_size=settings.batch_size, session_factory=sf
    )
    logger.info("Loaded %d trials, %d load errors", total_loaded, load_errors)

    return total_loaded, len(parse_errors), load_errors
