"""Bulk export endpoint: NDJSON and CSV streaming."""

import csv
import io
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.db.session import get_db
from app.models.trial import Trial
from app.schemas.trial import TrialResponse

router = APIRouter(prefix="/trials", tags=["export"])

EXPORT_FIELDS = [
    "trial_id",
    "title",
    "phase",
    "status",
    "sponsor_name",
    "interventions",
    "primary_outcomes",
    "secondary_outcomes",
    "start_date",
    "completion_date",
    "locations",
    "enrollment_number",
]

BATCH_SIZE = 1000


async def _stream_trials(session: AsyncSession) -> AsyncIterator[Trial]:
    """Yield trials in batches to avoid loading all into memory."""
    offset = 0
    while True:
        result = await session.scalars(
            select(Trial)
            .options(defer(Trial.raw_data))
            .offset(offset)
            .limit(BATCH_SIZE)
        )
        batch = list(result.all())
        if not batch:
            break
        for trial in batch:
            yield trial
        offset += BATCH_SIZE


async def _generate_ndjson(session: AsyncSession) -> AsyncIterator[str]:
    """Generate NDJSON lines from trial records."""
    async for trial in _stream_trials(session):
        row = TrialResponse.model_validate(trial)
        yield row.model_dump_json() + "\n"


async def _generate_csv(session: AsyncSession) -> AsyncIterator[str]:
    """Generate CSV rows from trial records."""
    # Header
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    yield output.getvalue()

    # Data rows
    async for trial in _stream_trials(session):
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
        row = TrialResponse.model_validate(trial)
        row_dict = {
            k: str(getattr(row, k, "")) if getattr(row, k, None) is not None else ""
            for k in EXPORT_FIELDS
        }
        writer.writerow(row_dict)
        yield output.getvalue()


@router.get("/export")
async def export_trials(
    format: str = Query(default="ndjson", pattern="^(ndjson|csv)$"),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export all trials as NDJSON or CSV streaming response.

    Responses are automatically gzip-compressed when the client sends
    Accept-Encoding: gzip (handled by GZipMiddleware).
    """
    if format == "csv":
        return StreamingResponse(
            _generate_csv(session),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trials.csv"},
        )
    else:
        return StreamingResponse(
            _generate_ndjson(session),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=trials.ndjson"},
        )
