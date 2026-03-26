"""Bulk export endpoints: NDJSON and CSV streaming."""

import csv
import io
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.trial import Trial
from app.schemas.trial import TrialResponse

router = APIRouter(prefix="/api/v1", tags=["export"])

EXPORT_FIELDS = [
    "trial_id",
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
]


@router.get("/export")
async def export_trials(
    format: str = Query(default="ndjson", pattern="^(ndjson|csv)$"),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export all trials as NDJSON or CSV streaming response."""
    result = await session.stream_scalars(select(Trial))

    if format == "csv":
        return StreamingResponse(
            _generate_csv(result),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trials.csv"},
        )
    else:
        return StreamingResponse(
            _generate_ndjson(result),
            media_type="application/x-ndjson",
        )


async def _generate_ndjson(stream: AsyncIterator[Trial]) -> AsyncIterator[str]:
    """Generate NDJSON lines from trial records."""
    async for trial in stream:
        row = TrialResponse.model_validate(trial)
        yield row.model_dump_json() + "\n"


async def _generate_csv(stream: AsyncIterator[Trial]) -> AsyncIterator[str]:
    """Generate CSV rows from trial records."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    yield output.getvalue()
    output.truncate(0)
    output.seek(0)

    async for trial in stream:
        row = TrialResponse.model_validate(trial)
        row_dict = {
            k: str(getattr(row, k, "")) if getattr(row, k, None) is not None else ""
            for k in EXPORT_FIELDS
        }
        writer.writerow(row_dict)
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
