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
async def test_filter_by_status_exact_match(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Status filter uses exact match — RECRUITING should NOT match ACTIVE_NOT_RECRUITING."""
    response = await client.get("/trials/search?status=RECRUITING")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    for trial in data["data"]:
        assert trial["status"] == "RECRUITING"


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
        assert trial["status"] == "RECRUITING"


@pytest.mark.asyncio
async def test_combined_filters_with_phase(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/trials/search?sponsor=pfizer&phase=phase1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["trial_id"] == "NCT00000003"


@pytest.mark.asyncio
async def test_filter_updated_since(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Filter trials by updated_since date."""
    response = await client.get("/trials/search?updated_since=2099-01-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 0

    response = await client.get("/trials/search?updated_since=2000-01-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5


@pytest.mark.asyncio
async def test_filter_updated_since_invalid_date(client: AsyncClient) -> None:
    """Invalid date format returns 422."""
    response = await client.get("/trials/search?updated_since=not-a-date")
    assert response.status_code == 422


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
    assert data["conditions"] == ["Lung Cancer", "Non-Small Cell Lung Cancer"]
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
    assert data["conditions"] is None
    assert data["locations"] is None
    assert data["study_type"] is None
    assert data["eligibility_criteria"] is None
    assert data["mesh_terms"] is None
    assert data["references"] is None
    assert data["investigators"] is None


@pytest.mark.asyncio
async def test_response_includes_new_enrichment_fields(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Verify new schema enrichment fields appear in API response."""
    response = await client.get("/trials/NCT00000001")
    assert response.status_code == 200
    data = response.json()
    assert data["study_type"] == "INTERVENTIONAL"
    assert "Age >= 18" in data["eligibility_criteria"]
    assert data["mesh_terms"] == ["Lung Neoplasms", "Carcinoma, Non-Small-Cell Lung"]
    assert data["references"][0]["pmid"] == "12345678"
    assert data["investigators"][0]["name"] == "Dr. Smith"
    assert data["source"] == "clinicaltrials.gov"


@pytest.mark.asyncio
async def test_filter_by_study_type(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Filter by study_type uses exact match."""
    response = await client.get("/trials/search?study_type=OBSERVATIONAL")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["study_type"] == "OBSERVATIONAL"


@pytest.mark.asyncio
async def test_sort_by_start_date_asc(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Sort by start_date ascending."""
    response = await client.get("/trials/search?sort_by=start_date&order=asc")
    assert response.status_code == 200
    data = response.json()
    dates = [t["start_date"] for t in data["data"] if t["start_date"] is not None]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_sort_by_start_date_desc(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Sort by start_date descending."""
    response = await client.get("/trials/search?sort_by=start_date&order=desc")
    assert response.status_code == 200
    data = response.json()
    # NULL dates sort differently across DBs, so just check non-null ones are descending
    dates = [t["start_date"] for t in data["data"] if t["start_date"] is not None]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_sort_by_updated_at(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Sort by updated_at is accepted."""
    response = await client.get("/trials/search?sort_by=updated_at&order=desc")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5


@pytest.mark.asyncio
async def test_sort_by_invalid_column_ignored(client: AsyncClient, seed_trials: list[Trial]) -> None:
    """Invalid sort_by is silently ignored (no error)."""
    response = await client.get("/trials/search?sort_by=nonexistent")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
