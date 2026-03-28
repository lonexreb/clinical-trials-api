"""Tests for the trials API endpoints."""

import pytest
from httpx import AsyncClient

from app.models.trial import Trial


@pytest.mark.asyncio
async def test_search_trials_empty_db(client: AsyncClient) -> None:
    response = await client.get("/trials/search")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_search_trials_returns_data(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
    assert data["meta"]["total"] == 5


@pytest.mark.asyncio
async def test_search_trials_pagination(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 5
    assert data["meta"]["skip"] == 0
    assert data["meta"]["limit"] == 2
    assert data["meta"]["has_more"] is True


@pytest.mark.asyncio
async def test_search_trials_skip_offset(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?skip=3&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["meta"]["has_more"] is False


@pytest.mark.asyncio
async def test_search_trials_limit_max_100(client: AsyncClient) -> None:
    response = await client.get("/trials/search?limit=200")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_by_sponsor(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?sponsor=pfizer")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    for trial in data["data"]:
        assert "pfizer" in trial["sponsor_name"].lower()


@pytest.mark.asyncio
async def test_filter_by_status(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?status=completed")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_filter_by_phase(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?phase=phase3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["phase"] == "PHASE3"


@pytest.mark.asyncio
async def test_combined_filters(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?sponsor=pfizer&status=recruiting")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    for trial in data["data"]:
        assert "pfizer" in trial["sponsor_name"].lower()
        assert "recruiting" in trial["status"].lower()


@pytest.mark.asyncio
async def test_combined_filters_with_phase(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?sponsor=pfizer&phase=phase1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["trial_id"] == "NCT00000003"


@pytest.mark.asyncio
async def test_get_trial_by_id(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/NCT00000001")
    assert response.status_code == 200
    data = response.json()
    assert data["trial_id"] == "NCT00000001"
    assert data["title"] == "Test Trial Alpha"


@pytest.mark.asyncio
async def test_get_trial_not_found(client: AsyncClient) -> None:
    response = await client.get("/trials/NCT_INVALID")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "NCT_INVALID" in data["detail"]


@pytest.mark.asyncio
async def test_pagination_meta_structure(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?skip=0&limit=3")
    data = response.json()
    meta = data["meta"]
    assert "total" in meta
    assert "skip" in meta
    assert "limit" in meta
    assert "has_more" in meta
    assert meta["total"] == 5
    assert meta["has_more"] is True


@pytest.mark.asyncio
async def test_response_includes_jsonb_fields(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Verify JSONB array fields appear in API response."""
    response = await client.get("/trials/NCT00000001")
    assert response.status_code == 200
    data = response.json()
    assert data["interventions"] == [{"type": "DRUG", "name": "TestDrug-A"}]
    assert data["primary_outcomes"][0]["measure"] == "Overall Survival"
    assert data["secondary_outcomes"][0]["measure"] == "Quality of Life"
    assert data["locations"][0]["country"] == "United States"


@pytest.mark.asyncio
async def test_response_null_jsonb_fields(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Verify null JSONB fields work correctly."""
    response = await client.get("/trials/NCT00000004")
    assert response.status_code == 200
    data = response.json()
    assert data["interventions"] is None
    assert data["primary_outcomes"] is None
    assert data["secondary_outcomes"] is None
    assert data["locations"] is None
