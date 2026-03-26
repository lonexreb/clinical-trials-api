"""Tests for the bulk export endpoints."""

import csv
import io
import json

import pytest
from httpx import AsyncClient

from app.models.trial import Trial


@pytest.mark.asyncio
async def test_export_ndjson_format(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/export?format=ndjson")
    assert response.status_code == 200

    lines = response.text.strip().split("\n")
    assert len(lines) == 5

    for line in lines:
        parsed = json.loads(line)
        assert "trial_id" in parsed
        assert "title" in parsed
        assert "status" in parsed


@pytest.mark.asyncio
async def test_export_ndjson_content_type(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/export?format=ndjson")
    assert "application/x-ndjson" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_export_ndjson_empty_db(client: AsyncClient) -> None:
    response = await client.get("/api/v1/export?format=ndjson")
    assert response.status_code == 200
    assert response.text.strip() == ""


@pytest.mark.asyncio
async def test_export_csv_format(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/export?format=csv")
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    # Header + 5 data rows
    assert len(rows) == 6


@pytest.mark.asyncio
async def test_export_csv_content_type(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/export?format=csv")
    assert "text/csv" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_export_csv_header_fields(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/export?format=csv")
    reader = csv.reader(io.StringIO(response.text))
    header = next(reader)
    assert "trial_id" in header
    assert "title" in header
    assert "status" in header
    assert "sponsor_name" in header
    assert "phase" in header


@pytest.mark.asyncio
async def test_export_invalid_format(client: AsyncClient) -> None:
    response = await client.get("/api/v1/export?format=xml")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_default_format_is_ndjson(client: AsyncClient, seed_trials: list[Trial]) -> None:
    response = await client.get("/api/v1/export")
    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]
