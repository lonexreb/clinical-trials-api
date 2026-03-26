"""Trial API endpoints: list, get, filter."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.trial import Trial
from app.schemas.trial import PaginationMeta, TrialListResponse, TrialResponse

router = APIRouter(prefix="/api/v1", tags=["trials"])


@router.get("/trials", response_model=TrialListResponse)
async def list_trials(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    sponsor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> TrialListResponse:
    """List trials with pagination and optional filtering."""
    query = select(Trial)
    count_query = select(func.count()).select_from(Trial)

    if sponsor:
        query = query.where(Trial.sponsor_name.ilike(f"%{sponsor}%"))
        count_query = count_query.where(Trial.sponsor_name.ilike(f"%{sponsor}%"))
    if status:
        query = query.where(Trial.status.ilike(f"%{status}%"))
        count_query = count_query.where(Trial.status.ilike(f"%{status}%"))

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


@router.get("/trials/{trial_id}", response_model=TrialResponse)
async def get_trial(
    trial_id: str,
    session: AsyncSession = Depends(get_db),
) -> TrialResponse:
    """Get a single trial by NCT ID."""
    result = await session.scalar(select(Trial).where(Trial.trial_id == trial_id))
    if not result:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return TrialResponse.model_validate(result)
