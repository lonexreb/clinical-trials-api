import datetime

from pydantic import BaseModel, Field


class TrialBase(BaseModel):
    trial_id: str
    title: str
    phase: str | None = None
    status: str
    sponsor_name: str
    intervention_type: str | None = None
    intervention_name: str | None = None
    primary_outcome_description: str | None = None
    primary_outcome_measure: str | None = None
    start_date: datetime.date | None = None
    completion_date: datetime.date | None = None
    location_country: str | None = None
    enrollment_number: int | None = None


class TrialCreate(TrialBase):
    raw_data: dict[str, object]


class TrialResponse(TrialBase):
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


class TrialListResponse(BaseModel):
    data: list[TrialResponse]
    meta: PaginationMeta


class TrialFilters(BaseModel):
    sponsor: str | None = None
    status: str | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
