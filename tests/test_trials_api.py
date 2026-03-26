"""Tests for the trials API endpoints."""

import pytest
from httpx import AsyncClient

from app.models.trial import Trial


@pytest.mark.asyncio
async def test_list_trials_empty_db(client: AsyncClient) -> None:
    response = await client.get("/api/v1/trials")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_list_trials_returns_data(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
    assert data["meta"]["total"] == 5


@pytest.mark.asyncio
async def test_list_trials_pagination(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 5
    assert data["meta"]["skip"] == 0
    assert data["meta"]["limit"] == 2
    assert data["meta"]["has_more"] is True


@pytest.mark.asyncio
async def test_list_trials_skip_offset(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials?skip=3&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["meta"]["has_more"] is False


@pytest.mark.asyncio
async def test_list_trials_limit_max_100(client: AsyncClient) -> None:
    response = await client.get("/api/v1/trials?limit=200")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_by_sponsor(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials?sponsor=pfizer")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    for trial in data["data"]:
        assert "pfizer" in trial["sponsor_name"].lower()


@pytest.mark.asyncio
async def test_filter_by_status(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials?status=completed")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_combined_filters(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials?sponsor=pfizer&status=recruiting")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    for trial in data["data"]:
        assert "pfizer" in trial["sponsor_name"].lower()
        assert "recruiting" in trial["status"].lower()


@pytest.mark.asyncio
async def test_get_trial_by_id(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials/NCT00000001")
    assert response.status_code == 200
    data = response.json()
    assert data["trial_id"] == "NCT00000001"
    assert data["title"] == "Test Trial Alpha"


@pytest.mark.asyncio
async def test_get_trial_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/trials/NCT_INVALID")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "NCT_INVALID" in data["detail"]


@pytest.mark.asyncio
async def test_pagination_meta_structure(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/trials?skip=0&limit=3")
    data = response.json()
    meta = data["meta"]
    assert "total" in meta
    assert "skip" in meta
    assert "limit" in meta
    assert "has_more" in meta
    assert meta["total"] == 5
    assert meta["has_more"] is True
