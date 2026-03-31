"""Trial API endpoints: search, get by ID."""

import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.trial import Trial
from app.schemas.trial import PaginationMeta, TrialListResponse, TrialResponse

router = APIRouter(prefix="/trials", tags=["trials"])

SORT_COLUMNS = {
    "trial_id": Trial.trial_id,
    "title": Trial.title,
    "status": Trial.status,
    "phase": Trial.phase,
    "sponsor_name": Trial.sponsor_name,
    "start_date": Trial.start_date,
    "completion_date": Trial.completion_date,
    "updated_at": Trial.updated_at,
    "enrollment_number": Trial.enrollment_number,
}


@router.get("/search", response_model=TrialListResponse)
async def search_trials(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    sponsor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    phase: str | None = Query(default=None),
    study_type: str | None = Query(default=None),
    updated_since: datetime.date | None = Query(default=None),
    sort_by: str | None = Query(
        default=None,
        description="Sort by: trial_id, title, status, phase, sponsor_name, "
        "start_date, completion_date, updated_at, enrollment_number",
    ),
    order: Literal["asc", "desc"] = Query(default="asc", description="Sort order"),
    session: AsyncSession = Depends(get_db),
) -> TrialListResponse:
    """Search trials with pagination, filtering, and sorting."""
    query = select(Trial)
    count_query = select(func.count()).select_from(Trial)

    if sponsor:
        query = query.where(Trial.sponsor_name.ilike(f"%{sponsor}%"))
        count_query = count_query.where(Trial.sponsor_name.ilike(f"%{sponsor}%"))
    if status:
        query = query.where(Trial.status == status.upper())
        count_query = count_query.where(Trial.status == status.upper())
    if phase:
        query = query.where(Trial.phase.ilike(f"%{phase}%"))
        count_query = count_query.where(Trial.phase.ilike(f"%{phase}%"))
    if study_type:
        query = query.where(Trial.study_type == study_type.upper())
        count_query = count_query.where(Trial.study_type == study_type.upper())
    if updated_since:
        query = query.where(Trial.updated_at >= updated_since)
        count_query = count_query.where(Trial.updated_at >= updated_since)

    if sort_by and sort_by in SORT_COLUMNS:
        sort_col = SORT_COLUMNS[sort_by]
        query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    total = await session.scalar(count_query) or 0
    results = await session.scalars(query.offset(skip).limit(limit))
    trials = list(results.all())

    return TrialListResponse(
        data=[TrialResponse.model_validate(t) for t in trials],
        meta=PaginationMeta(
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit < total),
        ),
    )


@router.get("/{trial_id}", response_model=TrialResponse)
async def get_trial(
    trial_id: str,
    session: AsyncSession = Depends(get_db),
) -> TrialResponse:
    """Get a single trial by NCT ID."""
    result = await session.scalar(select(Trial).where(Trial.trial_id == trial_id))
    if not result:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return TrialResponse.model_validate(result)
