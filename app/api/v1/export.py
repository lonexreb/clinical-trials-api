"""Bulk export endpoints: NDJSON and CSV streaming."""

import csv
import io
from collections.abc import Iterator

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
    result = await session.scalars(select(Trial))
    trials = list(result.all())

    if format == "csv":
        return StreamingResponse(
            _generate_csv(trials),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trials.csv"},
        )
    else:
        return StreamingResponse(
            _generate_ndjson(trials),
            media_type="application/x-ndjson",
        )


def _generate_ndjson(trials: list[Trial]) -> Iterator[str]:
    """Generate NDJSON lines from trial records."""
    for trial in trials:
        row = TrialResponse.model_validate(trial)
        yield row.model_dump_json() + "\n"


def _generate_csv(trials: list[Trial]) -> Iterator[str]:
    """Generate CSV rows from trial records."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    yield output.getvalue()
    output.truncate(0)
    output.seek(0)

    for trial in trials:
        row = TrialResponse.model_validate(trial)
        row_dict = {
            k: str(getattr(row, k, "")) if getattr(row, k, None) is not None else ""
            for k in EXPORT_FIELDS
        }
        writer.writerow(row_dict)
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
